"""Tests for HR zone calculation."""

import pytest

from app.services.hr_zones import (
    calculate_hr_zones,
    calculate_max_hr_from_age,
    format_hr_zones_for_prompt,
)


class TestMaxHRCalculation:
    """Test maximum heart rate calculation from age."""

    def test_calculate_max_hr_from_age(self):
        """Test standard max HR formula."""
        assert calculate_max_hr_from_age(30) == 190
        assert calculate_max_hr_from_age(40) == 180
        assert calculate_max_hr_from_age(25) == 195


class TestHRZoneCalculation:
    """Test HR zone calculation."""

    def test_lthr_based_zones(self):
        """Test zones calculated from lactate threshold."""
        zones = calculate_hr_zones(lactate_threshold_hr=160, max_hr=190)

        assert zones is not None
        assert len(zones) == 5

        # Check zone 1 structure
        assert "zone_1" in zones
        assert zones["zone_1"]["name"] == "Recovery"
        assert zones["zone_1"]["min"] == 80  # 50% of 160
        assert zones["zone_1"]["max"] == 136  # 85% of 160

        # Check zone 2
        assert zones["zone_2"]["min"] == 136  # 85% of 160
        assert zones["zone_2"]["max"] == 142  # 89% of 160

        # Check zone 4
        assert zones["zone_4"]["min"] == 152  # 95% of 160
        assert zones["zone_4"]["max"] == 168  # 105% of 160

        # Check zone 5 uses max_hr
        assert zones["zone_5"]["min"] == 168  # 105% of 160
        assert zones["zone_5"]["max"] == 190  # max_hr

    def test_age_based_zones_fallback(self):
        """Test fallback to age-based zones when LTHR unavailable."""
        zones = calculate_hr_zones(lactate_threshold_hr=None, age=30)

        assert zones is not None
        assert len(zones) == 5

        # Max HR should be 220 - 30 = 190
        # Zone 1: 50-60% of 190 = 95-114
        assert zones["zone_1"]["min"] == 95
        assert zones["zone_1"]["max"] == 114

        # Zone 2: 60-70% of 190 = 114-133
        assert zones["zone_2"]["min"] == 114
        assert zones["zone_2"]["max"] == 133

        # Zone 5: 90-100% of 190 = 171-190
        assert zones["zone_5"]["min"] == 171
        assert zones["zone_5"]["max"] == 190

    def test_lthr_with_age(self):
        """Test that LTHR takes precedence over age."""
        zones_lthr = calculate_hr_zones(lactate_threshold_hr=160, age=30)
        zones_age = calculate_hr_zones(lactate_threshold_hr=None, age=30)

        # LTHR zones should be different from age-based zones
        assert zones_lthr["zone_2"]["min"] != zones_age["zone_2"]["min"]
        assert zones_lthr["zone_2"]["max"] != zones_age["zone_2"]["max"]

    def test_no_data_raises_error(self):
        """Test that missing all data raises ValueError."""
        with pytest.raises(ValueError, match="Must provide either"):
            calculate_hr_zones(lactate_threshold_hr=None, max_hr=None, age=None)

    def test_zone_descriptions_present(self):
        """Test that all zones have required fields."""
        zones = calculate_hr_zones(lactate_threshold_hr=160, max_hr=190)

        for zone_key in ["zone_1", "zone_2", "zone_3", "zone_4", "zone_5"]:
            assert zone_key in zones
            zone = zones[zone_key]
            assert "min" in zone
            assert "max" in zone
            assert "name" in zone
            assert "description" in zone
            assert "effort" in zone


class TestHRZoneFormatting:
    """Test HR zone formatting for AI prompts."""

    def test_format_hr_zones_for_prompt(self):
        """Test formatting zones for AI prompt."""
        zones = calculate_hr_zones(lactate_threshold_hr=160, max_hr=190)
        formatted = format_hr_zones_for_prompt(zones)

        # Check format
        assert "Zone 1 (Recovery): 80-136 bpm" in formatted
        assert "Zone 2 (Aerobic): 136-142 bpm" in formatted
        assert "Zone 3 (Tempo): 144-150 bpm" in formatted
        assert "Zone 4 (Threshold): 152-168 bpm" in formatted
        assert "Zone 5 (VO2 Max): 168-190 bpm" in formatted

        # Check descriptions included
        assert "Easy aerobic, recovery runs" in formatted
        assert "Base building, long runs" in formatted
        assert "Lactate threshold training" in formatted

    def test_format_age_based_zones(self):
        """Test formatting age-based zones."""
        zones = calculate_hr_zones(lactate_threshold_hr=None, age=30)
        formatted = format_hr_zones_for_prompt(zones)

        # Should still produce formatted output
        assert "Zone 1 (Recovery)" in formatted
        assert "bpm" in formatted
        assert len(formatted.split("\n")) == 5  # 5 zones


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_low_lthr(self):
        """Test with unusually low LTHR."""
        zones = calculate_hr_zones(lactate_threshold_hr=120, max_hr=170)

        # Should still calculate valid zones
        assert zones["zone_1"]["min"] == 60  # 50% of 120
        assert zones["zone_1"]["max"] == 102  # 85% of 120
        assert zones["zone_5"]["max"] == 170  # max_hr

    def test_very_high_lthr(self):
        """Test with unusually high LTHR."""
        zones = calculate_hr_zones(lactate_threshold_hr=180, max_hr=200)

        # Should still calculate valid zones
        assert zones["zone_4"]["min"] == 171  # 95% of 180
        assert zones["zone_4"]["max"] == 189  # 105% of 180
        assert zones["zone_5"]["max"] == 200  # max_hr

    def test_lthr_close_to_max_hr(self):
        """Test when LTHR is very close to max HR - should fallback to age-based."""
        # LTHR at 185 is >95% of 190, should trigger fallback
        zones = calculate_hr_zones(lactate_threshold_hr=185, max_hr=190, age=30)

        # Should use age-based zones instead (max_hr=190 from age 30)
        # Zone 1: 50-60% of 190 = 95-114
        assert zones["zone_1"]["min"] == 95
        assert zones["zone_1"]["max"] == 114

        # Zone 5: 90-100% of 190 = 171-190
        assert zones["zone_5"]["min"] == 171
        assert zones["zone_5"]["max"] == 190


