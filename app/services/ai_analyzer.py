"""Claude AI-powered training readiness analysis."""
from __future__ import annotations

import contextlib
import json
import logging
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar, TypedDict

import yaml
from anthropic import Anthropic

from app.config import get_settings
from app.database import SessionLocal
from app.models.database_models import DailyMetric
from app.services.alert_detector import AlertDetector
from app.services.data_processor import DataProcessor
from app.services.garmin_service import GarminService
from app.services.hr_zones import calculate_hr_zones, format_hr_zones_for_prompt


logger = logging.getLogger(__name__)


class CacheEntry(TypedDict):
    """Cache entry with expiration metadata."""
    data: dict[str, Any]
    expires_at: datetime


class AIAnalyzer:
    """Analyzes training readiness using Claude AI and live Garmin data."""

    # Class-level cache with TTL support (persists across requests within same process)
    # Thread-safe with lock to prevent race conditions in multi-threaded FastAPI environment
    _response_cache: ClassVar[dict[tuple[date, str | None], CacheEntry]] = {}
    _cache_lock: ClassVar[threading.Lock] = threading.Lock()
    _cache_ttl_minutes: int = 60  # Match frontend cache TTL
    _max_cache_size: int = 100  # Prevent unbounded memory growth

    # Issue #3: Personal info cache (age/LTHR change infrequently)
    _personal_info_cache: ClassVar[dict[str, Any] | None] = None
    _personal_info_expires_at: ClassVar[datetime | None] = None
    _PERSONAL_INFO_TTL_HOURS: ClassVar[int] = 24

    def __init__(self) -> None:
        settings = get_settings()
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-5-20250929"

        # Load activity classification thresholds from config
        prompt_config = self._load_prompt_config(settings.prompt_config_path)
        activity_config = prompt_config.get("activity_classification", {})

        # Training effect thresholds
        te_config = activity_config.get("training_effect", {})
        self.training_effect_high = te_config.get("high_impact_threshold", 3.0)
        self.training_effect_moderate = te_config.get("moderate_impact_threshold", 2.5)
        self.training_effect_very_high = te_config.get("very_high_threshold", 4.0)

        # Heart rate thresholds
        hr_config = activity_config.get("heart_rate", {})
        self.hr_zone_threshold = hr_config.get("zone_threshold", 0.7)
        self.hr_high_intensity = hr_config.get("high_intensity_threshold", 0.85)

        # Duration thresholds
        duration_config = activity_config.get("duration", {})
        self.duration_minimum_seconds = duration_config.get("minimum_seconds", 1800)
        self.duration_long_minutes = duration_config.get("long_duration_minutes", 90)

        # Performance analysis thresholds (Phase 1 + Phase 2)
        perf_config = prompt_config.get("performance_analysis", {})
        self.workout_recency_hours = perf_config.get("workout_recency_hours", 72)
        self.min_duration_seconds = perf_config.get("min_duration_seconds", 300)
        self.similar_workout_lookback_days = perf_config.get("similar_workout_lookback_days", 14)
        self.min_similar_workouts = perf_config.get("min_similar_workouts", 2)
        self.hr_deviation_threshold = perf_config.get("hr_deviation_threshold", 5.0)
        self.pace_deviation_threshold_pct = perf_config.get("pace_deviation_threshold_pct", 5.0)
        self.stable_threshold = perf_config.get("stable_threshold", 5.0)

    def _get_cached_response(self, cache_key: tuple[date, str | None]) -> dict[str, Any] | None:
        """Retrieve cached response if valid (not expired). Thread-safe."""
        with self._cache_lock:
            if cache_key not in self._response_cache:
                return None

            entry = self._response_cache[cache_key]
            if datetime.utcnow() > entry["expires_at"]:
                # Expired - remove and return None
                del self._response_cache[cache_key]
                logger.debug("Cache entry expired for %s (locale=%s)", cache_key[0].isoformat(), cache_key[1] or "default")
                return None

            return entry["data"]

    def _set_cached_response(self, cache_key: tuple[date, str | None], data: dict[str, Any]) -> None:
        """Cache response with TTL expiration and size limit enforcement. Thread-safe."""
        try:
            should_cleanup = False
            with self._cache_lock:
                # Enforce cache size limit (FIFO eviction)
                if len(self._response_cache) >= self._max_cache_size:
                    # Remove oldest entry
                    oldest_key = next(iter(self._response_cache))
                    del self._response_cache[oldest_key]
                    logger.debug("Cache full - evicted oldest entry")

                # Store with expiration
                self._response_cache[cache_key] = {
                    "data": data,
                    "expires_at": datetime.utcnow() + timedelta(minutes=self._cache_ttl_minutes)
                }
                logger.debug("Cached AI response for %s (locale=%s), expires in %d min",
                            cache_key[0].isoformat(), cache_key[1] or "default", self._cache_ttl_minutes)

                # Check if cleanup needed (every 10 cache writes)
                should_cleanup = len(self._response_cache) % 10 == 0

            # Cleanup outside lock to minimize hold time
            if should_cleanup:
                self._cleanup_expired_cache()
        except Exception as e:
            # Non-fatal - log and continue
            logger.warning("Failed to cache AI response: %s", e, exc_info=True)

    def _cleanup_expired_cache(self) -> None:
        """Remove all expired cache entries. Thread-safe."""
        now = datetime.utcnow()
        with self._cache_lock:
            expired_keys = [k for k, v in self._response_cache.items() if now > v["expires_at"]]
            for key in expired_keys:
                del self._response_cache[key]
        if expired_keys:
            logger.debug("Cleaned up %d expired cache entries", len(expired_keys))

    @classmethod
    def clear_cache(cls) -> None:
        """Clear all cached responses. Used after manual data sync. Thread-safe."""
        with cls._cache_lock:
            cls._response_cache.clear()
            # Also clear personal info cache on manual sync
            cls._personal_info_cache = None
            cls._personal_info_expires_at = None
        logger.info("AI response cache and personal info cache cleared")

    def _fetch_personal_info_cached(self, garmin: GarminService) -> dict[str, Any]:
        """Fetch personal info with 24h cache (age/LTHR change infrequently).

        Issue #3: Cache personal info to avoid expensive API calls on every analysis.

        Args:
            garmin: GarminService instance to fetch data from

        Returns:
            Personal info dictionary with age, max_hr, lactate_threshold_hr
        """
        now = datetime.utcnow()

        # First check (fast path - unlocked read)
        with self._cache_lock:
            if (self._personal_info_cache is not None
                and self._personal_info_expires_at is not None
                and now < self._personal_info_expires_at):
                logger.debug("Using cached personal info (fast path)")
                return self._personal_info_cache

        # Fetch fresh data (outside lock to avoid blocking other threads)
        logger.debug("Fetching fresh personal info from Garmin")
        personal_info = garmin.get_personal_info()

        # Second check (slow path - double-checked locking)
        with self._cache_lock:
            # Verify another thread didn't already cache fresh data while we were fetching
            if (self._personal_info_cache is not None
                and self._personal_info_expires_at is not None
                and now < self._personal_info_expires_at):
                logger.debug("Another thread cached data while we were fetching, using theirs")
                return self._personal_info_cache

            # We're first - cache our fetched data if successful
            if personal_info.get("error") is None:
                self._personal_info_cache = personal_info
                self._personal_info_expires_at = now + timedelta(hours=self._PERSONAL_INFO_TTL_HOURS)
                logger.info("Cached personal info for %dh", self._PERSONAL_INFO_TTL_HOURS)
            else:
                logger.warning("Personal info fetch failed, not caching: %s", personal_info.get("error"))

        return personal_info

    async def analyze_daily_readiness(
        self,
        target_date: date,
        locale: str | None = None,
    ) -> dict[str, Any]:
        """
        Analyze daily training readiness based on live Garmin data.

        Fetches:
        - Today's sleep, HRV, heart rate, stress, body battery
        - Last 7 days of activities for training load context
        - Calculates simple baselines on the fly

        Returns structured recommendation with:
        - Readiness score (0-100)
        - Recommendation (high_intensity, moderate, easy, rest)
        - Suggested workout
        - Key factors and red flags
        - Recovery tips
        """

        # Check cache first (key is date + locale)
        cache_key = (target_date, locale)
        cached_response = self._get_cached_response(cache_key)
        if cached_response is not None:
            logger.info("Cache HIT for %s (locale=%s) - returning cached AI response", target_date.isoformat(), locale or "default")
            return cached_response

        # Fetch live Garmin data
        logger.info("Cache MISS - Starting readiness analysis for %s (locale=%s)", target_date.isoformat(), locale or "default")
        garmin = GarminService()
        try:
            logger.debug("Fetching Garmin data for %s", target_date.isoformat())
            garmin.login()
            data = self._fetch_garmin_data(garmin, target_date)

            # Fetch personal info and calculate HR zones (Issue #3: using cached version)
            personal_info = self._fetch_personal_info_cached(garmin)
            hr_zones = self._calculate_hr_zones(personal_info)
        finally:
            try:
                garmin.logout()
            except Exception:
                pass

        logger.debug("Calculating baselines for %s", target_date.isoformat())
        # Calculate baselines
        baselines = self._calculate_baselines(data)
        historical_baselines = self._get_historical_baselines(target_date)

        # Detect training alerts BEFORE building prompt (so AI can respect them)
        detected_alerts = []
        try:
            with SessionLocal() as session:
                detector = AlertDetector()
                # Pass historical_baselines directly - AlertDetector expects flat structure
                detected_alerts = detector.detect_alerts(target_date, session, context=historical_baselines)
                if detected_alerts:
                    logger.info("Detected %d alert(s) for %s BEFORE AI analysis", len(detected_alerts), target_date.isoformat())
        except (ValueError, KeyError, TypeError) as e:
            # Don't fail the entire analysis if alert detection fails
            logger.warning("Alert detection failed: %s", str(e), exc_info=True)

        # Build comprehensive prompt with HR zones and alerts
        language, prompt, system_prompt, extended_signals = self._build_prompt(
            target_date,
            data,
            baselines,
            historical_baselines,
            hr_zones=hr_zones,
            locale=locale,
            alerts=detected_alerts,
        )

        # Get AI analysis
        request_payload = {
            "model": self.model,
            "max_tokens": 4096,
            "temperature": 0.3,  # Balance consistency with natural variation
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            request_payload["system"] = system_prompt

        try:
            response = self.client.messages.create(**request_payload)
        except Exception:
            logger.exception("Claude analysis failed for %s", target_date.isoformat())
            raise

        # Parse response
        result = self._parse_response(response.content[0].text)
        result["language"] = language
        logger.info(
            "Readiness result for %s | score=%s recommendation=%s",
            target_date.isoformat(),
            result.get("readiness_score"),
            result.get("recommendation"),
        )

        # Add Phase 1 enhanced metrics to response
        training_readiness_data = data.get("training_readiness", {})
        training_status_data = data.get("training_status", {})
        spo2_data = data.get("spo2", {})
        respiration_data = data.get("respiration", {})

        # Extract Training Readiness (API returns list, uses "score" key)
        training_readiness_score = None
        if training_readiness_data and isinstance(training_readiness_data, list) and len(training_readiness_data) > 0:
            if isinstance(training_readiness_data[0], dict):
                training_readiness_score = training_readiness_data[0].get("score")
        elif training_readiness_data and isinstance(training_readiness_data, dict):
            training_readiness_score = training_readiness_data.get("score")

        # Extract Training Status (nested mostRecent* keys)
        vo2_max = None
        training_status = None
        if training_status_data and isinstance(training_status_data, dict):
            # VO2 Max - nested in mostRecentVO2Max → generic → vo2MaxValue
            if "mostRecentVO2Max" in training_status_data:
                vo2_data = training_status_data.get("mostRecentVO2Max")
                if vo2_data and isinstance(vo2_data, dict):
                    generic = vo2_data.get("generic")
                    if generic and isinstance(generic, dict):
                        vo2_max = generic.get("vo2MaxValue")

            # Training Status - nested in mostRecentTrainingStatus → latestTrainingStatusData → {deviceId}
            if "mostRecentTrainingStatus" in training_status_data:
                status_data = training_status_data.get("mostRecentTrainingStatus")
                if status_data and isinstance(status_data, dict):
                    latest = status_data.get("latestTrainingStatusData")
                    if latest and isinstance(latest, dict):
                        # Get first device's data (usually primary device)
                        for device_id, device_data in latest.items():
                            if device_data and isinstance(device_data, dict):
                                training_status = device_data.get("trainingStatusFeedbackPhrase")
                                break

        # Extract SPO2 (root level keys)
        spo2_avg = None
        spo2_min = None
        if spo2_data and isinstance(spo2_data, dict):
            spo2_avg = spo2_data.get("avgSleepSpO2")
            spo2_min = spo2_data.get("lowestSpO2")

        # Extract respiration (avgSleepRespirationValue)
        respiration_avg = None
        if respiration_data and isinstance(respiration_data, dict):
            respiration_avg = respiration_data.get("avgSleepRespirationValue")

        result["enhanced_metrics"] = {
            "training_readiness_score": training_readiness_score,
            "vo2_max": vo2_max,
            "training_status": training_status,
            "spo2_avg": spo2_avg,
            "spo2_min": spo2_min,
            "respiration_avg": respiration_avg,
        }

        if extended_signals:
            result["extended_signals"] = extended_signals

        # Attach structured context for UI consumers
        result["recent_training_load"] = baselines
        if historical_baselines:
            result["historical_baselines"] = historical_baselines

        readiness_history = self._get_readiness_history(target_date)
        if readiness_history:
            result["readiness_history"] = readiness_history

        latest_sync = self._get_latest_metric_sync()
        if latest_sync:
            result["latest_data_sync"] = latest_sync

        result["generated_at"] = datetime.utcnow().isoformat() + "Z"

        # Add detected alerts to result (already detected before prompt building)
        if detected_alerts:
            result["alerts"] = detected_alerts

        # Cache the response with TTL
        self._set_cached_response(cache_key, result)

        return result

    def _fetch_garmin_data(self, garmin: GarminService, target_date: date) -> dict[str, Any]:
        """Fetch all relevant data from Garmin for analysis."""

        date_str = target_date.isoformat()

        # Fetch today's metrics
        try:
            stats = garmin._client.get_stats(date_str)
        except Exception as e:
            stats = {"error": str(e)}

        try:
            sleep = garmin._client.get_sleep_data(date_str)
        except Exception as e:
            sleep = {"error": str(e)}

        try:
            hrv = garmin._client.get_hrv_data(date_str)
        except Exception as e:
            hrv = {"error": str(e)}

        try:
            hr = garmin._client.get_heart_rates(date_str)
        except Exception as e:
            hr = {"error": str(e)}

        try:
            stress = garmin._client.get_stress_data(date_str)
        except Exception as e:
            stress = {"error": str(e)}

        try:
            body_battery = garmin._client.get_body_battery(date_str)
        except Exception as e:
            body_battery = {"error": str(e)}

        # Fetch enhanced metrics (Phase 1)
        try:
            training_readiness = garmin._client.get_training_readiness(date_str)
        except Exception:
            training_readiness = {}

        try:
            training_status = garmin._client.get_training_status(date_str)
        except Exception:
            training_status = {}

        try:
            spo2 = garmin._client.get_spo2_data(date_str)
        except Exception:
            spo2 = {}

        try:
            respiration = garmin._client.get_respiration_data(date_str)
        except Exception:
            respiration = {}

        # Fetch last 7 days of activities
        activities = []
        try:
            activities_list = garmin._client.get_activities(0, 20)  # Get last 20 activities
            # Filter to last 7 days
            seven_days_ago = target_date - timedelta(days=7)
            for activity in activities_list:
                if activity.get("startTimeLocal"):
                    activity_date_str = activity["startTimeLocal"][:10]
                    activity_date = date.fromisoformat(activity_date_str)
                    if activity_date >= seven_days_ago:
                        activities.append(activity)
        except Exception as e:
            activities = [{"error": str(e)}]

        # Analyze most recent workout performance (Phase 1 - Individual Session Performance)
        recent_workout_analysis = None
        if activities and "error" not in str(activities):
            recent_workout = self._analyze_most_recent_workout(activities, target_date)
            if recent_workout:
                comparison = self._compare_to_recent_similar_workouts(recent_workout, activities)
                condition = self._calculate_performance_condition(recent_workout, comparison)
                # Pass Phase 2 detail metrics if available
                detail_metrics = recent_workout.get("detail_metrics")
                recent_workout_analysis = self._format_recent_workout_analysis(
                    recent_workout, comparison, condition, detail_metrics
                )

        return {
            "date": date_str,
            "stats": stats,
            "sleep": sleep,
            "hrv": hrv,
            "heart_rate": hr,
            "stress": stress,
            "body_battery": body_battery,
            "training_readiness": training_readiness,
            "training_status": training_status,
            "spo2": spo2,
            "respiration": respiration,
            "recent_activities": activities[:7],  # Last 7 days
            "recent_workout_analysis": recent_workout_analysis,
        }

    def _analyze_most_recent_workout(
        self, activities: list[dict[str, Any]], target_date: date
    ) -> dict[str, Any] | None:
        """Find and analyze the most recent workout within 72 hours of target date.

        Args:
            activities: List of Garmin activity dictionaries
            target_date: Date to analyze (today)

        Returns:
            Dictionary with workout details or None if no recent workout found:
            {
                "activity_type": str,
                "date": date,
                "duration_seconds": int,
                "distance_meters": float | None,
                "avg_hr": int | None,
                "max_hr": int | None,
                "avg_pace": float | None (min/km),
                "aerobic_training_effect": float | None,
                "anaerobic_training_effect": float | None,
                "hours_since_workout": float,
                "activity_id": int | None,
                "detail_metrics": dict | None  # Phase 2 detailed metrics
            }

        Configuration:
            workout_recency_hours: Loaded from config (default: 72)
            min_duration_seconds: Loaded from config (default: 300)
        """
        if not activities or "error" in str(activities):
            return None

        most_recent = None
        most_recent_datetime = None
        current_datetime = datetime.combine(target_date, datetime.now().time())

        for activity in activities:
            if not isinstance(activity, dict) or "error" in activity:
                continue

            # Extract activity datetime (parse full timestamp including time)
            start_time_local = activity.get("startTimeLocal")
            if not start_time_local:
                continue

            try:
                # Parse full datetime (YYYY-MM-DDTHH:MM:SS)
                activity_datetime = datetime.fromisoformat(start_time_local[:19])
            except (ValueError, TypeError):
                continue

            # Check if within recency window (compare to current datetime)
            time_diff = current_datetime - activity_datetime
            hours_since = time_diff.total_seconds() / 3600

            if hours_since < 0 or hours_since > self.workout_recency_hours:
                continue

            # Skip very short activities
            duration = activity.get("duration")
            if not duration or duration < self.min_duration_seconds:
                continue

            # Track most recent (based on datetime, not just date)
            if most_recent_datetime is None or activity_datetime > most_recent_datetime:
                most_recent = activity
                most_recent_datetime = activity_datetime

        if not most_recent:
            return None

        # Extract workout details
        activity_type_obj = most_recent.get("activityType", {})
        activity_type = activity_type_obj.get("typeKey", "unknown") if isinstance(activity_type_obj, dict) else "unknown"

        duration_seconds = most_recent.get("duration", 0)
        distance_meters = most_recent.get("distance")  # May be None for non-distance activities
        avg_hr = most_recent.get("averageHR")
        max_hr = most_recent.get("maxHR")
        aerobic_te = most_recent.get("aerobicTrainingEffect")
        anaerobic_te = most_recent.get("anaerobicTrainingEffect")
        activity_id = most_recent.get("activityId")

        # Calculate average pace (min/km) if distance available
        avg_pace = None
        if distance_meters and distance_meters > 0 and duration_seconds > 0:
            # Pace = duration_seconds / (distance_meters / 1000) = seconds per km
            # Convert to min/km
            avg_pace = (duration_seconds / (distance_meters / 1000)) / 60

        # Calculate hours since workout (using current datetime for accurate intra-day calculation)
        time_diff = current_datetime - most_recent_datetime
        hours_since = time_diff.total_seconds() / 3600

        # Fetch Phase 2 detailed metrics (cached only - no API call)
        detail_metrics = None
        if activity_id:
            detail_metrics = self._fetch_activity_detail_metrics(activity_id)

        return {
            "activity_type": activity_type,
            "date": most_recent_datetime.date(),  # Return date for compatibility
            "duration_seconds": duration_seconds,
            "distance_meters": distance_meters,
            "avg_hr": avg_hr,
            "max_hr": max_hr,
            "avg_pace": avg_pace,
            "aerobic_training_effect": aerobic_te,
            "anaerobic_training_effect": anaerobic_te,
            "hours_since_workout": hours_since,
            "activity_id": activity_id,
            "detail_metrics": detail_metrics,
        }

    def _compare_to_recent_similar_workouts(
        self, recent_activity: dict[str, Any], all_activities: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Compare recent workout to similar workouts from last 14 days.

        Args:
            recent_activity: Result from _analyze_most_recent_workout()
            all_activities: Full list of recent activities from Garmin

        Returns:
            Performance comparison metrics:
            {
                "avg_hr_baseline": float | None,
                "avg_pace_baseline": float | None (min/km),
                "avg_training_effect_baseline": float | None,
                "hr_deviation_bpm": float | None,
                "pace_deviation_pct": float | None,
                "trend": str ("improving" | "stable" | "declining" | None),
                "similar_workout_count": int
            }

        Configuration:
            similar_workout_lookback_days: Loaded from config (default: 14)
            min_similar_workouts: Loaded from config (default: 2)
        """
        if not recent_activity or not all_activities:
            return {
                "avg_hr_baseline": None,
                "avg_pace_baseline": None,
                "avg_training_effect_baseline": None,
                "hr_deviation_bpm": None,
                "pace_deviation_pct": None,
                "trend": None,
                "similar_workout_count": 0,
            }

        recent_type = recent_activity["activity_type"]
        recent_date = recent_activity["date"]
        cutoff_date = recent_date - timedelta(days=self.similar_workout_lookback_days)

        # Find similar workouts (same activity type, excluding the recent one)
        similar_workouts: list[dict[str, Any]] = []
        for activity in all_activities:
            if not isinstance(activity, dict) or "error" in activity:
                continue

            # Extract date
            start_time_local = activity.get("startTimeLocal")
            if not start_time_local:
                continue

            try:
                activity_date = date.fromisoformat(start_time_local[:10])
            except (ValueError, TypeError):
                continue

            # Skip if outside lookback window or is the recent activity
            if activity_date < cutoff_date or activity_date == recent_date:
                continue

            # Check activity type
            activity_type_obj = activity.get("activityType", {})
            activity_type = activity_type_obj.get("typeKey", "unknown") if isinstance(activity_type_obj, dict) else "unknown"

            if activity_type != recent_type:
                continue

            similar_workouts.append(activity)

        if len(similar_workouts) < self.min_similar_workouts:
            return {
                "avg_hr_baseline": None,
                "avg_pace_baseline": None,
                "avg_training_effect_baseline": None,
                "hr_deviation_bpm": None,
                "pace_deviation_pct": None,
                "trend": None,
                "similar_workout_count": len(similar_workouts),
            }

        # Calculate baselines from similar workouts
        hr_values: list[float] = []
        pace_values: list[float] = []
        te_values: list[float] = []

        for workout in similar_workouts:
            avg_hr = workout.get("averageHR")
            if avg_hr:
                hr_values.append(float(avg_hr))

            # Calculate pace if available
            duration = workout.get("duration", 0)
            distance = workout.get("distance")
            if distance and distance > 0 and duration > 0:
                pace_min_per_km = (duration / (distance / 1000)) / 60
                pace_values.append(pace_min_per_km)

            aerobic_te = workout.get("aerobicTrainingEffect")
            if aerobic_te:
                te_values.append(float(aerobic_te))

        # Calculate baseline averages
        avg_hr_baseline = sum(hr_values) / len(hr_values) if hr_values else None
        avg_pace_baseline = sum(pace_values) / len(pace_values) if pace_values else None
        avg_te_baseline = sum(te_values) / len(te_values) if te_values else None

        # Calculate deviations
        hr_deviation = None
        if avg_hr_baseline and recent_activity["avg_hr"]:
            hr_deviation = recent_activity["avg_hr"] - avg_hr_baseline

        pace_deviation_pct = None
        if avg_pace_baseline and recent_activity["avg_pace"]:
            # Negative deviation = faster pace (better performance)
            pace_deviation_pct = ((recent_activity["avg_pace"] - avg_pace_baseline) / avg_pace_baseline) * 100

        # Detect trend (improving/stable/declining)
        trend = None
        if hr_deviation is not None or pace_deviation_pct is not None:
            # Improving: HR lower OR pace faster
            # Declining: HR higher OR pace slower
            # Stable: within ±5%
            STABLE_THRESHOLD = 5.0

            if hr_deviation is not None and abs(hr_deviation) > STABLE_THRESHOLD:
                trend = "improving" if hr_deviation < 0 else "declining"
            elif pace_deviation_pct is not None and abs(pace_deviation_pct) > STABLE_THRESHOLD:
                trend = "improving" if pace_deviation_pct < 0 else "declining"
            else:
                trend = "stable"

        return {
            "avg_hr_baseline": avg_hr_baseline,
            "avg_pace_baseline": avg_pace_baseline,
            "avg_training_effect_baseline": avg_te_baseline,
            "hr_deviation_bpm": hr_deviation,
            "pace_deviation_pct": pace_deviation_pct,
            "trend": trend,
            "similar_workout_count": len(similar_workouts),
        }

    def _calculate_performance_condition(
        self, recent_workout: dict[str, Any], comparison: dict[str, Any]
    ) -> str:
        """Calculate performance condition based on HR and pace deviations.

        Args:
            recent_workout: Result from _analyze_most_recent_workout()
            comparison: Result from _compare_to_recent_similar_workouts()

        Returns:
            Performance condition verdict:
            - "Strong": HR lower OR pace faster (beyond threshold)
            - "Normal": Within threshold of baseline
            - "Fatigued": HR higher OR pace slower (beyond threshold)

        Configuration:
            hr_deviation_threshold: Loaded from config (default: 5 bpm)
            pace_deviation_threshold_pct: Loaded from config (default: 5%)
        """
        hr_deviation = comparison.get("hr_deviation_bpm")
        pace_deviation_pct = comparison.get("pace_deviation_pct")

        # Default to Normal if insufficient data
        if hr_deviation is None and pace_deviation_pct is None:
            return "Normal"

        # Check for strong performance (HR lower OR pace faster)
        if hr_deviation is not None and hr_deviation < -self.hr_deviation_threshold:
            return "Strong"
        if pace_deviation_pct is not None and pace_deviation_pct < -self.pace_deviation_threshold_pct:
            return "Strong"

        # Check for fatigue (HR higher OR pace slower)
        if hr_deviation is not None and hr_deviation > self.hr_deviation_threshold:
            return "Fatigued"
        if pace_deviation_pct is not None and pace_deviation_pct > self.pace_deviation_threshold_pct:
            return "Fatigued"

        # Within threshold = Normal
        return "Normal"

    def _fetch_activity_detail_metrics(self, activity_id: int) -> dict[str, Any] | None:
        """Fetch cached Phase 2 detailed activity metrics.

        This method retrieves detail metrics (pace consistency, HR drift, weather)
        from the database cache ONLY - no API calls are made.

        Args:
            activity_id: Garmin activity ID

        Returns:
            dict | None: Detail metrics dictionary with keys:
                - pace_consistency: float (0-100 score)
                - hr_drift: float (percentage)
                - weather: dict (temperature, humidity, conditions)
                - splits_summary: str (human-readable splits info)
            Returns None if no cached data or if fetch fails.
        """
        try:
            from app.database import SessionLocal
            from app.services.activity_detail_helper import ActivityDetailHelper

            # Use context manager to ensure proper session cleanup
            with contextlib.closing(SessionLocal()) as db:
                helper = ActivityDetailHelper()
                cached = helper.get_cached_detail(db, activity_id)

                if not cached:
                    logger.debug("No cached detail metrics for activity %d", activity_id)
                    return None

                # Build weather summary
                weather_summary = None
                if cached.weather_data:
                    weather = cached.weather_data
                    temp = weather.get("temp")
                    humidity = weather.get("relativeHumidity")
                    conditions = weather.get("weatherTypeDTO", {}).get("desc", "")

                    parts = []
                    if temp is not None:
                        parts.append(f"{temp}°C")
                    if humidity is not None:
                        parts.append(f"{humidity}% humidity")
                    if conditions:
                        parts.append(conditions)

                    if parts:
                        weather_summary = ", ".join(parts)

                # Build splits summary (simple version for now)
                splits_summary = None
                if cached.splits_data and "lapDTOs" in cached.splits_data:
                    laps = cached.splits_data["lapDTOs"]
                    if laps and len(laps) >= 2:
                        first_pace = None
                        last_pace = None

                        # First lap pace
                        first_lap = laps[0]
                        if first_lap.get("distance") and first_lap.get("duration"):
                            first_pace = (first_lap["duration"] / first_lap["distance"]) * 1000

                        # Last lap pace
                        last_lap = laps[-1]
                        if last_lap.get("distance") and last_lap.get("duration"):
                            last_pace = (last_lap["duration"] / last_lap["distance"]) * 1000

                        if first_pace and last_pace:
                            if last_pace > first_pace:
                                splits_summary = "Positive splits (slowing)"
                            elif last_pace < first_pace:
                                splits_summary = "Negative splits (getting faster)"
                            else:
                                splits_summary = "Even splits"

                return {
                    "pace_consistency": cached.pace_consistency_score,
                    "hr_drift": cached.hr_drift_percent,
                    "weather": weather_summary,
                    "splits_summary": splits_summary,
                }

        except Exception as e:
            logger.warning("Failed to fetch detail metrics for activity %d: %s", activity_id, e, exc_info=True)
            return None

    def _format_recent_workout_analysis(
        self,
        recent_workout: dict[str, Any],
        comparison: dict[str, Any],
        condition: str,
        detail_metrics: dict[str, Any] | None = None,
    ) -> str:
        """Format detailed workout summary for AI prompt.

        Args:
            recent_workout: Result from _analyze_most_recent_workout()
            comparison: Result from _compare_to_recent_similar_workouts()
            condition: Result from _calculate_performance_condition()
            detail_metrics: Optional Phase 2 detailed metrics (pace_consistency, hr_drift, weather)

        Returns:
            Multi-line formatted string with workout details, performance metrics, and condition
        """
        lines: list[str] = []

        # Header
        activity_type = recent_workout["activity_type"].replace("_", " ").title()
        date_str = recent_workout["date"].isoformat()
        hours_since = recent_workout["hours_since_workout"]

        if hours_since < 24:
            recency = f"{hours_since:.1f} hours ago"
        else:
            days = hours_since / 24
            recency = f"{days:.1f} days ago"

        lines.append(f"MOST RECENT WORKOUT: {activity_type} on {date_str} ({recency})")

        # Duration and distance
        duration_min = recent_workout["duration_seconds"] / 60
        lines.append(f"  Duration: {duration_min:.0f} minutes")

        if recent_workout["distance_meters"]:
            distance_km = recent_workout["distance_meters"] / 1000
            lines.append(f"  Distance: {distance_km:.2f} km")

        # Pace (if available)
        if recent_workout["avg_pace"]:
            pace_min = int(recent_workout["avg_pace"])
            pace_sec = int((recent_workout["avg_pace"] - pace_min) * 60)
            lines.append(f"  Pace: {pace_min}:{pace_sec:02d} min/km")

            # Show pace comparison if available
            if comparison["avg_pace_baseline"] and comparison["pace_deviation_pct"]:
                baseline_min = int(comparison["avg_pace_baseline"])
                baseline_sec = int((comparison["avg_pace_baseline"] - baseline_min) * 60)
                deviation = comparison["pace_deviation_pct"]
                if deviation < 0:
                    lines.append(f"    (FASTER by {abs(deviation):.1f}% vs baseline {baseline_min}:{baseline_sec:02d})")
                else:
                    lines.append(f"    (SLOWER by {deviation:.1f}% vs baseline {baseline_min}:{baseline_sec:02d})")

        # Heart rate
        if recent_workout["avg_hr"]:
            lines.append(f"  Average HR: {recent_workout['avg_hr']} bpm")

            # Show HR comparison if available
            if comparison["avg_hr_baseline"] and comparison["hr_deviation_bpm"]:
                baseline = comparison["avg_hr_baseline"]
                deviation = comparison["hr_deviation_bpm"]
                if deviation < 0:
                    lines.append(f"    (LOWER by {abs(deviation):.0f} bpm vs baseline {baseline:.0f})")
                else:
                    lines.append(f"    (HIGHER by {deviation:.0f} bpm vs baseline {baseline:.0f})")

        if recent_workout["max_hr"]:
            lines.append(f"  Max HR: {recent_workout['max_hr']} bpm")

        # Training effect
        if recent_workout["aerobic_training_effect"]:
            lines.append(f"  Aerobic Training Effect: {recent_workout['aerobic_training_effect']:.1f}")
        if recent_workout["anaerobic_training_effect"]:
            lines.append(f"  Anaerobic Training Effect: {recent_workout['anaerobic_training_effect']:.1f}")

        # Phase 2 detailed metrics (if available)
        if detail_metrics:
            lines.append("\nDETAILED PERFORMANCE BREAKDOWN:")

            # Pace consistency
            if detail_metrics.get("pace_consistency") is not None:
                score = detail_metrics["pace_consistency"]
                if score >= 90:
                    interpretation = "excellent pacing, minimal variation"
                elif score >= 70:
                    interpretation = "good pacing with some variation"
                elif score >= 50:
                    interpretation = "inconsistent pacing"
                else:
                    interpretation = "very inconsistent, possible mid-run struggles"

                lines.append(f"  - Pace consistency: {score:.0f}/100 ({interpretation})")

            # HR drift
            if detail_metrics.get("hr_drift") is not None:
                drift = detail_metrics["hr_drift"]
                if drift <= 3:
                    interpretation = "excellent efficiency, well-paced effort"
                elif drift <= 6:
                    interpretation = "normal cardiac drift for sustained efforts"
                elif drift <= 10:
                    interpretation = "moderate drift, possible heat stress or insufficient conditioning"
                else:
                    interpretation = "significant drift, indicates stress"

                lines.append(f"  - HR drift: +{drift:.1f}% ({interpretation})")

            # Weather
            if detail_metrics.get("weather"):
                lines.append(f"  - Weather: {detail_metrics['weather']}")

            # Splits summary
            if detail_metrics.get("splits_summary"):
                lines.append(f"  - Splits: {detail_metrics['splits_summary']}")

        # Performance condition verdict
        lines.append(f"\n  PERFORMANCE CONDITION: {condition}")

        # Trend if available
        if comparison["trend"]:
            trend = comparison["trend"].upper()
            lines.append(f"  TREND: {trend} (based on {comparison['similar_workout_count']} similar workouts)")

        return "\n".join(lines)

    def _calculate_baselines(self, data: dict[str, Any]) -> dict[str, Any]:
        """Calculate simple baselines from recent activity data with activity type breakdown.

        Args:
            data: Dictionary containing 'recent_activities' list from Garmin

        Returns:
            Dictionary with keys:
                - avg_training_load: Average training load across all activities
                - activity_count: Total number of activities in period
                - total_distance_km: Total distance covered (kilometers)
                - total_duration_min: Total duration (minutes)
                - activity_breakdown: Dict mapping activity type to stats:
                    {
                        "running": {
                            "count": 3,
                            "total_duration_min": 150.0,
                            "total_distance_km": 15.5,
                            "impact_level": "high",
                            "avg_hr": 145.0,
                            "total_training_effect": 12.5
                        },
                        ...
                    }

        Example:
            >>> data = {"recent_activities": [{"activityType": {"typeKey": "running"}, ...}]}
            >>> baselines = analyzer._calculate_baselines(data)
            >>> print(baselines["activity_breakdown"]["running"]["impact_level"])
            "high"
        """

        activities = data.get("recent_activities", [])

        if not activities or "error" in str(activities):
            return {
                "avg_training_load": 0,
                "activity_count": 0,
                "total_distance_km": 0,
                "total_duration_min": 0,
                "activity_breakdown": {},
            }

        # Calculate simple metrics from recent activities
        total_load = 0
        total_distance = 0
        total_duration = 0
        count = 0

        # Activity type breakdown structure
        activity_breakdown: dict[str, dict[str, Any]] = {}

        for activity in activities:
            if isinstance(activity, dict) and "error" not in activity:
                # Training load
                if "aerobicTrainingEffect" in activity:
                    total_load += activity.get("aerobicTrainingEffect", 0) * 10

                # Distance
                if "distance" in activity:
                    total_distance += activity.get("distance", 0) / 1000  # Convert to km

                # Duration
                if "duration" in activity:
                    total_duration += activity.get("duration", 0) / 60  # Convert to minutes

                count += 1

                # Extract activity type and classify impact
                activity_type = activity.get("activityType", {}).get("typeKey", "unknown")
                impact_level = self._classify_activity_impact(activity)

                # Aggregate by type
                if activity_type not in activity_breakdown:
                    activity_breakdown[activity_type] = {
                        "count": 0,
                        "total_duration_min": 0,
                        "total_distance_km": 0,
                        "impact_level": impact_level,
                        "avg_hr": None,
                        "total_training_effect": 0,
                    }

                breakdown = activity_breakdown[activity_type]
                breakdown["count"] += 1
                breakdown["total_duration_min"] += activity.get("duration", 0) / 60
                breakdown["total_distance_km"] += activity.get("distance", 0) / 1000
                breakdown["total_training_effect"] += activity.get("aerobicTrainingEffect", 0)

                # Track average HR if available
                avg_hr = activity.get("averageHR")
                if avg_hr:
                    if breakdown["avg_hr"] is None:
                        breakdown["avg_hr"] = avg_hr
                    else:
                        # Running average - protected against division by zero
                        current_count = breakdown["count"]
                        if current_count > 0:
                            breakdown["avg_hr"] = (breakdown["avg_hr"] * (current_count - 1) + avg_hr) / current_count

        # Division by zero protection
        avg_training_load = total_load / count if count > 0 else 0

        return {
            "avg_training_load": avg_training_load,
            "activity_count": count,
            "total_distance_km": round(total_distance, 1),
            "total_duration_min": round(total_duration, 0),
            "activity_breakdown": activity_breakdown,
        }

    def _classify_activity_impact(self, activity: dict[str, Any]) -> str:
        """Classify activity impact level based on type, intensity, and training effect.

        Combines multiple signals to determine the musculoskeletal and cardiovascular
        impact of an activity:
        - Activity type (e.g., running = high impact, swimming = low impact)
        - Training effect (aerobic + anaerobic, from Garmin)
        - Heart rate intensity (% of max HR)
        - Duration (long sessions increase impact)

        Args:
            activity: Garmin activity dictionary with fields:
                - activityType: {"typeKey": "running"}
                - aerobicTrainingEffect: float (0-5)
                - anaerobicTrainingEffect: float (0-5)
                - averageHR: int (bpm)
                - maxHR: int (bpm)
                - duration: int (seconds)

        Returns:
            Impact level: "high", "moderate", or "low"
            - "high": Running, intervals, plyometrics, or any activity with training effect >4.0
            - "moderate": Cycling, rowing, strength training
            - "low": Swimming, stretching, yoga

        Example:
            >>> activity = {
            ...     "activityType": {"typeKey": "running"},
            ...     "aerobicTrainingEffect": 3.2,
            ...     "averageHR": 155,
            ...     "maxHR": 180,
            ...     "duration": 2400
            ... }
            >>> impact = analyzer._classify_activity_impact(activity)
            >>> print(impact)
            "high"
        """
        # Input validation for malformed data
        if not isinstance(activity, dict):
            logger.warning(f"Invalid activity data type: {type(activity)}")
            return "moderate"

        activity_type_obj = activity.get("activityType")
        if not activity_type_obj or not isinstance(activity_type_obj, dict):
            logger.warning("Missing or invalid activityType field")
            return "moderate"

        activity_type = activity_type_obj.get("typeKey", "unknown").lower()
        training_effect = activity.get("aerobicTrainingEffect", 0)
        anaerobic_effect = activity.get("anaerobicTrainingEffect", 0)
        avg_hr = activity.get("averageHR")
        max_hr = activity.get("maxHR")
        duration_min = activity.get("duration", 0) / 60

        # High impact activities (plyometric, heavy muscular stress)
        high_impact_types = {
            "running", "trail_running", "track_running", "treadmill_running",
            "track_and_field", "cross_country_running", "speed_training",
            "hiit", "interval_training", "jump_rope", "plyometrics",
            "basketball", "tennis", "racquetball", "squash",
        }

        # Moderate impact activities (some muscular stress but lower impact)
        moderate_impact_types = {
            "hiking", "walking", "fitness_walking", "stair_climbing",
            "elliptical", "rowing", "indoor_rowing", "cycling", "mountain_biking",
            "gravel_cycling", "road_cycling", "virtual_cycling",
            "strength_training", "cardio_training", "crossfit",
            "pilates", "dance",
        }

        # Low impact activities (minimal joint stress)
        low_impact_types = {
            "swimming", "lap_swimming", "open_water_swimming",
            "stand_up_paddleboarding", "kayaking", "paddling",
            "stretching", "flexibility_training", "breathwork",
            "yoga",  # Yoga is low impact
        }

        # Classify by type first - using exact matching to avoid false positives
        if activity_type in high_impact_types:
            base_impact = "high"
        elif activity_type in moderate_impact_types:
            base_impact = "moderate"
        elif activity_type in low_impact_types:
            base_impact = "low"
        else:
            # Default to moderate for unknown types
            base_impact = "moderate"

        # Adjust based on training effect (overrides type if intensity is clear)
        total_effect = training_effect + anaerobic_effect
        if total_effect >= self.training_effect_very_high:
            return "high"  # Hard session regardless of type

        # Check HR intensity before mid-level training effect adjustments
        # This allows HR to override when training effect is ambiguous
        if avg_hr and max_hr:
            hr_pct = avg_hr / max_hr
            if hr_pct > self.hr_high_intensity:  # Zone 4-5
                return "high"

        # Continue with training effect adjustments
        if total_effect >= self.training_effect_moderate:
            # Keep base impact or upgrade if low
            return "high" if base_impact == "high" else "moderate"
        elif total_effect >= 1.0:
            # Downgrade if high, keep if moderate/low
            return "moderate" if base_impact == "high" else base_impact

        # Adjust based on duration (long duration = higher impact)
        if duration_min > self.duration_long_minutes:
            if base_impact == "low":
                return "moderate"
            return base_impact  # Keep high/moderate

        # Final HR check for zone 3-4
        if avg_hr and max_hr:
            hr_pct = avg_hr / max_hr
            if hr_pct > self.hr_zone_threshold:  # Zone 3-4
                return "high" if base_impact == "high" else "moderate"

        return base_impact

    def _format_metric(self, value: float, unit: str, decimals: int = 1) -> str:
        """Format a metric value with unit.

        Args:
            value: The numeric value to format
            unit: The unit string (e.g., 'km', 'min', 'bpm')
            decimals: Number of decimal places (default: 1)

        Returns:
            Formatted string like "10.5km" or "42min"
        """
        return f"{value:.{decimals}f}{unit}"

    def _format_activity_type_breakdown(self, breakdown: dict[str, dict[str, Any]]) -> str:
        """Format activity breakdown into human-readable summary for AI prompt.

        Groups activities by impact level (high/moderate/low) and formats them
        with detailed statistics for each activity type.

        Args:
            breakdown: Dict mapping activity type to statistics:
                {
                    "running": {
                        "count": 3,
                        "total_duration_min": 150.0,
                        "total_distance_km": 15.5,
                        "impact_level": "high",
                        "avg_hr": 145.0
                    }
                }

        Returns:
            Multi-line formatted string grouped by impact level:
                HIGH IMPACT:
                  - Running: 3x, 150min total, 15.5km, avg HR 145 bpm
                MODERATE IMPACT:
                  - Cycling: 2x, 120min total, 40.0km, avg HR 130 bpm
                LOW IMPACT:
                  - Swimming: 1x, 45min total

        Example:
            >>> breakdown = {
            ...     "running": {"count": 2, "total_duration_min": 60, "total_distance_km": 10,
            ...                 "impact_level": "high", "avg_hr": 150}
            ... }
            >>> print(analyzer._format_activity_type_breakdown(breakdown))
            HIGH IMPACT:
              - Running: 2x, 60min total, 10.0km, avg HR 150 bpm
        """
        if not breakdown:
            return "No recent activities synced"

        # Group by impact level
        high_impact: list[tuple[str, dict[str, Any]]] = []
        moderate_impact: list[tuple[str, dict[str, Any]]] = []
        low_impact: list[tuple[str, dict[str, Any]]] = []

        for activity_type, stats in breakdown.items():
            impact = stats.get("impact_level", "moderate")
            if impact == "high":
                high_impact.append((activity_type, stats))
            elif impact == "moderate":
                moderate_impact.append((activity_type, stats))
            else:
                low_impact.append((activity_type, stats))

        # Build formatted summary
        lines: list[str] = []

        # Helper to format a single activity group
        def format_group(label: str, activities: list[tuple[str, dict[str, Any]]]) -> None:
            """Format one impact group (high/moderate/low)."""
            if not activities:
                return
            lines.append(f"{label}:")
            for activity_type, stats in activities:
                type_display = activity_type.replace("_", " ").title()
                count = stats["count"]
                duration = stats["total_duration_min"]
                distance = stats["total_distance_km"]
                avg_hr = stats.get("avg_hr")

                detail = f"  - {type_display}: {count}x, {self._format_metric(duration, 'min', 0)} total"
                if distance > 0:
                    detail += f", {self._format_metric(distance, 'km', 1)}"
                if avg_hr:
                    detail += f", avg HR {self._format_metric(avg_hr, ' bpm', 0)}"
                lines.append(detail)

        # Format each impact group
        format_group("HIGH IMPACT", high_impact)
        format_group("MODERATE IMPACT", moderate_impact)
        format_group("LOW IMPACT", low_impact)

        return "\n".join(lines)

    def _has_historical_data(self, target_date: date) -> bool:
        """Check if we have historical data in database."""
        db = SessionLocal()
        try:
            # Check if we have at least 7 days of data before target date
            start_date = target_date - timedelta(days=7)
            count = (
                db.query(DailyMetric)
                .filter(
                    DailyMetric.date >= start_date,
                    DailyMetric.date <= target_date,
                )
                .count()
            )
            return count >= 5  # Need at least 5 days of data
        finally:
            db.close()

    def _get_historical_baselines(self, target_date: date) -> dict[str, Any] | None:
        """Fetch 30-day baseline metrics if enough history exists."""
        if not self._has_historical_data(target_date):
            return None

        db = SessionLocal()
        try:
            processor = DataProcessor(db)
            return processor.get_all_baselines(target_date)
        finally:
            db.close()

    def _get_readiness_history(self, target_date: date, days: int = 7) -> list[dict[str, Any]]:
        """Return recent readiness scores for sparkline and context."""
        db = SessionLocal()
        try:
            metrics = (
                db.query(DailyMetric)
                .filter(DailyMetric.date <= target_date)
                .order_by(DailyMetric.date.desc())
                .limit(days)
                .all()
            )

            history: list[dict[str, Any]] = []
            for metric in reversed(metrics):
                if metric.training_readiness_score is None:
                    continue
                history.append(
                    {
                        "date": metric.date.isoformat(),
                        "score": metric.training_readiness_score,
                    }
                )
            return history
        finally:
            db.close()

    def _get_latest_metric_sync(self) -> str | None:
        """Return the most recent updated_at timestamp for daily metrics."""
        db = SessionLocal()
        try:
            metric = (
                db.query(DailyMetric)
                .order_by(DailyMetric.updated_at.desc())
                .first()
            )
            if metric and metric.updated_at:
                # Ensure ISO8601 string for JSON clients
                return metric.updated_at.replace(microsecond=0).isoformat() + "Z"
            return None
        finally:
            db.close()

    def _calculate_hr_zones(
        self,
        personal_info: dict[str, Any],
    ) -> dict[str, dict[str, int | str]] | None:
        """
        Calculate HR zones from personal information.

        Args:
            personal_info: Dictionary from GarminService.get_personal_info()

        Returns:
            HR zones dict or None if calculation fails
        """
        try:
            lactate_threshold_hr = personal_info.get("lactate_threshold_hr")
            max_hr = personal_info.get("max_hr")
            age = personal_info.get("age")

            # Skip if we have no data at all
            if lactate_threshold_hr is None and max_hr is None and age is None:
                logger.warning("No personal info available for HR zone calculation")
                return None

            zones = calculate_hr_zones(
                lactate_threshold_hr=lactate_threshold_hr,
                max_hr=max_hr,
                age=age,
            )

            return zones

        except Exception as err:
            logger.exception("Failed to calculate HR zones: %s", err)
            return None

    def _build_prompt(
        self,
        target_date: date,
        data: dict[str, Any],
        baselines: dict[str, Any],
        historical_baselines: dict[str, Any] | None,
        hr_zones: dict[str, dict[str, int | str]] | None = None,
        locale: str | None = None,
        alerts: list[dict[str, Any]] | None = None,
    ) -> tuple[str, str, str | None, dict[str, Any]]:
        """Build comprehensive prompt for Claude AI."""

        settings = get_settings()
        prompt_config = self._load_prompt_config(settings.prompt_config_path)
        template = self._load_template(prompt_config["prompt_path"])
        hist_template = self._load_template(prompt_config["historical_context_path"])
        translations = prompt_config.get("translations", {})
        default_language = str(prompt_config.get("default_language", "en")).lower()
        language = self._resolve_language(locale, translations, default_language)
        thresholds = prompt_config["thresholds"]
        readiness_thresholds = thresholds["readiness"]

        stats = data.get("stats", {})
        sleep_data = data.get("sleep", {})
        hrv_data = data.get("hrv", {})
        hr_data = data.get("heart_rate", {})
        stress_data = data.get("stress", {})
        body_battery_data = data.get("body_battery", {})

        # Format sleep info
        sleep_info = "No sleep data available"
        if sleep_data and "dailySleepDTO" in sleep_data:
            sleep_dto = sleep_data["dailySleepDTO"]
            sleep_seconds = sleep_dto.get("sleepTimeSeconds", 0)
            sleep_hours = sleep_seconds / 3600
            sleep_score = sleep_dto.get("sleepScores", {}).get("overall", {}).get("value", "N/A")
            sleep_info = f"{sleep_hours:.1f} hours, quality score: {sleep_score}"

        # Format HRV info
        hrv_info = "No HRV data available"
        if hrv_data and "hrvSummary" in hrv_data:
            hrv_summary = hrv_data["hrvSummary"]
            last_night_avg = hrv_summary.get("lastNightAvg")
            weekly_avg = hrv_summary.get("weeklyAvg")
            if last_night_avg:
                hrv_info = f"Last night: {last_night_avg}ms"
                if weekly_avg:
                    hrv_info += f", 7-day avg: {weekly_avg}ms"

        # Format HR info
        hr_info = "No heart rate data available"
        if hr_data and "restingHeartRate" in hr_data:
            resting_hr = hr_data.get("restingHeartRate")
            max_hr = hr_data.get("maxHeartRate")
            hr_info = f"Resting: {resting_hr} bpm"
            if max_hr:
                hr_info += f", Max: {max_hr} bpm"

        # Format stress info
        stress_info = "No stress data available"
        if stress_data and isinstance(stress_data, list) and stress_data:
            stress_values = [s.get("stressLevel", 0) for s in stress_data if isinstance(s, dict)]
            if stress_values:
                avg_stress = sum(stress_values) / len(stress_values)
                stress_info = f"Average: {avg_stress:.0f}/100"

        # Format body battery info
        bb_info = "No body battery data available"
        if body_battery_data and isinstance(body_battery_data, list) and body_battery_data:
            latest_bb = body_battery_data[-1] if body_battery_data else {}
            if "charged" in latest_bb or "drained" in latest_bb:
                charged = latest_bb.get("charged", 0)
                drained = latest_bb.get("drained", 0)
                bb_info = f"Charged: +{charged}, Drained: -{drained}"

        training_readiness_data = data.get("training_readiness", {})
        training_status_data = data.get("training_status", {})
        spo2_data = data.get("spo2", {})
        respiration_data = data.get("respiration", {})

        garmin_readiness_info = "Not available"
        if training_readiness_data and isinstance(training_readiness_data, list) and len(training_readiness_data) > 0:
            if isinstance(training_readiness_data[0], dict):
                readiness_score = training_readiness_data[0].get("score")
                if readiness_score is not None:
                    garmin_readiness_info = f"{readiness_score}/100"
        elif training_readiness_data and isinstance(training_readiness_data, dict):
            readiness_score = training_readiness_data.get("score")
            if readiness_score is not None:
                garmin_readiness_info = f"{readiness_score}/100"

        vo2_max_info = "Not available"
        training_status_info = "Not available"
        if training_status_data and isinstance(training_status_data, dict):
            if "mostRecentVO2Max" in training_status_data:
                vo2_data = training_status_data.get("mostRecentVO2Max")
                if vo2_data and isinstance(vo2_data, dict):
                    generic = vo2_data.get("generic")
                    if generic and isinstance(generic, dict):
                        vo2_max = generic.get("vo2MaxValue")
                        if vo2_max:
                            vo2_max_info = f"{vo2_max} ml/kg/min"

            if "mostRecentTrainingStatus" in training_status_data:
                status_data = training_status_data.get("mostRecentTrainingStatus")
                if status_data and isinstance(status_data, dict):
                    latest = status_data.get("latestTrainingStatusData")
                    if latest and isinstance(latest, dict):
                        for _, device_data in latest.items():
                            if device_data and isinstance(device_data, dict):
                                training_status_info = device_data.get("trainingStatusFeedbackPhrase") or "Not available"
                                break

        spo2_info = "Not available"
        if spo2_data and isinstance(spo2_data, dict):
            avg_spo2 = spo2_data.get("avgSleepSpO2")
            min_spo2 = spo2_data.get("lowestSpO2")
            if avg_spo2 is not None:
                spo2_info = f"Average: {avg_spo2}%"
                if min_spo2 is not None:
                    spo2_info += f", Minimum: {min_spo2}%"

        respiration_info = "Not available"
        if respiration_data and isinstance(respiration_data, dict):
            avg_resp = respiration_data.get("avgSleepRespirationValue")
            if avg_resp is not None:
                respiration_info = f"{avg_resp} breaths/min"

        extended_signals_for_prompt = self._build_extended_signals(
            training_status_data,
            training_readiness_data,
        )
        recovery_time_info = self._format_recovery_for_prompt(
            extended_signals_for_prompt.get("recovery_time")
        )
        load_focus_info = self._format_load_focus_for_prompt(
            extended_signals_for_prompt.get("load_focus")
        )
        acclimation_info = self._format_acclimation_for_prompt(
            extended_signals_for_prompt.get("acclimation")
        )

        # Format HR zones for prompt
        hr_zones_info = "Not available"
        if hr_zones is not None:
            hr_zones_info = format_hr_zones_for_prompt(hr_zones)
            logger.debug("HR zones calculated and formatted for prompt")

        activity_summary = ""
        if isinstance(baselines, dict) and baselines:
            activity_count = baselines.get("activity_count", 0)
            total_distance = baselines.get("total_distance_km", 0)
            total_duration = baselines.get("total_duration_min", 0)
            activity_breakdown = baselines.get("activity_breakdown", {})

            if activity_count:
                # Use enhanced activity type breakdown if available
                if activity_breakdown:
                    breakdown_text = self._format_activity_type_breakdown(activity_breakdown)
                    activity_summary = (
                        f"{activity_count} activities in last 7 days, "
                        f"{total_distance}km total, "
                        f"{total_duration:.0f} min total\n\n"
                        f"ACTIVITY TYPE BREAKDOWN:\n{breakdown_text}"
                    )
                else:
                    # Fallback to simple summary
                    activity_summary = (
                        f"{activity_count} activities in last 7 days, "
                        f"{total_distance}km total, "
                        f"{total_duration:.0f} min total"
                    )
            else:
                activity_summary = "No recent activities synced"

        # Format recent workout details (Phase 1 - Individual Session Performance)
        recent_workout_details = data.get("recent_workout_analysis")
        if not recent_workout_details:
            recent_workout_details = "No recent workouts in last 72 hours"

        historical_context = ""
        if historical_baselines:
            hrv_baseline = historical_baselines.get("hrv", {})
            rhr_baseline = historical_baselines.get("resting_hr", {})
            sleep_baseline = historical_baselines.get("sleep", {})
            acwr = historical_baselines.get("acwr", {})
            trends = historical_baselines.get("training_trends", {})

            acwr_warning = "Insufficient data"
            acwr_ratio = None
            if acwr and isinstance(acwr, dict):
                acwr_ratio = acwr.get("acwr")
                if acwr_ratio is not None:
                    if acwr_ratio > thresholds["acwr_high"]:
                        acwr_warning = f"ACWR >{thresholds['acwr_high']} indicates HIGH INJURY RISK"
                    elif acwr_ratio > thresholds["acwr_moderate"]:
                        acwr_warning = "ACWR approaching risk zone"
                    else:
                        acwr_warning = "ACWR in safe zone"

            historical_context = hist_template.format(
                hrv_current=hrv_baseline.get("current_hrv", "N/A"),
                hrv_baseline=hrv_baseline.get("baseline_hrv", "N/A"),
                hrv_avg_7=hrv_baseline.get("7_day_avg", "N/A"),
                hrv_deviation=hrv_baseline.get("deviation_pct", "N/A"),
                hrv_trend=hrv_baseline.get("trend", "unknown"),
                hrv_flag="YES - HRV significantly below baseline" if hrv_baseline.get("is_concerning") else "No",
                rhr_current=rhr_baseline.get("current_rhr", "N/A"),
                rhr_baseline=rhr_baseline.get("baseline_rhr", "N/A"),
                rhr_deviation=rhr_baseline.get("deviation_bpm", "N/A"),
                rhr_flag="YES - possible illness or fatigue" if rhr_baseline.get("is_elevated") else "No",
                sleep_current=sleep_baseline.get("current_hours", "N/A"),
                sleep_baseline=sleep_baseline.get("baseline_hours", "N/A"),
                sleep_avg_7=sleep_baseline.get("7_day_avg", "N/A"),
                sleep_debt=sleep_baseline.get("sleep_debt_hours", "N/A"),
                sleep_flag="YES - insufficient sleep" if sleep_baseline.get("is_sleep_deprived") else "No",
                acwr_acute=acwr.get("acute_load", "N/A"),
                acwr_chronic=acwr.get("chronic_load", "N/A"),
                acwr_ratio=acwr.get("acwr", "N/A"),
                acwr_status=acwr.get("status", "unknown"),
                acwr_risk=acwr.get("injury_risk", "unknown").upper(),
                weekly_load_increase=historical_baselines.get("weekly_load_increase_pct", "N/A"),
                acwr_warning=acwr_warning,
                trends_total=trends.get("total_activities", 0),
                trends_distance=trends.get("total_distance_km", 0),
                trends_weekly_distance=trends.get("avg_weekly_distance", 0),
                trends_consecutive=trends.get("consecutive_training_days", 0),
                trends_rest_flag="YES - overtraining risk!" if trends.get("consecutive_training_days", 0) >= thresholds["no_rest_days"] else "No",
                hrv_drop_threshold=thresholds["hrv_drop_pct"],
                resting_hr_elevated_threshold=thresholds["resting_hr_elevated_bpm"],
                acwr_moderate_threshold=thresholds["acwr_moderate"],
                acwr_high_threshold=thresholds["acwr_high"],
                no_rest_days_threshold=thresholds["no_rest_days"],
            )

        # Format active alerts for prompt
        alerts_info = "No active training alerts"
        if alerts:
            alert_lines = []
            for alert in alerts:
                severity = alert.get("severity", "warning").upper()
                alert_type = alert.get("alert_type", "unknown")
                message = alert.get("message", "")
                triggers = alert.get("triggers", [])

                alert_text = f"🚨 [{severity}] {alert_type.replace('_', ' ').title()}: {message}"
                if triggers:
                    alert_text += f"\n   Triggers: {', '.join(triggers)}"
                alert_lines.append(alert_text)

            alerts_info = "\n".join(alert_lines)

        prompt = template.format(
            today=target_date.isoformat(),
            sleep_info=sleep_info,
            hrv_info=hrv_info,
            hr_info=hr_info,
            stress_info=stress_info,
            body_battery_info=bb_info,
            daily_steps=stats.get("totalSteps", "N/A"),
            active_calories=stats.get("activeKilocalories", "N/A"),
            training_readiness_info=garmin_readiness_info,
            vo2_max_info=vo2_max_info,
            training_status_info=training_status_info,
            spo2_info=spo2_info,
            respiration_info=respiration_info,
            hr_zones_info=hr_zones_info,
            historical_context=historical_context,
            activity_summary=activity_summary,
            recent_workout_details=recent_workout_details,
            recovery_time_info=recovery_time_info,
            alerts_info=alerts_info,
            load_focus_info=load_focus_info,
            acclimation_info=acclimation_info,
            hrv_drop_threshold=thresholds["hrv_drop_pct"],
            resting_hr_elevated_threshold=thresholds["resting_hr_elevated_bpm"],
            sleep_hours_threshold=thresholds["sleep_hours_min"],
            acwr_moderate_threshold=thresholds["acwr_moderate"],
            acwr_high_threshold=thresholds["acwr_high"],
            no_rest_days_threshold=thresholds["no_rest_days"],
            readiness_critical=readiness_thresholds["critical"],
            readiness_poor=readiness_thresholds["poor"],
            readiness_moderate_low=readiness_thresholds["moderate_low"],
            readiness_good=readiness_thresholds.get("good", 90),
            readiness_moderate=readiness_thresholds["moderate"],
        )

        language_entry = translations.get(language, {})
        instruction_text = language_entry.get("instruction")
        system_prompt = instruction_text
        if instruction_text:
            prompt = f"{prompt}\n\nLANGUAGE DIRECTIVE:\n{instruction_text}"

        return language, prompt, system_prompt, extended_signals_for_prompt

    @staticmethod
    def _load_template(path: str | Path) -> str:
        with Path(path).open("r", encoding="utf-8") as fh:
            return fh.read()

    @staticmethod
    def _load_prompt_config(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)

    @staticmethod
    def _resolve_language(
        locale: str | None,
        translations: dict[str, Any],
        default_language: str,
    ) -> str:
        """Normalize requested locale to a supported translation key."""

        if locale:
            normalized = locale.strip().lower().replace("_", "-")
            candidates = [normalized]
            if "-" in normalized:
                candidates.append(normalized.split("-")[0])
            for candidate in candidates:
                if candidate in translations:
                    return candidate

        if default_language in translations:
            return default_language

        if "en" in translations:
            return "en"

        if translations:
            return next(iter(translations))

        return default_language

    def _build_extended_signals(
        self,
        training_status: dict[str, Any] | list | None,
        training_readiness: Any,
    ) -> dict[str, Any]:
        signals: dict[str, Any] = {}

        recovery = self._parse_recovery_time(training_status, training_readiness)
        if recovery:
            signals["recovery_time"] = recovery

        load_focus = self._parse_load_focus(training_status)
        if load_focus:
            signals["load_focus"] = load_focus

        acclimation = self._parse_acclimation(training_status)
        if acclimation:
            signals["acclimation"] = acclimation

        return signals

    def _parse_recovery_time(self, training_status: Any, training_readiness: Any) -> dict[str, Any] | None:
        candidate_values: list[tuple[Any, str | None]] = []

        if isinstance(training_status, dict):
            for key in (
                "currentRecoveryTime",
                "recoveryTime",
                "currentRecoveryTimeInHours",
                "currentRecoveryTimeInMinutes",
                "recoveryTimeInHours",
                "recoveryTimeInMinutes",
                "currentTrainingStatus",
                "currentTrainingStatusData",
            ):
                value = training_status.get(key)
                if value is not None:
                    hint = "minutes" if "minute" in key.lower() else "hours" if "hour" in key.lower() else None
                    candidate_values.append((value, hint))

        # Garmin sometimes nests recovery time under `currentTrainingStatus` dict
        if isinstance(training_status, dict):
            nested = training_status.get("currentTrainingStatus")
            if isinstance(nested, dict):
                for sub_key, sub_val in nested.items():
                    hint = "minutes" if isinstance(sub_key, str) and "minute" in sub_key.lower() else "hours" if isinstance(sub_key, str) and "hour" in sub_key.lower() else None
                    candidate_values.append((sub_val, hint))

        # Training readiness payload often includes recommended recovery time
        if isinstance(training_readiness, list):
            for item in training_readiness:
                if isinstance(item, dict):
                    for key in (
                        "recoveryTime",  # Actual Garmin API key (in minutes)
                        "recommendedRecoveryTimeInHours",
                        "recommendedRecoveryTimeInMinutes",
                        "recoveryTimeInHours",
                        "recoveryTimeInMinutes",
                    ):
                        value = item.get(key)
                        if value is not None:
                            hint = "minutes" if ("minute" in key.lower() or key == "recoveryTime") else "hours" if "hour" in key.lower() else None
                            candidate_values.append((value, hint))
        elif isinstance(training_readiness, dict):
            for key in (
                "recoveryTime",  # Actual Garmin API key (in minutes)
                "recommendedRecoveryTimeInHours",
                "recommendedRecoveryTimeInMinutes",
                "recoveryTimeInHours",
                "recoveryTimeInMinutes",
            ):
                value = training_readiness.get(key)
                if value is not None:
                    hint = "minutes" if ("minute" in key.lower() or key == "recoveryTime") else "hours" if "hour" in key.lower() else None
                    candidate_values.append((value, hint))

        hours = None
        for value, hint in candidate_values:
            extracted = self._extract_recovery_hours(value, hint)
            if extracted is not None:
                hours = round(float(extracted), 2)
                break

        note = None
        if isinstance(training_status, dict):
            for key, value in training_status.items():
                if isinstance(value, str) and "recovery" in key.lower():
                    note = value
                    break
        if note is None and isinstance(training_readiness, list):
            for item in training_readiness:
                if isinstance(item, dict):
                    text = item.get("recommendationRecoveryTimeDescription") or item.get("recoveryRecommendation")
                    if isinstance(text, str):
                        note = text
                        break

        if hours is None and note is None:
            return None

        return {"hours": hours, "note": note}

    def _extract_recovery_hours(self, value: Any, hint: str | None = None) -> float | None:
        if isinstance(value, (int, float)):
            hours = float(value)
            if hint == "minutes":
                hours /= 60.0
            return hours
        if isinstance(value, str):
            stripped = value.strip().upper()
            if stripped.endswith("MINUTES"):
                try:
                    return float(stripped[:-7]) / 60.0
                except ValueError:
                    return None
            if stripped.endswith("MINS"):
                try:
                    return float(stripped[:-4]) / 60.0
                except ValueError:
                    return None
            if stripped.endswith("MIN"):
                try:
                    return float(stripped[:-3]) / 60.0
                except ValueError:
                    return None
            if stripped.endswith("M") and not stripped.endswith("MM"):
                try:
                    return float(stripped[:-1]) / 60.0
                except ValueError:
                    return None
        if isinstance(value, dict):
            for key in ("hours", "value", "quantity", "duration"):
                if key in value:
                    child_hint = "minutes" if "minute" in key.lower() else "hours" if "hour" in key.lower() else hint
                    extracted = self._extract_recovery_hours(value[key], child_hint)
                    if extracted is not None:
                        return extracted
        result = self._extract_numeric(value)
        if result is None:
            return None
        if isinstance(value, dict):
            for minute_key in ("minutes", "mins", "durationminutes"):
                if minute_key in value:
                    return result / 60.0
        if hint == "minutes":
            return result / 60.0
        return result

    def _parse_load_focus(self, training_status: Any) -> list[dict[str, Any]] | None:
        focus_entries = None
        if isinstance(training_status, dict):
            focus_entries = training_status.get("loadFocus")
            if focus_entries is None:
                focus_entries = training_status.get("trainingLoadFocus")

        if not isinstance(focus_entries, list) or not focus_entries:
            return None

        parsed: list[dict[str, Any]] = []
        for entry in focus_entries:
            if not isinstance(entry, dict):
                continue
            focus_type = (
                entry.get("focus")
                if entry.get("focus") is not None
                else entry.get("name")
                if entry.get("name") is not None
                else entry.get("label")
            )
            load_value = entry.get("load")
            if load_value is None:
                load_value = entry.get("value")
            load_value = self._extract_numeric(load_value)
            optimal_low = entry.get("optimalRangeLow")
            if optimal_low is None:
                optimal_low = entry.get("rangeLow")
            optimal_low = self._extract_numeric(optimal_low)
            optimal_high = entry.get("optimalRangeHigh")
            if optimal_high is None:
                optimal_high = entry.get("rangeHigh")
            optimal_high = self._extract_numeric(optimal_high)
            status = entry.get("status")
            if status is None:
                status = entry.get("state")
            if focus_type is None and load_value is None:
                continue
            parsed.append(
                {
                    "focus": focus_type,
                    "load": load_value,
                    "optimal_low": optimal_low,
                    "optimal_high": optimal_high,
                    "status": status,
                }
            )

        return parsed or None

    def _parse_acclimation(self, training_status: Any) -> dict[str, Any] | None:
        if not isinstance(training_status, dict):
            return None

        acclimation = training_status.get("heatAndAltitudeStatus")
        if acclimation is None:
            acclimation = training_status.get("heatAndAltitudeAcclimation")
        if acclimation is None:
            acclimation = training_status.get("acclimationStatus")

        if isinstance(acclimation, dict):
            heat_raw = acclimation.get("heatAcclimationValue")
            if heat_raw is None:
                heat_raw = acclimation.get("heatAcclimation")
            if heat_raw is None:
                heat_raw = acclimation.get("heat")
            heat = self._extract_numeric(heat_raw)

            altitude_raw = acclimation.get("altitudeAcclimationValue")
            if altitude_raw is None:
                altitude_raw = acclimation.get("altitudeAcclimation")
            if altitude_raw is None:
                altitude_raw = acclimation.get("altitude")
            altitude = self._extract_numeric(altitude_raw)

            status = acclimation.get("status")
            if status is None:
                status = acclimation.get("summary")
            return {
                "heat": heat,
                "altitude": altitude,
                "status": status,
            }

        return None

    def _format_recovery_for_prompt(self, recovery: dict[str, Any] | None) -> str:
        if not recovery:
            return "Not available"

        parts: list[str] = []
        hours = recovery.get("hours")
        note = recovery.get("note")
        if isinstance(hours, (int, float)):
            if hours <= 0.5:
                parts.append("Ready now")
            else:
                parts.append(f"{hours:.1f}h remaining")
        if isinstance(note, str) and note.strip():
            parts.append(note.strip())

        return " / ".join(parts) if parts else "Not available"

    def _format_load_focus_for_prompt(self, load_focus: list[dict[str, Any]] | None) -> str:
        if not load_focus:
            return "Not available"

        fragments: list[str] = []
        for entry in load_focus[:3]:
            focus = self._humanize_label(entry.get("focus"))
            load = entry.get("load")
            low = entry.get("optimal_low")
            high = entry.get("optimal_high")
            status = entry.get("status")

            if isinstance(load, (int, float)):
                fragment = f"{focus}: {load:.0f}"
                if isinstance(low, (int, float)) and isinstance(high, (int, float)):
                    fragment += f" (opt {low:.0f}-{high:.0f})"
            else:
                fragment = focus or "Focus"

            if isinstance(status, str) and status.strip():
                fragment += f" [{self._humanize_label(status)}]"

            fragments.append(fragment)

        return "; ".join(fragments) if fragments else "Not available"

    def _format_acclimation_for_prompt(self, acclimation: dict[str, Any] | None) -> str:
        if not acclimation:
            return "Not available"

        heat = acclimation.get("heat")
        altitude = acclimation.get("altitude")
        status = acclimation.get("status")

        parts: list[str] = []
        if isinstance(heat, (int, float)):
            parts.append(f"heat {heat:.0f}%")
        if isinstance(altitude, (int, float)):
            parts.append(f"altitude {altitude:.0f}%")
        if isinstance(status, str) and status.strip():
            parts.append(status.strip())

        return " | ".join(parts) if parts else "Not available"

    @staticmethod
    def _humanize_label(value: Any) -> str:
        if value is None:
            return ""
        return str(value).replace("_", " ").title()

    def _extract_numeric(self, value: Any) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, dict):
            for key in ("hours", "value", "current", "duration", "quantity", "sum"):
                if key in value:
                    extracted = self._extract_numeric(value[key])
                    if extracted is not None:
                        return extracted
        if isinstance(value, str):
            stripped = value.strip()
            upper = stripped.upper()
            if upper.startswith("PT"):
                # ISO-8601 duration, extract hours/minutes
                hours_val = 0.0
                num = ""
                for char in upper[2:]:
                    if char.isdigit() or char == '.':
                        num += char
                        continue
                    if char == 'H' and num:
                        hours_val += float(num)
                        num = ""
                    elif char == 'M' and num:
                        hours_val += float(num) / 60.0
                        num = ""
                    elif char == 'S' and num:
                        hours_val += float(num) / 3600.0
                        num = ""
                if hours_val > 0:
                    return hours_val
            if stripped.endswith("MIN") and stripped[:-3].replace('.', '', 1).isdigit():
                try:
                    return float(stripped[:-3]) / 60.0
                except ValueError:
                    return None
            if stripped.endswith("h") and stripped[:-1].replace(".", "", 1).isdigit():
                try:
                    return float(stripped[:-1])
                except ValueError:
                    return None
            if stripped.endswith("min") and stripped[:-3].replace(".", "", 1).isdigit():
                try:
                    return float(stripped[:-3]) / 60.0
                except ValueError:
                    return None
            if stripped.endswith("m") and stripped[:-1].replace(".", "", 1).isdigit():
                try:
                    return float(stripped[:-1]) / 60.0
                except ValueError:
                    return None
            try:
                return float(stripped)
            except ValueError:
                return None
        return None

    def _parse_response(self, response_text: str) -> dict[str, Any]:
        """Parse Claude's JSON response into structured format."""

        try:
            # Try to extract JSON from response
            # Look for JSON object in the response
            start = response_text.find("{")
            end = response_text.rfind("}") + 1

            if start >= 0 and end > start:
                json_str = response_text[start:end]
                result = json.loads(json_str)
                return result
            else:
                # Fallback if no JSON found
                return {
                    "readiness_score": 50,
                    "recommendation": "moderate",
                    "confidence": "low",
                    "key_factors": ["Unable to parse AI response"],
                    "red_flags": [],
                    "suggested_workout": {
                        "type": "easy_run",
                        "description": "30-40 min easy run",
                        "target_duration_minutes": 35,
                        "intensity": 3,
                        "rationale": "Default recommendation"
                    },
                    "recovery_tips": ["Stay hydrated", "Get adequate sleep"],
                    "ai_reasoning": "Fallback response due to parsing error",
                    "raw_response": response_text
                }
        except json.JSONDecodeError:
            # Return safe fallback
            return {
                "readiness_score": 50,
                "recommendation": "moderate",
                "confidence": "low",
                "key_factors": ["JSON parsing error"],
                "red_flags": [],
                "suggested_workout": {
                    "type": "easy_run",
                    "description": "30-40 min easy run",
                    "target_duration_minutes": 35,
                    "intensity": 3,
                    "rationale": "Default recommendation"
                },
                "recovery_tips": ["Stay hydrated", "Get adequate sleep"],
                "ai_reasoning": "Fallback response",
                "raw_response": response_text
            }
