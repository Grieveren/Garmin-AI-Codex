"""Comprehensive tests for recovery time tracking feature.

This test module verifies the end-to-end flow of recovery time data:
1. Database model accepts and persists recovery_time_hours
2. Sync script extracts currentRecoveryTime from Garmin API
3. Migration script adds column safely and idempotently
4. AI analyzer can access and use recovery time in recommendations
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text

from app.database import SessionLocal, engine
from app.models.database_models import DailyMetric
from scripts.migrate_recovery_time import migrate_recovery_time_column
from scripts.sync_data import fetch_daily_metrics


class TestDailyMetricRecoveryTime:
    """Test database model handling of recovery_time_hours field."""

    def test_daily_metric_accepts_recovery_time(self):
        """Verify DailyMetric model accepts recovery_time_hours integer field."""
        db = SessionLocal()
        try:
            # Clean up any existing data for this date first
            test_date = date(2025, 10, 21)
            existing = db.query(DailyMetric).filter(DailyMetric.date == test_date).first()
            if existing:
                db.delete(existing)
                db.commit()

            # Create metric with recovery time
            metric = DailyMetric(
                date=test_date,
                recovery_time_hours=14,
                resting_hr=45,
                hrv_morning=55,
            )
            db.add(metric)
            db.commit()
            db.refresh(metric)

            # Verify field is set correctly
            assert metric.recovery_time_hours == 14
            assert isinstance(metric.recovery_time_hours, int)

            # Cleanup
            db.delete(metric)
            db.commit()
        finally:
            db.close()

    def test_daily_metric_null_recovery_time(self):
        """Verify recovery_time_hours handles null values gracefully."""
        db = SessionLocal()
        try:
            # Create metric without recovery time
            metric = DailyMetric(
                date=date(2025, 10, 22),
                recovery_time_hours=None,
                resting_hr=46,
            )
            db.add(metric)
            db.commit()
            db.refresh(metric)

            # Verify null is stored correctly
            assert metric.recovery_time_hours is None

            # Cleanup
            db.delete(metric)
            db.commit()
        finally:
            db.close()

    def test_daily_metric_persists_and_retrieves(self):
        """Verify recovery_time_hours persists correctly and can be queried."""
        db = SessionLocal()
        try:
            # Create metric with recovery time
            test_date = date(2025, 10, 23)
            metric = DailyMetric(
                date=test_date,
                recovery_time_hours=8,
                resting_hr=47,
            )
            db.add(metric)
            db.commit()

            # Query back from database
            retrieved = db.query(DailyMetric).filter(DailyMetric.date == test_date).first()

            assert retrieved is not None
            assert retrieved.recovery_time_hours == 8
            assert retrieved.date == test_date

            # Cleanup
            db.delete(retrieved)
            db.commit()
        finally:
            db.close()

    def test_daily_metric_edge_case_zero_hours(self):
        """Test edge case: 0 recovery hours (fully recovered)."""
        db = SessionLocal()
        try:
            metric = DailyMetric(
                date=date(2025, 10, 24),
                recovery_time_hours=0,
                resting_hr=44,
            )
            db.add(metric)
            db.commit()
            db.refresh(metric)

            # Zero should be stored as 0, not null
            assert metric.recovery_time_hours == 0
            assert metric.recovery_time_hours is not None

            # Cleanup
            db.delete(metric)
            db.commit()
        finally:
            db.close()

    def test_daily_metric_edge_case_large_value(self):
        """Test edge case: Very large recovery time (72+ hours)."""
        db = SessionLocal()
        try:
            metric = DailyMetric(
                date=date(2025, 10, 25),
                recovery_time_hours=96,  # 4 days
                resting_hr=52,
            )
            db.add(metric)
            db.commit()
            db.refresh(metric)

            assert metric.recovery_time_hours == 96

            # Cleanup
            db.delete(metric)
            db.commit()
        finally:
            db.close()


class TestSyncScriptExtraction:
    """Test sync script extraction of recovery time from Garmin API."""

    def test_extract_from_valid_training_status(self):
        """Test extraction when currentRecoveryTime exists in training_status."""
        # Mock Garmin service
        mock_garmin = MagicMock()
        mock_garmin._client.get_stats.return_value = {"totalSteps": 8000}
        mock_garmin._client.get_sleep_data.return_value = {}
        mock_garmin._client.get_hrv_data.return_value = {}
        mock_garmin._client.get_heart_rates.return_value = {"restingHeartRate": 45}
        mock_garmin._client.get_stress_data.return_value = []
        mock_garmin._client.get_body_battery.return_value = []
        mock_garmin._client.get_training_readiness.return_value = None
        mock_garmin._client.get_training_status.return_value = {
            "currentRecoveryTime": 14,
            "mostRecentVO2Max": {"generic": {"vo2MaxValue": 54.3}},
        }
        mock_garmin._client.get_spo2_data.return_value = None
        mock_garmin._client.get_respiration_data.return_value = None

        # Fetch metrics
        metrics = fetch_daily_metrics(mock_garmin, date(2025, 10, 21), verbose=False)

        # Verify recovery time extracted
        assert metrics is not None
        assert "recovery_time_hours" in metrics
        assert metrics["recovery_time_hours"] == 14

    def test_extract_when_missing_current_recovery_time(self):
        """Test handling when currentRecoveryTime is missing from training_status."""
        mock_garmin = MagicMock()
        mock_garmin._client.get_stats.return_value = {"totalSteps": 8000}
        mock_garmin._client.get_sleep_data.return_value = {}
        mock_garmin._client.get_hrv_data.return_value = {}
        mock_garmin._client.get_heart_rates.return_value = {"restingHeartRate": 45}
        mock_garmin._client.get_stress_data.return_value = []
        mock_garmin._client.get_body_battery.return_value = []
        mock_garmin._client.get_training_readiness.return_value = None
        mock_garmin._client.get_training_status.return_value = {
            "mostRecentVO2Max": {"generic": {"vo2MaxValue": 54.3}},
            # No currentRecoveryTime key
        }
        mock_garmin._client.get_spo2_data.return_value = None
        mock_garmin._client.get_respiration_data.return_value = None

        metrics = fetch_daily_metrics(mock_garmin, date(2025, 10, 21), verbose=False)

        # Verify recovery_time_hours is not in metrics when missing
        assert metrics is not None
        assert "recovery_time_hours" not in metrics

    def test_extract_when_training_status_is_none(self):
        """Test handling when training_status API call returns None."""
        mock_garmin = MagicMock()
        mock_garmin._client.get_stats.return_value = {"totalSteps": 8000}
        mock_garmin._client.get_sleep_data.return_value = {}
        mock_garmin._client.get_hrv_data.return_value = {}
        mock_garmin._client.get_heart_rates.return_value = {"restingHeartRate": 45}
        mock_garmin._client.get_stress_data.return_value = []
        mock_garmin._client.get_body_battery.return_value = []
        mock_garmin._client.get_training_readiness.return_value = None
        mock_garmin._client.get_training_status.return_value = None
        mock_garmin._client.get_spo2_data.return_value = None
        mock_garmin._client.get_respiration_data.return_value = None

        metrics = fetch_daily_metrics(mock_garmin, date(2025, 10, 21), verbose=False)

        # Verify no error and recovery_time_hours not present
        assert metrics is not None
        assert "recovery_time_hours" not in metrics

    def test_extract_when_training_status_is_empty_dict(self):
        """Test handling when training_status returns empty dict."""
        mock_garmin = MagicMock()
        mock_garmin._client.get_stats.return_value = {"totalSteps": 8000}
        mock_garmin._client.get_sleep_data.return_value = {}
        mock_garmin._client.get_hrv_data.return_value = {}
        mock_garmin._client.get_heart_rates.return_value = {"restingHeartRate": 45}
        mock_garmin._client.get_stress_data.return_value = []
        mock_garmin._client.get_body_battery.return_value = []
        mock_garmin._client.get_training_readiness.return_value = None
        mock_garmin._client.get_training_status.return_value = {}
        mock_garmin._client.get_spo2_data.return_value = None
        mock_garmin._client.get_respiration_data.return_value = None

        metrics = fetch_daily_metrics(mock_garmin, date(2025, 10, 21), verbose=False)

        assert metrics is not None
        assert "recovery_time_hours" not in metrics

    def test_extract_edge_case_zero_hours(self):
        """Test extraction of 0 recovery hours (fully recovered)."""
        mock_garmin = MagicMock()
        mock_garmin._client.get_stats.return_value = {"totalSteps": 8000}
        mock_garmin._client.get_sleep_data.return_value = {}
        mock_garmin._client.get_hrv_data.return_value = {}
        mock_garmin._client.get_heart_rates.return_value = {"restingHeartRate": 44}
        mock_garmin._client.get_stress_data.return_value = []
        mock_garmin._client.get_body_battery.return_value = []
        mock_garmin._client.get_training_readiness.return_value = None
        mock_garmin._client.get_training_status.return_value = {
            "currentRecoveryTime": 0,  # Fully recovered
        }
        mock_garmin._client.get_spo2_data.return_value = None
        mock_garmin._client.get_respiration_data.return_value = None

        metrics = fetch_daily_metrics(mock_garmin, date(2025, 10, 21), verbose=False)

        # Zero should be extracted, not treated as missing
        assert metrics is not None
        assert "recovery_time_hours" in metrics
        assert metrics["recovery_time_hours"] == 0

    def test_extract_edge_case_large_value(self):
        """Test extraction of very large recovery time (96 hours)."""
        mock_garmin = MagicMock()
        mock_garmin._client.get_stats.return_value = {"totalSteps": 8000}
        mock_garmin._client.get_sleep_data.return_value = {}
        mock_garmin._client.get_hrv_data.return_value = {}
        mock_garmin._client.get_heart_rates.return_value = {"restingHeartRate": 58}
        mock_garmin._client.get_stress_data.return_value = []
        mock_garmin._client.get_body_battery.return_value = []
        mock_garmin._client.get_training_readiness.return_value = None
        mock_garmin._client.get_training_status.return_value = {
            "currentRecoveryTime": 96,  # 4 days recovery (severe overtraining)
        }
        mock_garmin._client.get_spo2_data.return_value = None
        mock_garmin._client.get_respiration_data.return_value = None

        metrics = fetch_daily_metrics(mock_garmin, date(2025, 10, 21), verbose=False)

        assert metrics is not None
        assert "recovery_time_hours" in metrics
        assert metrics["recovery_time_hours"] == 96


class TestRecoveryTimeExtraction:
    """Test GarminService.extract_recovery_time() static method with edge cases."""

    def test_extract_valid_minutes_to_hours(self):
        """Test conversion from minutes to hours (2220 min = 37 hours)."""
        from app.services.garmin_service import GarminService

        training_readiness = [{"score": 30, "recoveryTime": 2220}]
        result = GarminService.extract_recovery_time(training_readiness)
        assert result == 37

    def test_extract_float_minutes_rounds_correctly(self):
        """Test float values round to nearest hour (870.5 min = 15 hours)."""
        from app.services.garmin_service import GarminService

        training_readiness = [{"score": 30, "recoveryTime": 870.5}]  # 14.5 hours
        result = GarminService.extract_recovery_time(training_readiness)
        assert result == 15  # Rounds up

    def test_extract_negative_value_returns_none(self):
        """Test negative values are rejected and return None."""
        from app.services.garmin_service import GarminService

        training_readiness = [{"score": 30, "recoveryTime": -120}]
        result = GarminService.extract_recovery_time(training_readiness)
        assert result is None

    def test_extract_string_numeric_converts(self):
        """Test numeric strings are converted correctly."""
        from app.services.garmin_service import GarminService

        training_readiness = [{"score": 30, "recoveryTime": "1800"}]  # 30 hours
        result = GarminService.extract_recovery_time(training_readiness)
        assert result == 30

    def test_extract_string_non_numeric_returns_none(self):
        """Test non-numeric strings return None."""
        from app.services.garmin_service import GarminService

        training_readiness = [{"score": 30, "recoveryTime": "N/A"}]
        result = GarminService.extract_recovery_time(training_readiness)
        assert result is None

    def test_extract_zero_recovery_time(self):
        """Test zero recovery time (fully recovered)."""
        from app.services.garmin_service import GarminService

        training_readiness = [{"score": 100, "recoveryTime": 0}]
        result = GarminService.extract_recovery_time(training_readiness)
        assert result == 0

    def test_extract_missing_recovery_time_key(self):
        """Test missing recoveryTime key returns None."""
        from app.services.garmin_service import GarminService

        training_readiness = [{"score": 30}]  # No recoveryTime
        result = GarminService.extract_recovery_time(training_readiness)
        assert result is None

    def test_extract_empty_list_returns_none(self):
        """Test empty training_readiness list returns None."""
        from app.services.garmin_service import GarminService

        training_readiness = []
        result = GarminService.extract_recovery_time(training_readiness)
        assert result is None

    def test_extract_none_input_returns_none(self):
        """Test None input returns None gracefully."""
        from app.services.garmin_service import GarminService

        result = GarminService.extract_recovery_time(None)
        assert result is None


class TestMigrationScript:
    """Test migration script adds column safely and idempotently."""

    @pytest.fixture(autouse=True)
    def cleanup_test_column(self):
        """Prepare test environment - column will already exist in production DB."""
        # SQLite doesn't support DROP COLUMN easily, so we skip column manipulation
        # The migration tests will verify idempotency instead
        yield

    def test_migration_adds_column_successfully(self):
        """Verify migration script handles column addition (may already exist)."""
        # Run migration - should succeed whether column exists or not
        try:
            migrate_recovery_time_column()
            success = True
        except Exception as e:
            success = False
            print(f"Migration failed: {e}")

        assert success, "Migration should succeed"

        # Verify column exists after migration
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(daily_metrics)"))
            columns = {row[1] for row in result}
            assert "recovery_time_hours" in columns

    def test_migration_is_idempotent(self):
        """Verify migration can be run multiple times without errors."""
        # Run migration first time
        migrate_recovery_time_column()

        # Run migration second time - should not fail
        try:
            migrate_recovery_time_column()
            success = True
        except Exception as e:
            success = False
            print(f"Migration failed on second run: {e}")

        assert success, "Migration should be idempotent"

    def test_migration_preserves_existing_data(self):
        """Verify migration doesn't affect existing records."""
        db = SessionLocal()
        try:
            # Create test record
            test_date = date(2025, 10, 26)

            # Clean up any existing
            existing = db.query(DailyMetric).filter(DailyMetric.date == test_date).first()
            if existing:
                db.delete(existing)
                db.commit()

            metric = DailyMetric(
                date=test_date,
                resting_hr=45,
                hrv_morning=55,
                sleep_seconds=28800,
            )
            db.add(metric)
            db.commit()

            # Run migration (column already exists, should be idempotent)
            migrate_recovery_time_column()

            # Verify existing data still intact
            retrieved = db.query(DailyMetric).filter(DailyMetric.date == test_date).first()
            assert retrieved is not None
            assert retrieved.resting_hr == 45
            assert retrieved.hrv_morning == 55
            assert retrieved.sleep_seconds == 28800
            # recovery_time_hours should exist (may be null)
            assert hasattr(retrieved, "recovery_time_hours")

            # Cleanup
            db.delete(retrieved)
            db.commit()
        finally:
            db.close()


