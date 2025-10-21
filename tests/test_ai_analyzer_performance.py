"""Comprehensive unit tests for AIAnalyzer Phase 1 performance analysis.

Tests cover:
- _analyze_most_recent_workout: Find recent workouts within 72h window
- _compare_to_recent_similar_workouts: Compare against similar workout history
- _calculate_performance_condition: Determine performance state (Strong/Normal/Fatigued)
- _format_recent_workout_analysis: Format for AI prompt inclusion
"""
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.services.ai_analyzer import AIAnalyzer


# ============================================================================
# Fixtures and Test Data
# ============================================================================

@pytest.fixture
def analyzer():
    """Create AIAnalyzer instance with mocked config."""
    class DummySettings:
        anthropic_api_key = "test-key"
        garmin_email = "test@example.com"
        garmin_password = "test-password"
        garmin_token_store = None
        prompt_config_path = Path("app/config/prompts.yaml")

    import app.services.ai_analyzer as ai_module
    original_get_settings = ai_module.get_settings
    ai_module.get_settings = lambda: DummySettings()

    analyzer = AIAnalyzer()

    # Restore
    ai_module.get_settings = original_get_settings
    return analyzer


def create_activity(
    activity_type: str,
    date_str: str,
    duration_seconds: int = 1800,
    distance_meters: float | None = 5000,
    avg_hr: int | None = 150,
    max_hr: int | None = 180,
    aerobic_te: float | None = 3.0,
    anaerobic_te: float | None = 0.5,
) -> dict:
    """Helper to create realistic Garmin activity data."""
    return {
        "activityType": {"typeKey": activity_type},
        "startTimeLocal": f"{date_str}T08:00:00",
        "duration": duration_seconds,
        "distance": distance_meters,
        "averageHR": avg_hr,
        "maxHR": max_hr,
        "aerobicTrainingEffect": aerobic_te,
        "anaerobicTrainingEffect": anaerobic_te,
    }


# ============================================================================
# Test _analyze_most_recent_workout
# ============================================================================

