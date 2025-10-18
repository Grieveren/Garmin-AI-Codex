"""Claude AI-powered training readiness analysis."""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any

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

    async def analyze_daily_readiness(self, target_date: date) -> dict[str, Any]:
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
        prompt = self._build_prompt(
            target_date,
            data,
            baselines,
            historical_baselines,
        )

        # Get AI analysis
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}]
            )
        except Exception:
            logger.exception("Claude analysis failed for %s", target_date.isoformat())
            raise

        # Parse response
        result = self._parse_response(response.content[0].text)
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
    ) -> str:
        """Build comprehensive prompt for Claude AI."""

        # Extract key metrics
        stats = data.get("stats", {})
        sleep_data = data.get("sleep", {})
        hrv_data = data.get("hrv", {})
        hr_data = data.get("heart_rate", {})
        stress_data = data.get("stress", {})
        body_battery_data = data.get("body_battery", {})

        has_history = historical_baselines is not None

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
            # Get average stress from recent readings
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

        # Format enhanced metrics (Phase 1)
        training_readiness_data = data.get("training_readiness", {})
        training_status_data = data.get("training_status", {})
        spo2_data = data.get("spo2", {})
        respiration_data = data.get("respiration", {})

        garmin_readiness_info = "Not available"
        # Training readiness returns a list, uses "score" key
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
            # VO2 Max - nested in mostRecentVO2Max → generic → vo2MaxValue
            if "mostRecentVO2Max" in training_status_data:
                vo2_data = training_status_data.get("mostRecentVO2Max")
                if vo2_data and isinstance(vo2_data, dict):
                    generic = vo2_data.get("generic")
                    if generic and isinstance(generic, dict):
                        vo2_max = generic.get("vo2MaxValue")
                        if vo2_max:
                            vo2_max_info = f"{vo2_max} ml/kg/min"

            # Training Status - nested in mostRecentTrainingStatus → latestTrainingStatusData → {deviceId}
            if "mostRecentTrainingStatus" in training_status_data:
                status_data = training_status_data.get("mostRecentTrainingStatus")
                if status_data and isinstance(status_data, dict):
                    latest = status_data.get("latestTrainingStatusData")
                    if latest and isinstance(latest, dict):
                        # Get first device's data (usually primary device)
                        for device_id, device_data in latest.items():
                            if device_data and isinstance(device_data, dict):
                                training_status_key = device_data.get("trainingStatusFeedbackPhrase")
                                if training_status_key:
                                    training_status_info = training_status_key
                                break

        spo2_info = "Not available"
        if spo2_data and isinstance(spo2_data, dict):
            # Keys are at root level: avgSleepSpO2, lowestSpO2
            avg_spo2 = spo2_data.get("avgSleepSpO2")
            min_spo2 = spo2_data.get("lowestSpO2")
            if avg_spo2:
                spo2_info = f"Average: {avg_spo2}%"
                if min_spo2:
                    spo2_info += f", Minimum: {min_spo2}%"

        respiration_info = "Not available"
        if respiration_data and isinstance(respiration_data, dict):
            # Garmin uses avgSleepRespirationValue
            avg_resp = respiration_data.get("avgSleepRespirationValue")
            if avg_resp:
                respiration_info = f"{avg_resp} breaths/min"

        # Format activity summary
        activity_summary = f"{baselines['activity_count']} activities in last 7 days, "
        activity_summary += f"{baselines['total_distance_km']}km total, "
        activity_summary += f"{baselines['total_duration_min']:.0f} min total"

        # Build historical context section
        historical_context = ""
        if historical_baselines:
            hrv_baseline = historical_baselines["hrv"]
            rhr_baseline = historical_baselines["resting_hr"]
            sleep_baseline = historical_baselines["sleep"]
            acwr = historical_baselines["acwr"]
            trends = historical_baselines["training_trends"]

            acwr_warning = "Insufficient data"
            if acwr:
                acwr_ratio = acwr.get("acwr")
                if acwr_ratio is not None:
                    if acwr_ratio > 1.5:
                        acwr_warning = "ACWR >1.5 indicates HIGH INJURY RISK"
                    else:
                        acwr_warning = "ACWR in safe zone"

            historical_context = f"""

HISTORICAL BASELINES (30-day analysis):
- HRV Analysis:
  * Current: {hrv_baseline.get('current_hrv', 'N/A')}ms
  * 30-day baseline: {hrv_baseline.get('baseline_hrv', 'N/A')}ms
  * 7-day average: {hrv_baseline.get('7_day_avg', 'N/A')}ms
  * Deviation: {hrv_baseline.get('deviation_pct', 'N/A')}%
  * Trend: {hrv_baseline.get('trend', 'unknown')}
  * ⚠️ Concerning: {'YES - HRV significantly below baseline' if hrv_baseline.get('is_concerning') else 'No'}

- Resting Heart Rate:
  * Current: {rhr_baseline.get('current_rhr', 'N/A')} bpm
  * Baseline: {rhr_baseline.get('baseline_rhr', 'N/A')} bpm
  * Deviation: {rhr_baseline.get('deviation_bpm', 'N/A')} bpm
  * ⚠️ Elevated: {'YES - possible illness or fatigue' if rhr_baseline.get('is_elevated') else 'No'}

- Sleep Pattern:
  * Current: {sleep_baseline.get('current_hours', 'N/A')} hours
  * Baseline: {sleep_baseline.get('baseline_hours', 'N/A')} hours
  * 7-day average: {sleep_baseline.get('7_day_avg', 'N/A')} hours
  * Weekly sleep debt: {sleep_baseline.get('sleep_debt_hours', 'N/A')} hours
  * ⚠️ Sleep deprived: {'YES - insufficient sleep' if sleep_baseline.get('is_sleep_deprived') else 'No'}

- Training Load (ACWR - Injury Prevention):
  * Acute load (7 days): {acwr.get('acute_load', 'N/A')}
  * Chronic load (28 days): {acwr.get('chronic_load', 'N/A')}
  * ACWR Ratio: {acwr.get('acwr', 'N/A')}
  * Status: {acwr.get('status', 'unknown')}
  * Injury risk: {acwr.get('injury_risk', 'unknown').upper()}
  * ⚠️ WARNING: {acwr_warning}

- Training Trends (30 days):
  * Total activities: {trends.get('total_activities', 0)}
  * Total distance: {trends.get('total_distance_km', 0)}km
  * Average weekly distance: {trends.get('avg_weekly_distance', 0)}km/week
  * Consecutive training days: {trends.get('consecutive_training_days', 0)} days
  * ⚠️ No rest days: {'YES - overtraining risk!' if trends.get('consecutive_training_days', 0) >= 7 else 'No'}

IMPORTANT CONTEXT FROM HISTORICAL DATA:
* You now have 30 days of baseline data to compare against
* This allows you to detect deviations from the athlete's NORMAL ranges
* HRV drop >10% from baseline is a major red flag for overtraining/illness
* Resting HR elevation >5bpm suggests incomplete recovery
* ACWR >1.3 indicates increasing injury risk; >1.5 is dangerous
* 7+ consecutive training days without rest increases overtraining risk
"""

        prompt = f"""You are an expert running coach and sports scientist analyzing an athlete's readiness to train."""

        if historical_baselines:
            prompt += """

**IMPORTANT: You have access to 30 days of historical baseline data. Use this to provide highly personalized recommendations based on the athlete's ACTUAL normal ranges, not population averages.**
"""

        prompt += f"""

TODAY'S DATE: {target_date.isoformat()}

ATHLETE'S PHYSIOLOGICAL DATA (Today):
- Sleep: {sleep_info}
- HRV (Heart Rate Variability): {hrv_info}
- Heart Rate: {hr_info}
- Stress Level: {stress_info}
- Body Battery: {bb_info}
- Daily Steps: {stats.get('totalSteps', 'N/A')}
- Active Calories: {stats.get('activeKilocalories', 'N/A')}

ENHANCED RECOVERY METRICS:
- Garmin Training Readiness Score: {garmin_readiness_info} (Garmin's AI-powered readiness assessment)
- VO2 Max Estimate: {vo2_max_info}
- Training Status: {training_status_info} (productive/maintaining/peaking/overreaching)
- Blood Oxygen (SPO2): {spo2_info} (sleep average)
- Respiration Rate: {respiration_info} (elevated = stress/illness/overtraining)
{historical_context}
RECENT TRAINING HISTORY (Last 7 days):
{activity_summary}

TASK:
Analyze the athlete's readiness to train TODAY and provide:
1. Readiness score (0-100, where 0=completely exhausted, 100=fully recovered and ready for hard training)
2. Training recommendation: "high_intensity", "moderate", "easy", or "rest"
3. Specific workout suggestion with duration, intensity, and heart rate zones
4. Key factors that influenced your decision (3-5 bullet points)
5. Any red flags or concerns
6. Recovery tips (2-3 practical suggestions)

IMPORTANT GUIDELINES:
- **Use historical baselines when available** - Compare today's metrics to the athlete's 30-day baseline, not population averages
- HRV drop >10% from PERSONAL baseline = possible illness/overtraining → recommend easy or rest
- Resting HR >5bpm above PERSONAL baseline = incomplete recovery
- Sleep <6 hours or below personal average → recommend easy day
- High stress or low body battery → scale back intensity
- **ACWR >1.3 = approaching injury risk; >1.5 = HIGH RISK** - recommend reduced volume/intensity
- 7+ consecutive training days without rest = overtraining risk - MANDATE rest day

**PHASE 1 ENHANCED METRICS - HOW TO USE THEM:**
- **Garmin Training Readiness Score**: Primary indicator of readiness
  * <20 = CRITICAL - mandate rest day regardless of other metrics
  * 20-40 = POOR - strong consideration for rest or very easy day
  * 40-60 = LOW - recommend easy/recovery day
  * 60-75 = MODERATE - moderate training appropriate
  * 75+ = GOOD/EXCELLENT - green light for quality work
  * **ALWAYS mention this score in your reasoning** - it's Garmin's AI assessment

- **Training Status** (PRODUCTIVE/MAINTAINING/PEAKING/STRAINED/OVERREACHING/UNPRODUCTIVE):
  * **ALWAYS reference this in ai_reasoning** to contextualize training effectiveness
  * PRODUCTIVE = training is working, gains are happening
  * MAINTAINING = holding fitness, no regression
  * PEAKING = approaching peak form
  * STRAINED/OVERREACHING = warning signs, reduce volume
  * UNPRODUCTIVE = detraining or overtraining, intervention needed
  * Use this to reassure athlete that rest is part of productive training, not a failure

- **VO2 Max**:
  * **Mention when discussing fitness level or training capacity**
  * <35 = Low fitness (general population)
  * 35-45 = Average recreational athlete
  * 45-55 = Well-trained athlete
  * 55-65 = Highly trained/competitive
  * >65 = Elite level
  * Use this to contextualize the athlete's training capacity and recovery demands

- **SPO2 (Blood Oxygen Saturation)**:
  * **Reference if <95% average or showing concerning trends**
  * <95% = potential recovery issue, altitude effect, or respiratory concern
  * Normal: 95-100%
  * Combine with respiration rate for respiratory health assessment

- **Respiration Rate**:
  * **Mention if elevated above baseline or >15 breaths/min**
  * Normal resting: 8-12 breaths/min
  * Elevated = possible stress/illness/overtraining
  * Combine with SPO2 and HRV for comprehensive recovery picture

**CRITICAL: Your ai_reasoning MUST integrate these Phase 1 metrics to provide complete context, not just list problems.**

- Trust the data but acknowledge the athlete should listen to their body
- Be specific with workout details (duration, intensity, HR zones if available)
- Prioritize LONG-TERM health and injury prevention over short-term gains

Return your response as a JSON object with this EXACT structure:
{{
    "readiness_score": <number 0-100>,
    "recommendation": "<high_intensity|moderate|easy|rest>",
    "confidence": "<high|medium|low>",
    "key_factors": [
        "Factor 1...",
        "Factor 2...",
        "Factor 3..."
    ],
    "red_flags": [
        "Concern 1..."
    ],
    "suggested_workout": {{
        "type": "easy_run|tempo_run|intervals|long_run|rest|etc",
        "description": "Detailed workout description with structure",
        "target_duration_minutes": <number>,
        "intensity": <1-10>,
        "rationale": "Why this workout today?"
    }},
    "recovery_tips": [
        "Tip 1...",
        "Tip 2..."
    ],
    "ai_reasoning": "Brief explanation of your overall analysis and recommendation"
}}

Return ONLY the JSON object, no other text."""

        return prompt

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