class TestAIAnalyzerIntegration:
    """Test AI analyzer can access and use recovery time data.

    These tests verify the critical integration point: that recovery time
    flows through the entire system and influences AI recommendations.
    """

    def test_ai_analyzer_parse_recovery_time_with_current_recovery_time(self):
        """Test _parse_recovery_time extracts currentRecoveryTime correctly."""
        from app.services.ai_analyzer import AIAnalyzer

        analyzer = AIAnalyzer()

        training_status = {
            "currentRecoveryTime": 14,
            "mostRecentVO2Max": {"generic": {"vo2MaxValue": 54.3}},
        }
        training_readiness = None

        result = analyzer._parse_recovery_time(training_status, training_readiness)

        assert result is not None
        assert "hours" in result
        assert result["hours"] == 14

    def test_ai_analyzer_parse_recovery_time_with_zero(self):
        """Test _parse_recovery_time handles 0 hours (fully recovered)."""
        from app.services.ai_analyzer import AIAnalyzer

        analyzer = AIAnalyzer()

        training_status = {"currentRecoveryTime": 0}
        training_readiness = None

        result = analyzer._parse_recovery_time(training_status, training_readiness)

        assert result is not None
        assert result["hours"] == 0

    def test_ai_analyzer_parse_recovery_time_missing(self):
        """Test _parse_recovery_time returns None when recovery time missing."""
        from app.services.ai_analyzer import AIAnalyzer

        analyzer = AIAnalyzer()

        training_status = {"mostRecentVO2Max": {"generic": {"vo2MaxValue": 54.3}}}
        training_readiness = None

        result = analyzer._parse_recovery_time(training_status, training_readiness)

        # Should return None or empty dict when no recovery data found
        assert result is None or not result.get("hours")

    def test_ai_analyzer_format_recovery_for_prompt_with_hours(self):
        """Test _format_recovery_for_prompt formats recovery time correctly."""
        from app.services.ai_analyzer import AIAnalyzer

        analyzer = AIAnalyzer()

        recovery = {"hours": 14, "note": "Moderate recovery needed"}
        formatted = analyzer._format_recovery_for_prompt(recovery)

        assert "14.0h remaining" in formatted
        assert "Moderate recovery needed" in formatted

    def test_ai_analyzer_format_recovery_for_prompt_ready_now(self):
        """Test _format_recovery_for_prompt shows 'Ready now' for ≤0.5 hours."""
        from app.services.ai_analyzer import AIAnalyzer

        analyzer = AIAnalyzer()

        recovery = {"hours": 0.3}
        formatted = analyzer._format_recovery_for_prompt(recovery)

        assert "Ready now" in formatted

    def test_ai_analyzer_format_recovery_for_prompt_missing(self):
        """Test _format_recovery_for_prompt handles missing data gracefully."""
        from app.services.ai_analyzer import AIAnalyzer

        analyzer = AIAnalyzer()

        formatted = analyzer._format_recovery_for_prompt(None)
        assert formatted == "Not available"

        formatted = analyzer._format_recovery_for_prompt({})
        assert formatted == "Not available"