class TestAnalyzeMostRecentWorkout:
    """Test suite for _analyze_most_recent_workout method."""

    def test_recent_workout_found_within_72h(self, analyzer):
        """Test that recent workout within 72h window is found correctly."""
        target_date = date(2025, 10, 21)
        yesterday = (target_date - timedelta(days=1)).isoformat()

        activities = [
            create_activity("running", yesterday, duration_seconds=2400, distance_meters=8000)
        ]

        result = analyzer._analyze_most_recent_workout(activities, target_date)

        assert result is not None
        assert result["activity_type"] == "running"
        assert result["date"] == date(2025, 10, 20)
        assert result["duration_seconds"] == 2400
        assert result["distance_meters"] == 8000
        assert result["avg_hr"] == 150
        assert result["max_hr"] == 180
        assert result["aerobic_training_effect"] == 3.0
        assert result["hours_since_workout"] == pytest.approx(24.0)

    def test_no_recent_workout_beyond_72h(self, analyzer):
        """Test that workout older than 72h returns None."""
        target_date = date(2025, 10, 21)
        four_days_ago = (target_date - timedelta(days=4)).isoformat()

        activities = [
            create_activity("running", four_days_ago)
        ]

        result = analyzer._analyze_most_recent_workout(activities, target_date)

        assert result is None

    def test_multiple_recent_workouts_returns_most_recent(self, analyzer):
        """Test that most recent workout is returned when multiple are within window."""
        target_date = date(2025, 10, 21)
        yesterday = (target_date - timedelta(days=1)).isoformat()
        two_days_ago = (target_date - timedelta(days=2)).isoformat()

        activities = [
            create_activity("cycling", two_days_ago, duration_seconds=3600),
            create_activity("running", yesterday, duration_seconds=1800),
        ]

        result = analyzer._analyze_most_recent_workout(activities, target_date)

        assert result is not None
        assert result["activity_type"] == "running"
        assert result["date"] == date(2025, 10, 20)
        assert result["duration_seconds"] == 1800

    def test_workout_too_short_excluded(self, analyzer):
        """Test that workouts shorter than 5 minutes are excluded."""
        target_date = date(2025, 10, 21)
        yesterday = (target_date - timedelta(days=1)).isoformat()

        activities = [
            # 4 minutes - should be excluded
            create_activity("running", yesterday, duration_seconds=240)
        ]

        result = analyzer._analyze_most_recent_workout(activities, target_date)

        assert result is None

    def test_missing_activity_data_fields_graceful_handling(self, analyzer):
        """Test graceful handling of activities with missing optional fields."""
        target_date = date(2025, 10, 21)
        yesterday = (target_date - timedelta(days=1)).isoformat()

        activities = [
            {
                "activityType": {"typeKey": "yoga"},
                "startTimeLocal": f"{yesterday}T08:00:00",
                "duration": 3600,
                # Missing: distance, avg_hr, max_hr, training effects
            }
        ]

        result = analyzer._analyze_most_recent_workout(activities, target_date)

        assert result is not None
        assert result["activity_type"] == "yoga"
        assert result["duration_seconds"] == 3600
        assert result["distance_meters"] is None
        assert result["avg_hr"] is None
        assert result["max_hr"] is None
        assert result["avg_pace"] is None
        assert result["aerobic_training_effect"] is None

    def test_empty_activities_list(self, analyzer):
        """Test that empty activities list returns None."""
        result = analyzer._analyze_most_recent_workout([], date(2025, 10, 21))
        assert result is None

    def test_malformed_activity_data(self, analyzer):
        """Test graceful handling of malformed activity data."""
        target_date = date(2025, 10, 21)

        activities = [
            {"error": "API error"},  # Error response
            {"activityType": "invalid"},  # Missing typeKey
            {"startTimeLocal": "invalid-date"},  # Invalid date format
            {},  # Empty dict
        ]

        result = analyzer._analyze_most_recent_workout(activities, target_date)
        assert result is None

    def test_pace_calculation_with_distance(self, analyzer):
        """Test that average pace is calculated correctly when distance is available."""
        target_date = date(2025, 10, 21)
        yesterday = (target_date - timedelta(days=1)).isoformat()

        # 5km in 30 minutes = 6 min/km pace
        activities = [
            create_activity("running", yesterday, duration_seconds=1800, distance_meters=5000)
        ]

        result = analyzer._analyze_most_recent_workout(activities, target_date)

        assert result is not None
        assert result["avg_pace"] == pytest.approx(6.0)  # 1800s / 5km = 6 min/km

    def test_pace_calculation_without_distance(self, analyzer):
        """Test that pace is None for non-distance activities."""
        target_date = date(2025, 10, 21)
        yesterday = (target_date - timedelta(days=1)).isoformat()

        activities = [
            create_activity("strength_training", yesterday, duration_seconds=2400, distance_meters=None)
        ]

        result = analyzer._analyze_most_recent_workout(activities, target_date)

        assert result is not None
        assert result["avg_pace"] is None

    def test_hours_since_workout_calculation(self, analyzer):
        """Test accurate calculation of hours since workout."""
        target_date = date(2025, 10, 21)

        # Test various time differences (only using full days since we work with date objects)
        test_cases = [
            ((target_date - timedelta(days=1)).isoformat(), 24.0),
            ((target_date - timedelta(days=2)).isoformat(), 48.0),
            ((target_date - timedelta(days=3)).isoformat(), 72.0),
        ]

        for date_str, expected_hours in test_cases:
            activities = [create_activity("running", date_str)]
            result = analyzer._analyze_most_recent_workout(activities, target_date)
            assert result["hours_since_workout"] == pytest.approx(expected_hours, abs=0.1)


# ============================================================================
# Test _compare_to_recent_similar_workouts
# ============================================================================

