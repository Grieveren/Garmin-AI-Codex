"""Claude AI-powered training readiness analysis."""
from __future__ import annotations

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

        # Check cache (thread-safe)
        with self._cache_lock:
            if (self._personal_info_cache is not None
                and self._personal_info_expires_at is not None
                and now < self._personal_info_expires_at):
                logger.debug("Using cached personal info")
                return self._personal_info_cache

        # Fetch fresh data (outside lock to avoid blocking)
        logger.debug("Fetching fresh personal info from Garmin")
        personal_info = garmin.get_personal_info()

        # Cache if successful (no error key)
        if personal_info.get("error") is None:
            with self._cache_lock:
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

        # Build comprehensive prompt with HR zones
        language, prompt, system_prompt, extended_signals = self._build_prompt(
            target_date,
            data,
            baselines,
            historical_baselines,
            hr_zones=hr_zones,
            locale=locale,
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

        try:
            hydration = garmin._client.get_hydration_data(date_str)
        except Exception:
            hydration = {}

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
            "hydration": hydration,
            "recent_activities": activities[:7],  # Last 7 days
        }

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
            data.get("hydration", {}),
            training_readiness_data,
        )
        recovery_time_info = self._format_recovery_for_prompt(
            extended_signals_for_prompt.get("recovery_time")
        )
        load_focus_info = self._format_load_focus_for_prompt(
            extended_signals_for_prompt.get("load_focus")
        )
        hydration_info = self._format_hydration_for_prompt(
            extended_signals_for_prompt.get("hydration")
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
            recovery_time_info=recovery_time_info,
            load_focus_info=load_focus_info,
            hydration_info=hydration_info,
            acclimation_info=acclimation_info,
            hrv_drop_threshold=thresholds["hrv_drop_pct"],
            resting_hr_elevated_threshold=thresholds["resting_hr_elevated_bpm"],
            sleep_hours_threshold=thresholds["sleep_hours_min"],
            acwr_moderate_threshold=thresholds["acwr_moderate"],
            acwr_high_threshold=thresholds["acwr_high"],
            no_rest_days_threshold=thresholds["no_rest_days"],
            readiness_critical=readiness_thresholds["critical"],
            readiness_poor=readiness_thresholds["poor"],
            readiness_low=readiness_thresholds["low"],
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
        hydration: dict[str, Any] | None,
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

        hydration_summary = self._parse_hydration(hydration)
        if hydration_summary:
            signals["hydration"] = hydration_summary

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
                        "recommendedRecoveryTimeInHours",
                        "recommendedRecoveryTimeInMinutes",
                        "recoveryTimeInHours",
                        "recoveryTimeInMinutes",
                    ):
                        value = item.get(key)
                        if value is not None:
                            hint = "minutes" if "minute" in key.lower() else "hours" if "hour" in key.lower() else None
                            candidate_values.append((value, hint))
        elif isinstance(training_readiness, dict):
            for key in (
                "recommendedRecoveryTimeInHours",
                "recommendedRecoveryTimeInMinutes",
                "recoveryTimeInHours",
                "recoveryTimeInMinutes",
            ):
                value = training_readiness.get(key)
                if value is not None:
                    hint = "minutes" if "minute" in key.lower() else "hours" if "hour" in key.lower() else None
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

    def _parse_hydration(self, hydration: Any) -> dict[str, Any] | None:
        if not isinstance(hydration, dict):
            return None

        summary = hydration.get("summary")
        if not isinstance(summary, dict):
            summary = hydration

        intake = None
        goal = None
        sweat = None

        for key, value in summary.items():
            if not isinstance(value, (int, float)):
                continue
            key_lower = key.lower()
            if "goal" in key_lower and goal is None:
                goal = float(value)
            elif any(term in key_lower for term in ("consumed", "intake", "hydration")) and "goal" not in key_lower:
                if intake is None:
                    intake = float(value)
            elif "sweat" in key_lower and sweat is None:
                sweat = float(value)

        if intake is None and goal is None and sweat is None:
            return None

        return {
            "intake_ml": intake,
            "goal_ml": goal,
            "sweat_loss_ml": sweat,
        }

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

    def _format_hydration_for_prompt(self, hydration: dict[str, Any] | None) -> str:
        if not hydration:
            return "Not available"

        intake = hydration.get("intake_ml")
        goal = hydration.get("goal_ml")
        sweat = hydration.get("sweat_loss_ml")

        parts: list[str] = []
        if isinstance(intake, (int, float)):
            intake_l = intake / 1000
            if isinstance(goal, (int, float)) and goal > 0:
                goal_l = goal / 1000
                parts.append(f"{intake_l:.1f}L of {goal_l:.1f}L goal")
            else:
                parts.append(f"{intake_l:.1f}L consumed")

        if isinstance(sweat, (int, float)) and sweat > 0:
            parts.append(f"sweat loss {sweat / 1000:.1f}L")

        return "; ".join(parts) if parts else "Not available"

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