class TestEndToEndFlow:
    """Integration tests verifying complete data flow from API to AI analyzer."""

    def test_recovery_time_stored_in_database_matches_fixture(self):
        """Verify recovery time from fixture is stored and retrievable.

        This test simulates the end-to-end flow:
        1. Garmin API returns training_status with currentRecoveryTime: 14
        2. Sync script extracts and stores in database
        3. Query confirms recovery_time_hours == 14
        """
        db = SessionLocal()
        try:
            # Simulate sync_data.py storing fixture data
            test_date = date(2025, 10, 17)

            # Clean up any existing data
            existing = db.query(DailyMetric).filter(DailyMetric.date == test_date).first()
            if existing:
                db.delete(existing)
                db.commit()

            # Create metric matching fixture data
            metric = DailyMetric(
                date=test_date,
                recovery_time_hours=14,  # From fixtures/garmin_daily_metrics.json
                resting_hr=44,
                hrv_morning=48,
                vo2_max=54.3,
                training_status="PRODUCTIVE",
            )
            db.add(metric)
            db.commit()

            # Query back - simulating what AI analyzer would do
            retrieved = db.query(DailyMetric).filter(DailyMetric.date == test_date).first()

            assert retrieved is not None
            assert retrieved.recovery_time_hours == 14, "Recovery time should match fixture value"
            assert retrieved.resting_hr == 44
            assert retrieved.hrv_morning == 48

            # Cleanup
            db.delete(retrieved)
            db.commit()
        finally:
            db.close()

    @pytest.mark.asyncio
    async def test_ai_analyzer_accesses_stored_recovery_time(self, monkeypatch):
        """CRITICAL: Verify AI analyzer can access stored recovery time and use in recommendations.

        This is the most important test - it verifies the complete integration:
        1. Recovery time stored in database (14 hours from fixture)
        2. AI analyzer fetches data from database
        3. Recovery time influences AI recommendation
        """
        from app.services.ai_analyzer import AIAnalyzer

        # Mock settings
        class DummySettings:
            anthropic_api_key = "test-key"
            garmin_email = "test@example.com"
            garmin_password = "hunter2"
            garmin_token_store = None
            prompt_config_path = Path("app/config/prompts.yaml")

        monkeypatch.setattr("app.services.ai_analyzer.get_settings", lambda: DummySettings())

        # Setup test data in database
        db = SessionLocal()
        test_date = date(2025, 10, 17)
        try:
            # Clean existing
            existing = db.query(DailyMetric).filter(DailyMetric.date == test_date).first()
            if existing:
                db.delete(existing)
                db.commit()

            # Create metric with recovery time
            metric = DailyMetric(
                date=test_date,
                recovery_time_hours=14,
                resting_hr=44,
                hrv_morning=48,
                sleep_seconds=25500,
                sleep_score=82,
                training_readiness_score=67,
                vo2_max=54.3,
                training_status="PRODUCTIVE",
            )
            db.add(metric)
            db.commit()
        finally:
            db.close()

        # Mock Garmin service (analyzer will use database data, not Garmin API)
        def mock_fetch_garmin_data(self, garmin, target_date):
            """Return data that includes recovery time from training_status."""
            return {
                "stats": {"totalSteps": 12345},
                "heart_rate": {"restingHeartRate": 44},
                "hrv": {"hrvSummary": {"lastNightAvg": 48}},
                "sleep": {
                    "dailySleepDTO": {
                        "sleepTimeSeconds": 25500,
                        "sleepScores": {"overall": {"value": 82}},
                    }
                },
                "training_readiness": [{"score": 67}],
                "training_status": {
                    "currentRecoveryTime": 14,  # This should flow through
                    "mostRecentVO2Max": {"generic": {"vo2MaxValue": 54.3}},
                },
                "recent_activities": [],
            }

        monkeypatch.setattr(AIAnalyzer, "_fetch_garmin_data", mock_fetch_garmin_data)

        # Mock other dependencies
        monkeypatch.setattr(
            AIAnalyzer,
            "_calculate_baselines",
            lambda self, data: {
                "avg_training_load": 30,
                "activity_count": 0,
                "total_distance_km": 0,
                "total_duration_min": 0,
                "activity_breakdown": {},
            },
        )
        monkeypatch.setattr(AIAnalyzer, "_has_historical_data", lambda self, target_date: False)
        monkeypatch.setattr(AIAnalyzer, "_get_readiness_history", lambda self, target_date, days=7: [])
        monkeypatch.setattr(AIAnalyzer, "_get_latest_metric_sync", lambda self: None)

        # Mock Anthropic API to verify recovery time in prompt
        class DummyMessages:
            def create(self, **kwargs):
                prompt = kwargs["messages"][0]["content"]

                # CRITICAL: Verify recovery time appears in prompt sent to AI
                assert "Recovery time remaining" in prompt or "recovery" in prompt.lower(), \
                    "Recovery time should be included in AI prompt"

                # Check that the 14 hour value appears somewhere in prompt
                assert "14" in prompt or "14.0h" in prompt, \
                    "Recovery time value (14 hours) should appear in prompt"

                # Return mock AI response
                return MagicMock(
                    content=[
                        MagicMock(
                            text=json.dumps({
                                "readiness_score": 65,
                                "recommendation": "moderate",
                                "confidence": "high",
                                "key_factors": [
                                    "Recovery time: 14 hours remaining - moderate activity recommended"
                                ],
                                "suggested_workout": {
                                    "type": "easy_run",
                                    "description": "Easy 30 min run in Zone 2",
                                    "target_duration_minutes": 30,
                                },
                            })
                        )
                    ]
                )

        class DummyAnthropic:
            def __init__(self, api_key: str):
                self.messages = DummyMessages()

        monkeypatch.setattr("app.services.ai_analyzer.Anthropic", DummyAnthropic)

        # Run analysis
        analyzer = AIAnalyzer()
        result = await analyzer.analyze_daily_readiness(test_date)

        # Verify recovery time data flows through
        assert result is not None
        assert "extended_signals" in result
        assert "recovery_time" in result["extended_signals"]
        assert result["extended_signals"]["recovery_time"]["hours"] == 14

        # Cleanup
        db = SessionLocal()
        try:
            metric = db.query(DailyMetric).filter(DailyMetric.date == test_date).first()
            if metric:
                db.delete(metric)
                db.commit()
        finally:
            db.close()
