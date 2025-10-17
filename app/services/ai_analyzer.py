"""Claude AI-powered training readiness analysis."""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from anthropic import Anthropic

from app.config import get_settings
from app.services.garmin_service import GarminService


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
        garmin = GarminService()
        try:
            garmin.login()
            data = self._fetch_garmin_data(garmin, target_date)
        finally:
            try:
                garmin.logout()
            except Exception:
                pass

        # Calculate baselines
        baselines = self._calculate_baselines(data)

        # Build comprehensive prompt
        prompt = self._build_prompt(target_date, data, baselines)

        # Get AI analysis
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )

        # Parse response
        result = self._parse_response(response.content[0].text)

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

    def _build_prompt(self, target_date: date, data: dict[str, Any], baselines: dict[str, Any]) -> str:
        """Build comprehensive prompt for Claude AI."""

        # Extract key metrics
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

        # Format activity summary
        activity_summary = f"{baselines['activity_count']} activities in last 7 days, "
        activity_summary += f"{baselines['total_distance_km']}km total, "
        activity_summary += f"{baselines['total_duration_min']:.0f} min total"

        prompt = f"""You are an expert running coach and sports scientist analyzing an athlete's readiness to train.

TODAY'S DATE: {target_date.isoformat()}

ATHLETE'S PHYSIOLOGICAL DATA:
- Sleep: {sleep_info}
- HRV (Heart Rate Variability): {hrv_info}
- Heart Rate: {hr_info}
- Stress Level: {stress_info}
- Body Battery: {bb_info}
- Daily Steps: {stats.get('totalSteps', 'N/A')}
- Active Calories: {stats.get('activeKilocalories', 'N/A')}

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
- HRV drop >10% from baseline = possible illness/overtraining → recommend easy or rest
- Sleep <6 hours or poor quality → recommend easy day
- High stress or low body battery → scale back intensity
- Trust the data but acknowledge the athlete should listen to their body
- Be specific with workout details (duration, intensity, HR zones if available)

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
