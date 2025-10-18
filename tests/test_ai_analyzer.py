"""Unit tests for AIAnalyzer stub."""
import json
from datetime import date
from types import SimpleNamespace

import pytest

from app.services.ai_analyzer import AIAnalyzer


@pytest.mark.asyncio
async def test_analyze_daily_readiness_returns_placeholder(monkeypatch: pytest.MonkeyPatch):
    class DummySettings:
        anthropic_api_key = "test-key"
        garmin_email = "test@example.com"
        garmin_password = "hunter2"
        garmin_token_store = None

    monkeypatch.setattr("app.services.ai_analyzer.get_settings", lambda: DummySettings())

    class DummyGarminService:
        def login(self, *args, **kwargs) -> None:
            return None

        def logout(self) -> None:
            return None

    monkeypatch.setattr("app.services.ai_analyzer.GarminService", DummyGarminService)

    sample_ai_payload = {
        "readiness_score": 72,
        "recommendation": "moderate",
        "confidence": "high",
        "key_factors": ["Stable HRV baseline"],
        "red_flags": [],
        "suggested_workout": {
            "type": "easy_run",
            "description": "30 min aerobic run",
            "target_duration_minutes": 30,
            "intensity": 4,
            "rationale": "Maintain aerobic base",
        },
        "recovery_tips": ["Finish with mobility work"],
        "ai_reasoning": "Stubbed response for unit test",
    }

    class DummyMessages:
        def create(self, **kwargs):
            return SimpleNamespace(
                content=[SimpleNamespace(text=json.dumps(sample_ai_payload))]
            )

    class DummyAnthropic:
        def __init__(self, api_key: str):
            self.messages = DummyMessages()

    monkeypatch.setattr("app.services.ai_analyzer.Anthropic", DummyAnthropic)

    def fake_fetch(self, garmin, target_date):
        return {
            "training_readiness": [{"score": 55}],
            "training_status": {
                "mostRecentVO2Max": {"generic": {"vo2MaxValue": 51.2}},
                "mostRecentTrainingStatus": {
                    "latestTrainingStatusData": {
                        "device123": {"trainingStatusFeedbackPhrase": "PRODUCTIVE"}
                    }
                },
            },
            "spo2": {"avgSleepSpO2": 96, "lowestSpO2": 92},
            "respiration": {"avgSleepRespirationValue": 14.5},
            "recent_activities": [],
        }

    monkeypatch.setattr(AIAnalyzer, "_fetch_garmin_data", fake_fetch)
    monkeypatch.setattr(
        AIAnalyzer,
        "_calculate_baselines",
        lambda self, data: {
            "avg_training_load": 42,
            "activity_count": 2,
            "total_distance_km": 10,
            "total_duration_min": 90,
        },
    )
    monkeypatch.setattr(AIAnalyzer, "_has_historical_data", lambda self, target_date: False)

    analyzer = AIAnalyzer()
    result = await analyzer.analyze_daily_readiness(date.today())

    assert result["recommendation"] == sample_ai_payload["recommendation"]
    assert result["readiness_score"] == sample_ai_payload["readiness_score"]
    assert result["enhanced_metrics"]["training_readiness_score"] == 55
