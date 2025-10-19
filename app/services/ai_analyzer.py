"""Claude AI-powered training readiness analysis."""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from anthropic import Anthropic

from app.config import get_settings
from app.database import SessionLocal
from app.models.database_models import DailyMetric
from app.services.data_processor import DataProcessor
from app.services.garmin_service import GarminService


logger = logging.getLogger(__name__)


class AIAnalyzer:
    """Analyzes training readiness using Claude AI and live Garmin data."""

    def __init__(self) -> None:
        settings = get_settings()
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-5-20250929"

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

        # Fetch live Garmin data
        logger.info("Starting readiness analysis for %s", target_date.isoformat())
        garmin = GarminService()
        try:
            logger.debug("Fetching Garmin data for %s", target_date.isoformat())
            garmin.login()
            data = self._fetch_garmin_data(garmin, target_date)
        finally:
            try:
                garmin.logout()
            except Exception:
                pass

        logger.debug("Calculating baselines for %s", target_date.isoformat())
        # Calculate baselines
        baselines = self._calculate_baselines(data)
        historical_baselines = self._get_historical_baselines(target_date)

        # Build comprehensive prompt
        language, prompt, system_prompt = self._build_prompt(
            target_date,
            data,
            baselines,
            historical_baselines,
            locale=locale,
        )

        # Get AI analysis
        request_payload = {
            "model": self.model,
            "max_tokens": 4096,
            "temperature": 0.7,
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
        }

    def _calculate_baselines(self, data: dict[str, Any]) -> dict[str, Any]:
        """Calculate simple baselines from recent activity data."""

        activities = data.get("recent_activities", [])

        if not activities or "error" in str(activities):
            return {
                "avg_training_load": 0,
                "activity_count": 0,
                "total_distance": 0,
                "total_duration": 0,
            }

        # Calculate simple metrics from recent activities
        total_load = 0
        total_distance = 0
        total_duration = 0
        count = 0

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

        return {
            "avg_training_load": total_load / max(count, 1),
            "activity_count": count,
            "total_distance_km": round(total_distance, 1),
            "total_duration_min": round(total_duration, 0),
        }

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

    def _build_prompt(
        self,
        target_date: date,
        data: dict[str, Any],
        baselines: dict[str, Any],
        historical_baselines: dict[str, Any] | None,
        locale: str | None = None,
    ) -> tuple[str, str, str | None]:
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

        activity_summary = ""
        if isinstance(baselines, dict) and baselines:
            activity_count = baselines.get("activity_count", 0)
            total_distance = baselines.get("total_distance_km", 0)
            total_duration = baselines.get("total_duration_min", 0)
            activity_summary = (
                f"{activity_count} activities in last 7 days, "
                f"{total_distance}km total, "
                f"{total_duration:.0f} min total"
            ) if activity_count else "No recent activities synced"

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
            historical_context=historical_context,
            activity_summary=activity_summary,
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

        return language, prompt, system_prompt

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
