"""Unit tests for AIAnalyzer stub."""
import json
from datetime import date
from pathlib import Path
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
        prompt_config_path = Path("app/config/prompts.yaml")

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
                "currentRecoveryTime": 16,
                "loadFocus": [
                    {
                        "focus": "LOW_AEROBIC",
                        "load": 150,
                        "optimalRangeLow": 120,
                        "optimalRangeHigh": 200,
                        "status": "WITHIN"
                    }
                ],
                "heatAndAltitudeAcclimation": {
                    "heatAcclimationValue": 30,
                    "altitudeAcclimationValue": 5,
                    "status": "Acclimating"
                },
            },
            "spo2": {"avgSleepSpO2": 96, "lowestSpO2": 92},
            "respiration": {"avgSleepRespirationValue": 14.5},
            "hydration": {
                "summary": {
                    "hydrationGoalInML": 3000,
                    "consumedQuantityInML": 2400,
                    "sweatLossInML": 350
                }
            },
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
            "activity_breakdown": {},  # Backward compatibility for new feature
        },
    )
    monkeypatch.setattr(AIAnalyzer, "_has_historical_data", lambda self, target_date: False)

    analyzer = AIAnalyzer()
    result = await analyzer.analyze_daily_readiness(date.today())

    assert result["recommendation"] == sample_ai_payload["recommendation"]
    assert result["readiness_score"] == sample_ai_payload["readiness_score"]
    assert result["enhanced_metrics"]["training_readiness_score"] == 55
    assert result["extended_signals"]["recovery_time"]["hours"] == pytest.approx(16)
    assert result["extended_signals"]["hydration"]["goal_ml"] == 3000