class TestCompareToRecentSimilarWorkouts:
    """Test suite for _compare_to_recent_similar_workouts method."""

    def test_sufficient_similar_workouts(self, analyzer):
        """Test comparison with sufficient similar workouts (≥2)."""
        target_date = date(2025, 10, 21)
        yesterday = (target_date - timedelta(days=1)).isoformat()

        recent_workout = {
            "activity_type": "running",
            "date": date(2025, 10, 20),
            "avg_hr": 155,
            "avg_pace": 5.5,
        }

        # Similar workouts with slightly higher HR and slower pace
        activities = [
            create_activity("running", (target_date - timedelta(days=3)).isoformat(), avg_hr=150, distance_meters=5000, duration_seconds=1800),
            create_activity("running", (target_date - timedelta(days=5)).isoformat(), avg_hr=148, distance_meters=5000, duration_seconds=1800),
            create_activity("cycling", (target_date - timedelta(days=4)).isoformat()),  # Different type
        ]

        result = analyzer._compare_to_recent_similar_workouts(recent_workout, activities)

        assert result["similar_workout_count"] == 2
        assert result["avg_hr_baseline"] == pytest.approx(149.0)  # (150 + 148) / 2
        assert result["hr_deviation_bpm"] == pytest.approx(6.0)  # 155 - 149
        assert result["avg_pace_baseline"] is not None
        assert result["trend"] in ["improving", "stable", "declining"]

    def test_insufficient_similar_workouts(self, analyzer):
        """Test that insufficient similar workouts (<2) returns None values."""
        recent_workout = {
            "activity_type": "running",
            "date": date(2025, 10, 20),
            "avg_hr": 155,
            "avg_pace": 5.5,
        }

        # Only 1 similar workout
        activities = [
            create_activity("running", "2025-10-18", avg_hr=150),
        ]

        result = analyzer._compare_to_recent_similar_workouts(recent_workout, activities)

        assert result["similar_workout_count"] == 1
        assert result["avg_hr_baseline"] is None
        assert result["avg_pace_baseline"] is None
        assert result["hr_deviation_bpm"] is None
        assert result["trend"] is None

    def test_no_similar_workouts_different_activity_types(self, analyzer):
        """Test that different activity types are not compared."""
        recent_workout = {
            "activity_type": "running",
            "date": date(2025, 10, 20),
            "avg_hr": 155,
        }

        # All different activity types
        activities = [
            create_activity("cycling", "2025-10-18"),
            create_activity("swimming", "2025-10-17"),
            create_activity("yoga", "2025-10-16"),
        ]

        result = analyzer._compare_to_recent_similar_workouts(recent_workout, activities)

        assert result["similar_workout_count"] == 0
        assert result["trend"] is None

    def test_missing_hr_data_in_comparison(self, analyzer):
        """Test graceful handling when HR data is missing."""
        recent_workout = {
            "activity_type": "running",
            "date": date(2025, 10, 20),
            "avg_hr": None,  # Missing HR
            "avg_pace": 5.5,
        }

        activities = [
            create_activity("running", "2025-10-18", avg_hr=None),
            create_activity("running", "2025-10-17", avg_hr=None),
        ]

        result = analyzer._compare_to_recent_similar_workouts(recent_workout, activities)

        assert result["avg_hr_baseline"] is None
        assert result["hr_deviation_bpm"] is None

    def test_missing_pace_data_in_comparison(self, analyzer):
        """Test graceful handling when pace data is missing."""
        recent_workout = {
            "activity_type": "strength_training",
            "date": date(2025, 10, 20),
            "avg_hr": 130,
            "avg_pace": None,  # No distance = no pace
        }

        activities = [
            create_activity("strength_training", "2025-10-18", distance_meters=None),
            create_activity("strength_training", "2025-10-17", distance_meters=None),
        ]

        result = analyzer._compare_to_recent_similar_workouts(recent_workout, activities)

        assert result["avg_pace_baseline"] is None
        assert result["pace_deviation_pct"] is None

    def test_trend_detection_improving(self, analyzer):
        """Test trend detection identifies improving performance (lower HR)."""
        recent_workout = {
            "activity_type": "running",
            "date": date(2025, 10, 20),
            "avg_hr": 140,  # Much lower than baseline
            "avg_pace": 5.0,
        }

        # Baseline HR = 155
        activities = [
            create_activity("running", "2025-10-18", avg_hr=155, distance_meters=5000, duration_seconds=1800),
            create_activity("running", "2025-10-17", avg_hr=155, distance_meters=5000, duration_seconds=1800),
        ]

        result = analyzer._compare_to_recent_similar_workouts(recent_workout, activities)

        assert result["hr_deviation_bpm"] == pytest.approx(-15.0)
        assert result["trend"] == "improving"

    def test_trend_detection_stable(self, analyzer):
        """Test trend detection identifies stable performance (within ±5%)."""
        recent_workout = {
            "activity_type": "running",
            "date": date(2025, 10, 20),
            "avg_hr": 152,  # Only +2 bpm from baseline
            "avg_pace": 6.0,
        }

        # Baseline HR = 150
        activities = [
            create_activity("running", "2025-10-18", avg_hr=150, distance_meters=5000, duration_seconds=1800),
            create_activity("running", "2025-10-17", avg_hr=150, distance_meters=5000, duration_seconds=1800),
        ]

        result = analyzer._compare_to_recent_similar_workouts(recent_workout, activities)

        assert result["hr_deviation_bpm"] == pytest.approx(2.0)
        assert result["trend"] == "stable"

    def test_trend_detection_declining(self, analyzer):
        """Test trend detection identifies declining performance (higher HR or slower pace)."""
        recent_workout = {
            "activity_type": "running",
            "date": date(2025, 10, 20),
            "avg_hr": 165,  # Much higher than baseline
            "avg_pace": 6.5,
        }

        # Baseline HR = 150
        activities = [
            create_activity("running", "2025-10-18", avg_hr=150, distance_meters=5000, duration_seconds=1800),
            create_activity("running", "2025-10-17", avg_hr=150, distance_meters=5000, duration_seconds=1800),
        ]

        result = analyzer._compare_to_recent_similar_workouts(recent_workout, activities)

        assert result["hr_deviation_bpm"] == pytest.approx(15.0)
        assert result["trend"] == "declining"

    def test_pace_deviation_calculation(self, analyzer):
        """Test accurate pace deviation percentage calculation."""
        recent_workout = {
            "activity_type": "running",
            "date": date(2025, 10, 20),
            "avg_hr": 150,
            "avg_pace": 5.0,  # 5 min/km (faster than baseline)
        }

        # Baseline pace = 6 min/km
        activities = [
            create_activity("running", "2025-10-18", duration_seconds=1800, distance_meters=5000),  # 6 min/km
            create_activity("running", "2025-10-17", duration_seconds=1800, distance_meters=5000),  # 6 min/km
        ]

        result = analyzer._compare_to_recent_similar_workouts(recent_workout, activities)

        # (5 - 6) / 6 * 100 = -16.67% (negative = faster)
        assert result["pace_deviation_pct"] == pytest.approx(-16.67, rel=0.01)

    def test_similar_workout_lookback_window_14_days(self, analyzer):
        """Test that only workouts within 14-day lookback window are considered."""
        target_date = date(2025, 10, 21)
        recent_workout = {
            "activity_type": "running",
            "date": date(2025, 10, 20),
            "avg_hr": 150,
            "avg_pace": 6.0,  # Required field
        }

        activities = [
            create_activity("running", "2025-10-18", avg_hr=150),  # 2 days before recent - INCLUDED
            create_activity("running", "2025-10-10", avg_hr=148),  # 10 days before recent - INCLUDED
            create_activity("running", "2025-10-05", avg_hr=145),  # 15 days before recent - EXCLUDED
        ]

        result = analyzer._compare_to_recent_similar_workouts(recent_workout, activities)

        # Only 2 workouts within 14-day window
        assert result["similar_workout_count"] == 2

    def test_excludes_recent_workout_from_comparison(self, analyzer):
        """Test that the recent workout itself is excluded from comparison baseline."""
        recent_workout = {
            "activity_type": "running",
            "date": date(2025, 10, 20),
            "avg_hr": 160,  # Outlier
            "avg_pace": 6.5,  # Required field
        }

        activities = [
            # The recent workout itself
            create_activity("running", "2025-10-20", avg_hr=160),
            # Other similar workouts
            create_activity("running", "2025-10-18", avg_hr=150),
            create_activity("running", "2025-10-17", avg_hr=150),
        ]

        result = analyzer._compare_to_recent_similar_workouts(recent_workout, activities)

        # Should only compare against the 2 older workouts
        assert result["similar_workout_count"] == 2
        assert result["avg_hr_baseline"] == pytest.approx(150.0)