class TestCriticalIssueFixes:
    """Tests for the 3 critical issues identified in code review."""

    def test_issue1_lthr_exceeds_max_hr_falls_back(self, caplog):
        """Issue #1: LTHR > max HR should fallback with warning."""
        import logging
        caplog.set_level(logging.WARNING)

        # LTHR = 195 is >95% of max HR = 200 (threshold is 0.95)
        zones = calculate_hr_zones(lactate_threshold_hr=195, max_hr=200, age=30)

        # Should fallback to age-based zones using provided max_hr=200
        # (not recalculated from age since max_hr was provided)
        assert zones["zone_1"]["min"] == 100  # 50% of 200
        assert zones["zone_1"]["max"] == 120  # 60% of 200

        # Should log warning
        assert "too close to or exceeds max HR" in caplog.text
        assert "Falling back to age-based zones" in caplog.text

    def test_issue1_lthr_equal_to_max_hr_falls_back(self, caplog):
        """Issue #1: LTHR == max HR should fallback with warning."""
        import logging
        caplog.set_level(logging.WARNING)

        zones = calculate_hr_zones(lactate_threshold_hr=190, max_hr=190, age=30)

        # Should fallback to age-based zones
        assert zones["zone_1"]["min"] == 95
        assert zones["zone_5"]["max"] == 190

        assert "too close to or exceeds max HR" in caplog.text

    def test_issue2_negative_lthr_falls_back(self, caplog):
        """Issue #2: Negative LTHR should fallback with warning."""
        import logging
        caplog.set_level(logging.WARNING)

        zones = calculate_hr_zones(lactate_threshold_hr=-10, max_hr=190, age=30)

        # Should fallback to age-based zones
        assert zones["zone_1"]["min"] == 95
        assert zones["zone_5"]["max"] == 190

        # Should log warning
        assert "Invalid LTHR value" in caplog.text
        assert "must be positive" in caplog.text

    def test_issue2_zero_lthr_falls_back(self, caplog):
        """Issue #2: Zero LTHR should fallback with warning."""
        import logging
        caplog.set_level(logging.WARNING)

        zones = calculate_hr_zones(lactate_threshold_hr=0, max_hr=190, age=30)

        # Should fallback to age-based zones
        assert zones["zone_1"]["min"] == 95
        assert zones["zone_5"]["max"] == 190

        assert "Invalid LTHR value" in caplog.text

    def test_lthr_outside_normal_range_warns_but_continues(self, caplog):
        """Issue #1/#2: LTHR outside 80-200 range should warn but still calculate."""
        import logging
        caplog.set_level(logging.WARNING)

        # Test low boundary (75 < 80)
        zones_low = calculate_hr_zones(lactate_threshold_hr=75, max_hr=150)
        assert zones_low["zone_1"]["min"] == 38  # 50% of 75
        assert "outside normal range (80-200 bpm)" in caplog.text

        caplog.clear()

        # Test high boundary (205 > 200)
        zones_high = calculate_hr_zones(lactate_threshold_hr=205, max_hr=220)
        assert zones_high["zone_4"]["min"] == 195  # 95% of 205
        assert "outside normal range (80-200 bpm)" in caplog.text

    def test_invalid_age_raises_error(self):
        """Test that invalid age raises ValueError."""
        # Age too low
        with pytest.raises(ValueError, match="Age .* outside valid range"):
            calculate_hr_zones(lactate_threshold_hr=None, age=5)

        # Age too high
        with pytest.raises(ValueError, match="Age .* outside valid range"):
            calculate_hr_zones(lactate_threshold_hr=None, age=120)

    def test_valid_age_boundaries(self):
        """Test that boundary ages (10 and 100) are accepted."""
        # Age 10 should work
        zones_young = calculate_hr_zones(lactate_threshold_hr=None, age=10)
        assert zones_young["zone_5"]["max"] == 210  # 220 - 10

        # Age 100 should work
        zones_old = calculate_hr_zones(lactate_threshold_hr=None, age=100)
        assert zones_old["zone_5"]["max"] == 120  # 220 - 100

    def test_lthr_just_below_threshold_uses_lthr(self):
        """Test LTHR just below 95% threshold uses LTHR-based zones."""
        # LTHR = 179 is 94.2% of max HR = 190 (below 0.95 threshold)
        zones = calculate_hr_zones(lactate_threshold_hr=179, max_hr=190)

        # Should use LTHR-based zones
        assert zones["zone_1"]["min"] == 90  # 50% of 179
        assert zones["zone_1"]["max"] == 152  # 85% of 179
        assert zones["zone_5"]["max"] == 190  # max_hr