class TestActivityTypeAnalysis:
    """Comprehensive tests for activity type classification and breakdown."""

    def test_classify_activity_impact_high_running(self):
        """Test high-impact classification for running activities."""
        analyzer = AIAnalyzer()
        activity = {
            "activityType": {"typeKey": "running"},
            "aerobicTrainingEffect": 3.2,
            "anaerobicTrainingEffect": 0.8,
            "averageHR": 155,
            "maxHR": 180,
            "duration": 2400,
        }
        impact = analyzer._classify_activity_impact(activity)
        assert impact == "high"

    def test_classify_activity_impact_high_training_effect(self):
        """Test high-impact classification based on very high training effect."""
        analyzer = AIAnalyzer()
        activity = {
            "activityType": {"typeKey": "cycling"},  # Normally moderate
            "aerobicTrainingEffect": 3.5,
            "anaerobicTrainingEffect": 0.8,  # Total = 4.3 > 4.0 threshold
            "averageHR": 165,
            "maxHR": 180,
            "duration": 3600,
        }
        impact = analyzer._classify_activity_impact(activity)
        assert impact == "high"

    def test_classify_activity_impact_high_hr_zones(self):
        """Test high-impact classification based on high HR zones."""
        analyzer = AIAnalyzer()
        activity = {
            "activityType": {"typeKey": "cycling"},
            "aerobicTrainingEffect": 1.5,  # Low training effect, but high HR
            "anaerobicTrainingEffect": 0.3,  # Total = 1.8 < 2.5 threshold
            "averageHR": 160,  # 89% of max HR > 0.85 threshold
            "maxHR": 180,
            "duration": 2400,
        }
        impact = analyzer._classify_activity_impact(activity)
        assert impact == "high"

    def test_classify_activity_impact_low_swimming(self):
        """Test low-impact classification for swimming."""
        analyzer = AIAnalyzer()
        activity = {
            "activityType": {"typeKey": "swimming"},
            "aerobicTrainingEffect": 2.0,
            "anaerobicTrainingEffect": 0.3,
            "averageHR": 120,
            "maxHR": 180,
            "duration": 2700,
        }
        impact = analyzer._classify_activity_impact(activity)
        assert impact == "low"

    def test_classify_activity_impact_low_yoga(self):
        """Test low-impact classification for yoga."""
        analyzer = AIAnalyzer()
        activity = {
            "activityType": {"typeKey": "yoga"},
            "aerobicTrainingEffect": 0.5,
            "anaerobicTrainingEffect": 0.0,
            "averageHR": 90,
            "maxHR": 180,
            "duration": 3600,
        }
        impact = analyzer._classify_activity_impact(activity)
        assert impact == "low"

    def test_classify_activity_impact_moderate_cycling(self):
        """Test moderate-impact classification for cycling."""
        analyzer = AIAnalyzer()
        activity = {
            "activityType": {"typeKey": "cycling"},
            "aerobicTrainingEffect": 2.8,
            "anaerobicTrainingEffect": 0.5,
            "averageHR": 135,
            "maxHR": 180,
            "duration": 3600,
        }
        impact = analyzer._classify_activity_impact(activity)
        assert impact == "moderate"

    def test_classify_activity_impact_moderate_rowing(self):
        """Test moderate-impact classification for rowing."""
        analyzer = AIAnalyzer()
        activity = {
            "activityType": {"typeKey": "rowing"},
            "aerobicTrainingEffect": 2.5,
            "anaerobicTrainingEffect": 0.4,
            "averageHR": 140,
            "maxHR": 180,
            "duration": 2400,
        }
        impact = analyzer._classify_activity_impact(activity)
        assert impact == "moderate"

    def test_classify_activity_impact_edge_case_none_input(self):
        """Test edge case: None input returns moderate."""
        analyzer = AIAnalyzer()
        impact = analyzer._classify_activity_impact(None)
        assert impact == "moderate"

    def test_classify_activity_impact_edge_case_malformed_dict(self):
        """Test edge case: malformed dict without activityType."""
        analyzer = AIAnalyzer()
        activity = {
            "aerobicTrainingEffect": 2.0,
            "duration": 1800,
            # Missing activityType field
        }
        impact = analyzer._classify_activity_impact(activity)
        assert impact == "moderate"

    def test_classify_activity_impact_edge_case_missing_fields(self):
        """Test edge case: activity with minimal fields."""
        analyzer = AIAnalyzer()
        activity = {
            "activityType": {"typeKey": "walking"},
            # Missing all optional fields
        }
        impact = analyzer._classify_activity_impact(activity)
        assert impact == "moderate"

    def test_classify_activity_impact_edge_case_unknown_type(self):
        """Test edge case: unknown activity type defaults to moderate."""
        analyzer = AIAnalyzer()
        activity = {
            "activityType": {"typeKey": "unknown_future_sport"},
            "aerobicTrainingEffect": 2.0,
            "anaerobicTrainingEffect": 0.5,
            "duration": 1800,
        }
        impact = analyzer._classify_activity_impact(activity)
        assert impact == "moderate"

    def test_format_activity_type_breakdown_mixed(self):
        """Test formatting with mixed activity types."""
        analyzer = AIAnalyzer()
        breakdown = {
            "running": {
                "count": 2,
                "total_duration_min": 60.0,
                "total_distance_km": 10.0,
                "impact_level": "high",
                "avg_hr": 150.0,
            },
            "cycling": {
                "count": 1,
                "total_duration_min": 90.0,
                "total_distance_km": 30.0,
                "impact_level": "moderate",
                "avg_hr": 135.0,
            },
            "swimming": {
                "count": 1,
                "total_duration_min": 45.0,
                "total_distance_km": 2.5,
                "impact_level": "low",
                "avg_hr": 120.0,
            },
        }
        result = analyzer._format_activity_type_breakdown(breakdown)

        assert "HIGH IMPACT:" in result
        assert "Running: 2x" in result
        assert "10.0km" in result

        assert "MODERATE IMPACT:" in result
        assert "Cycling: 1x" in result
        assert "30.0km" in result

        assert "LOW IMPACT:" in result
        assert "Swimming: 1x" in result

    def test_format_activity_type_breakdown_single_type(self):
        """Test formatting with single activity type."""
        analyzer = AIAnalyzer()
        breakdown = {
            "running": {
                "count": 3,
                "total_duration_min": 150.0,
                "total_distance_km": 25.0,
                "impact_level": "high",
                "avg_hr": 155.0,
            }
        }
        result = analyzer._format_activity_type_breakdown(breakdown)

        assert "HIGH IMPACT:" in result
        assert "Running: 3x" in result
        assert "150min total" in result
        assert "25.0km" in result
        assert "avg HR 155 bpm" in result

    def test_format_activity_type_breakdown_empty(self):
        """Test formatting with empty breakdown."""
        analyzer = AIAnalyzer()
        result = analyzer._format_activity_type_breakdown({})
        assert result == "No recent activities synced"

    def test_calculate_baselines_with_activities(self):
        """Test baseline calculation includes activity breakdown."""
        analyzer = AIAnalyzer()
        data = {
            "recent_activities": [
                {
                    "activityType": {"typeKey": "running"},
                    "aerobicTrainingEffect": 3.2,
                    "distance": 5000,  # 5km in meters
                    "duration": 1800,  # 30 min in seconds
                    "averageHR": 150,
                },
                {
                    "activityType": {"typeKey": "running"},
                    "aerobicTrainingEffect": 2.8,
                    "distance": 8000,  # 8km
                    "duration": 2700,  # 45 min
                    "averageHR": 145,
                },
            ]
        }

        result = analyzer._calculate_baselines(data)

        assert result["activity_count"] == 2
        assert result["total_distance_km"] == 13.0
        assert result["total_duration_min"] == 75.0
        assert "activity_breakdown" in result
        assert "running" in result["activity_breakdown"]

        running_stats = result["activity_breakdown"]["running"]
        assert running_stats["count"] == 2
        assert running_stats["impact_level"] == "high"
        assert running_stats["total_distance_km"] == 13.0
        assert running_stats["avg_hr"] == pytest.approx(147.5)  # (150 + 145) / 2

    def test_calculate_baselines_empty_activities(self):
        """Test baseline calculation with no activities (backward compatibility)."""
        analyzer = AIAnalyzer()
        data = {"recent_activities": []}

        result = analyzer._calculate_baselines(data)

        assert result["activity_count"] == 0
        assert result["avg_training_load"] == 0
        assert result["total_distance_km"] == 0
        assert result["total_duration_min"] == 0
        assert result["activity_breakdown"] == {}

    def test_calculate_baselines_division_by_zero_protection(self):
        """Test that division by zero is properly handled."""
        analyzer = AIAnalyzer()
        data = {"recent_activities": []}

        result = analyzer._calculate_baselines(data)

        # Should not raise exception, should return 0
        assert result["avg_training_load"] == 0
        assert result["activity_count"] == 0