# ============================================================================
# Test _calculate_performance_condition
# ============================================================================

class TestCalculatePerformanceCondition:
    """Test suite for _calculate_performance_condition method."""

    def test_strong_condition_low_hr(self, analyzer):
        """Test Strong condition when HR is 6+ bpm lower than baseline."""
        recent_workout = {"avg_hr": 140}
        comparison = {
            "hr_deviation_bpm": -6.0,
            "pace_deviation_pct": 0.0,
        }

        condition = analyzer._calculate_performance_condition(recent_workout, comparison)
        assert condition == "Strong"

    def test_strong_condition_fast_pace(self, analyzer):
        """Test Strong condition when pace is 6%+ faster than baseline."""
        recent_workout = {"avg_pace": 5.5}
        comparison = {
            "hr_deviation_bpm": 0.0,
            "pace_deviation_pct": -6.0,
        }

        condition = analyzer._calculate_performance_condition(recent_workout, comparison)
        assert condition == "Strong"

    def test_normal_condition_within_threshold(self, analyzer):
        """Test Normal condition when metrics are within ±5% threshold."""
        recent_workout = {"avg_hr": 150}
        comparison = {
            "hr_deviation_bpm": 2.0,  # +2 bpm
            "pace_deviation_pct": -3.0,  # 3% faster
        }

        condition = analyzer._calculate_performance_condition(recent_workout, comparison)
        assert condition == "Normal"

    def test_fatigued_condition_high_hr(self, analyzer):
        """Test Fatigued condition when HR is 6+ bpm higher than baseline."""
        recent_workout = {"avg_hr": 165}
        comparison = {
            "hr_deviation_bpm": 6.0,
            "pace_deviation_pct": 0.0,
        }

        condition = analyzer._calculate_performance_condition(recent_workout, comparison)
        assert condition == "Fatigued"

    def test_fatigued_condition_slow_pace(self, analyzer):
        """Test Fatigued condition when pace is 6%+ slower than baseline."""
        recent_workout = {"avg_pace": 6.5}
        comparison = {
            "hr_deviation_bpm": 0.0,
            "pace_deviation_pct": 6.0,
        }

        condition = analyzer._calculate_performance_condition(recent_workout, comparison)
        assert condition == "Fatigued"

    def test_missing_comparison_data_defaults_normal(self, analyzer):
        """Test that missing comparison data defaults to Normal condition."""
        recent_workout = {}
        comparison = {
            "hr_deviation_bpm": None,
            "pace_deviation_pct": None,
        }

        condition = analyzer._calculate_performance_condition(recent_workout, comparison)
        assert condition == "Normal"

    def test_threshold_boundary_exactly_5_bpm(self, analyzer):
        """Test exact boundary condition (5 bpm deviation)."""
        recent_workout = {"avg_hr": 155}
        comparison = {
            "hr_deviation_bpm": 5.0,  # Exactly at threshold
            "pace_deviation_pct": 0.0,
        }

        condition = analyzer._calculate_performance_condition(recent_workout, comparison)
        assert condition == "Normal"  # Must be > 5 to be Fatigued

    def test_threshold_boundary_exactly_5_percent(self, analyzer):
        """Test exact boundary condition (5% pace deviation)."""
        recent_workout = {"avg_pace": 6.0}
        comparison = {
            "hr_deviation_bpm": 0.0,
            "pace_deviation_pct": 5.0,  # Exactly at threshold
        }

        condition = analyzer._calculate_performance_condition(recent_workout, comparison)
        assert condition == "Normal"  # Must be > 5% to be Fatigued


# ============================================================================
# Test _format_recent_workout_analysis
# ============================================================================

class TestFormatRecentWorkoutAnalysis:
    """Test suite for _format_recent_workout_analysis method."""

    def test_complete_data_formatting(self, analyzer):
        """Test formatting with complete workout and comparison data."""
        recent_workout = {
            "activity_type": "running",
            "date": date(2025, 10, 20),
            "duration_seconds": 1800,
            "distance_meters": 5000,
            "avg_hr": 155,
            "max_hr": 175,
            "avg_pace": 6.0,
            "aerobic_training_effect": 3.2,
            "anaerobic_training_effect": 0.8,
            "hours_since_workout": 18.5,
        }

        comparison = {
            "avg_hr_baseline": 150.0,
            "avg_pace_baseline": 6.5,
            "hr_deviation_bpm": 5.0,
            "pace_deviation_pct": -7.69,
            "trend": "improving",
            "similar_workout_count": 3,
        }

        condition = "Strong"

        result = analyzer._format_recent_workout_analysis(recent_workout, comparison, condition)

        # Verify key sections are present
        assert "MOST RECENT WORKOUT: Running on 2025-10-20" in result
        assert "18.5 hours ago" in result
        assert "Duration: 30 minutes" in result
        assert "Distance: 5.00 km" in result
        assert "Pace: 6:00 min/km" in result
        assert "FASTER by 7.7%" in result
        assert "Average HR: 155 bpm" in result
        assert "HIGHER by 5 bpm" in result
        assert "Max HR: 175 bpm" in result
        assert "Aerobic Training Effect: 3.2" in result
        assert "Anaerobic Training Effect: 0.8" in result
        assert "PERFORMANCE CONDITION: Strong" in result
        assert "TREND: IMPROVING" in result
        assert "3 similar workouts" in result

    def test_missing_distance_no_pace(self, analyzer):
        """Test formatting when distance is missing (no pace calculation)."""
        recent_workout = {
            "activity_type": "strength_training",
            "date": date(2025, 10, 20),
            "duration_seconds": 2400,
            "distance_meters": None,  # No distance
            "avg_hr": 130,
            "max_hr": 160,
            "avg_pace": None,
            "aerobic_training_effect": 2.0,
            "anaerobic_training_effect": 1.5,
            "hours_since_workout": 12.0,
        }

        comparison = {
            "avg_hr_baseline": 128.0,
            "avg_pace_baseline": None,
            "hr_deviation_bpm": 2.0,
            "pace_deviation_pct": None,
            "trend": "stable",
            "similar_workout_count": 2,
        }

        condition = "Normal"

        result = analyzer._format_recent_workout_analysis(recent_workout, comparison, condition)

        assert "MOST RECENT WORKOUT: Strength Training" in result
        assert "Duration: 40 minutes" in result
        assert "Distance:" not in result  # No distance section
        assert "Pace:" not in result  # No pace section
        assert "Average HR: 130 bpm" in result
        assert "PERFORMANCE CONDITION: Normal" in result

    def test_missing_hr_data(self, analyzer):
        """Test formatting when HR data is missing."""
        recent_workout = {
            "activity_type": "yoga",
            "date": date(2025, 10, 20),
            "duration_seconds": 3600,
            "distance_meters": None,
            "avg_hr": None,  # No HR data
            "max_hr": None,
            "avg_pace": None,
            "aerobic_training_effect": 0.5,
            "anaerobic_training_effect": 0.0,
            "hours_since_workout": 6.0,
        }

        comparison = {
            "avg_hr_baseline": None,
            "avg_pace_baseline": None,
            "hr_deviation_bpm": None,
            "pace_deviation_pct": None,
            "trend": None,
            "similar_workout_count": 0,
        }

        condition = "Normal"

        result = analyzer._format_recent_workout_analysis(recent_workout, comparison, condition)

        assert "MOST RECENT WORKOUT: Yoga" in result
        assert "Duration: 60 minutes" in result
        assert "Average HR:" not in result  # No HR section
        assert "PERFORMANCE CONDITION: Normal" in result
        assert "TREND:" not in result  # No trend with 0 similar workouts

    def test_output_structure_and_readability(self, analyzer):
        """Test that output is well-structured and readable."""
        recent_workout = {
            "activity_type": "cycling",
            "date": date(2025, 10, 20),
            "duration_seconds": 3600,
            "distance_meters": 30000,
            "avg_hr": 145,
            "max_hr": 165,
            "avg_pace": 7.2,  # 7.2 min/km (cycling pace)
            "aerobic_training_effect": 2.8,
            "anaerobic_training_effect": 0.5,
            "hours_since_workout": 36.0,
        }

        comparison = {
            "avg_hr_baseline": 140.0,
            "avg_pace_baseline": 7.5,
            "hr_deviation_bpm": 5.0,
            "pace_deviation_pct": -4.0,
            "trend": "improving",
            "similar_workout_count": 4,
        }

        condition = "Normal"

        result = analyzer._format_recent_workout_analysis(recent_workout, comparison, condition)

        # Check structure
        lines = result.split("\n")
        assert len(lines) > 5  # Should have multiple lines

        # Check formatting
        assert "1.5 days ago" in result  # 36 hours = 1.5 days
        assert "Duration: 60 minutes" in result
        assert "Distance: 30.00 km" in result
        assert "Pace: 7:12 min/km" in result
        assert "FASTER by 4.0%" in result

    def test_recency_formatting_hours_vs_days(self, analyzer):
        """Test that recency is formatted as hours (<24h) or days (≥24h)."""
        # Test hours
        recent_workout_hours = {
            "activity_type": "running",
            "date": date(2025, 10, 20),
            "duration_seconds": 1800,
            "distance_meters": 5000,
            "avg_hr": 150,
            "max_hr": 170,
            "avg_pace": 6.0,
            "aerobic_training_effect": 3.0,
            "anaerobic_training_effect": 0.5,
            "hours_since_workout": 18.5,
        }

        comparison = {
            "avg_hr_baseline": None,
            "avg_pace_baseline": None,
            "hr_deviation_bpm": None,
            "pace_deviation_pct": None,
            "trend": None,
            "similar_workout_count": 0,
        }

        condition = "Normal"

        result_hours = analyzer._format_recent_workout_analysis(recent_workout_hours, comparison, condition)
        assert "18.5 hours ago" in result_hours

        # Test days
        recent_workout_days = recent_workout_hours.copy()
        recent_workout_days["hours_since_workout"] = 48.0

        result_days = analyzer._format_recent_workout_analysis(recent_workout_days, comparison, condition)
        assert "2.0 days ago" in result_days


# ============================================================================
# Integration Tests
# ============================================================================

class TestPerformanceAnalysisIntegration:
    """End-to-end integration tests for performance analysis workflow."""

    def test_end_to_end_workflow_with_realistic_data(self, analyzer):
        """Test complete workflow from activities to formatted analysis."""
        target_date = date(2025, 10, 21)

        # Realistic activity history
        activities = [
            # Most recent: Yesterday's run (slower than usual)
            create_activity("running", "2025-10-20", duration_seconds=1800, distance_meters=5000, avg_hr=165, max_hr=180),

            # Similar runs from past 14 days (faster, lower HR)
            create_activity("running", "2025-10-18", duration_seconds=1620, distance_meters=5000, avg_hr=155, max_hr=175),
            create_activity("running", "2025-10-15", duration_seconds=1650, distance_meters=5000, avg_hr=153, max_hr=173),
            create_activity("running", "2025-10-12", duration_seconds=1680, distance_meters=5000, avg_hr=156, max_hr=176),

            # Other activities (should not affect running comparison)
            create_activity("cycling", "2025-10-19", duration_seconds=3600, distance_meters=30000, avg_hr=140),
            create_activity("yoga", "2025-10-17", duration_seconds=3600, distance_meters=None, avg_hr=100),

            # Old activities (outside 14-day window)
            create_activity("running", "2025-10-05", duration_seconds=1800, distance_meters=5000, avg_hr=150),
        ]

        # Step 1: Analyze most recent workout
        recent_workout = analyzer._analyze_most_recent_workout(activities, target_date)
        assert recent_workout is not None
        assert recent_workout["activity_type"] == "running"

        # Step 2: Compare to similar workouts
        comparison = analyzer._compare_to_recent_similar_workouts(recent_workout, activities)
        assert comparison["similar_workout_count"] == 3  # 3 similar runs within 14 days
        assert comparison["avg_hr_baseline"] == pytest.approx(154.67, abs=0.1)  # (155+153+156)/3

        # Step 3: Calculate performance condition
        condition = analyzer._calculate_performance_condition(recent_workout, comparison)
        assert condition == "Fatigued"  # Higher HR, slower pace

        # Step 4: Format analysis
        analysis = analyzer._format_recent_workout_analysis(recent_workout, comparison, condition)
        assert "MOST RECENT WORKOUT: Running" in analysis
        assert "PERFORMANCE CONDITION: Fatigued" in analysis
        assert "HIGHER by" in analysis  # HR higher than baseline
        assert "SLOWER by" in analysis  # Pace slower than baseline

    def test_workflow_with_running_cycling_swimming(self, analyzer):
        """Test workflow distinguishes between different activity types."""
        target_date = date(2025, 10, 21)

        activities = [
            # Recent swimming workout
            create_activity("swimming", "2025-10-20", duration_seconds=2700, distance_meters=2000, avg_hr=130, max_hr=150),

            # Similar swimming workouts
            create_activity("swimming", "2025-10-18", duration_seconds=2700, distance_meters=2000, avg_hr=128),
            create_activity("swimming", "2025-10-16", duration_seconds=2700, distance_meters=2000, avg_hr=132),

            # Running workouts (should be ignored for swimming comparison)
            create_activity("running", "2025-10-19", duration_seconds=1800, distance_meters=5000, avg_hr=155),
            create_activity("running", "2025-10-17", duration_seconds=1800, distance_meters=5000, avg_hr=158),
        ]

        recent_workout = analyzer._analyze_most_recent_workout(activities, target_date)
        assert recent_workout["activity_type"] == "swimming"

        comparison = analyzer._compare_to_recent_similar_workouts(recent_workout, activities)
        assert comparison["similar_workout_count"] == 2  # Only 2 swimming workouts

        condition = analyzer._calculate_performance_condition(recent_workout, comparison)
        assert condition == "Normal"  # Similar to baseline

    def test_workflow_with_missing_fields_graceful_degradation(self, analyzer):
        """Test workflow handles missing data fields gracefully."""
        target_date = date(2025, 10, 21)

        activities = [
            # Recent workout with minimal data
            {
                "activityType": {"typeKey": "strength_training"},
                "startTimeLocal": "2025-10-20T08:00:00",
                "duration": 2400,
                # Missing: distance, HR, training effects
            },

            # Similar workouts also with minimal data
            {
                "activityType": {"typeKey": "strength_training"},
                "startTimeLocal": "2025-10-18T08:00:00",
                "duration": 2400,
            },
            {
                "activityType": {"typeKey": "strength_training"},
                "startTimeLocal": "2025-10-16T08:00:00",
                "duration": 2400,
            },
        ]

        recent_workout = analyzer._analyze_most_recent_workout(activities, target_date)
        assert recent_workout is not None
        assert recent_workout["avg_hr"] is None
        assert recent_workout["avg_pace"] is None

        comparison = analyzer._compare_to_recent_similar_workouts(recent_workout, activities)
        assert comparison["similar_workout_count"] == 2
        assert comparison["avg_hr_baseline"] is None
        assert comparison["avg_pace_baseline"] is None

        condition = analyzer._calculate_performance_condition(recent_workout, comparison)
        assert condition == "Normal"  # Defaults to Normal with missing data

        analysis = analyzer._format_recent_workout_analysis(recent_workout, comparison, condition)
        assert "MOST RECENT WORKOUT: Strength Training" in analysis
        assert "PERFORMANCE CONDITION: Normal" in analysis
