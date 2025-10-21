"""Tests for activity detail fetching and caching."""
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.database_models import Activity, ActivityDetail
from app.services.activity_detail_helper import ActivityDetailHelper
from app.services.activity_detail_service import ActivityDetailService


@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_activity(db_session):
    """Create a sample activity record."""
    activity = Activity(
        id=12345678,
        date=datetime.now().date(),
        activity_type="running",
        activity_name="Morning Run",
        duration_seconds=3600,
        distance_meters=10000,
        avg_hr=150,
        start_time=datetime.now()
    )
    db_session.add(activity)
    db_session.commit()
    return activity


@pytest.fixture
def sample_splits_data():
    """Sample splits data from Garmin API."""
    return {
        "lapDTOs": [
            {
                "distance": 1000.0,
                "duration": 300.0,
                "averageHR": 145,
                "maxHR": 152,
                "averageSpeed": 3.33
            },
            {
                "distance": 1000.0,
                "duration": 305.0,
                "averageHR": 148,
                "maxHR": 155,
                "averageSpeed": 3.28
            },
            {
                "distance": 1000.0,
                "duration": 310.0,
                "averageHR": 152,
                "maxHR": 158,
                "averageSpeed": 3.23
            }
        ]
    }


@pytest.fixture
def sample_hr_zones_data():
    """Sample HR zones data from Garmin API."""
    return {
        "timeInZones": [
            {"zone": 1, "duration": 120},
            {"zone": 2, "duration": 600},
            {"zone": 3, "duration": 1200},
            {"zone": 4, "duration": 300},
            {"zone": 5, "duration": 60}
        ]
    }


@pytest.fixture
def sample_weather_data():
    """Sample weather data from Garmin API."""
    return {
        "temperature": 15.0,
        "apparentTemperature": 13.0,
        "humidity": 65,
        "windSpeed": 12.0,
        "weatherCondition": "cloudy"
    }


class TestActivityDetailHelper:
    """Test ActivityDetailHelper class."""

    def test_calculate_pace_consistency_good(self, sample_splits_data):
        """Test pace consistency with consistent pacing."""
        score = ActivityDetailHelper.calculate_pace_consistency(sample_splits_data)
        assert score is not None
        assert 80 <= score <= 100  # Good consistency

    def test_calculate_pace_consistency_poor(self):
        """Test pace consistency with inconsistent pacing."""
        splits_data = {
            "lapDTOs": [
                {"distance": 1000.0, "duration": 300.0},
                {"distance": 1000.0, "duration": 360.0},  # Much slower
                {"distance": 1000.0, "duration": 290.0},  # Much faster
            ]
        }
        score = ActivityDetailHelper.calculate_pace_consistency(splits_data)
        assert score is not None
        assert score < 80  # Poor consistency

    def test_calculate_pace_consistency_insufficient_data(self):
        """Test pace consistency with too few splits."""
        splits_data = {"lapDTOs": [{"distance": 1000.0, "duration": 300.0}]}
        score = ActivityDetailHelper.calculate_pace_consistency(splits_data)
        assert score is None

    def test_calculate_pace_consistency_no_data(self):
        """Test pace consistency with no data."""
        score = ActivityDetailHelper.calculate_pace_consistency(None)
        assert score is None

    def test_calculate_hr_drift_positive(self, sample_splits_data):
        """Test HR drift with increasing heart rate."""
        drift = ActivityDetailHelper.calculate_hr_drift(None, sample_splits_data)
        assert drift is not None
        assert drift > 0  # HR increased from 145 to 152

    def test_calculate_hr_drift_negative(self):
        """Test HR drift with decreasing heart rate."""
        splits_data = {
            "lapDTOs": [
                {"averageHR": 160},
                {"averageHR": 150},
            ]
        }
        drift = ActivityDetailHelper.calculate_hr_drift(None, splits_data)
        assert drift is not None
        assert drift < 0  # HR decreased

    def test_calculate_hr_drift_insufficient_data(self):
        """Test HR drift with too few laps."""
        splits_data = {"lapDTOs": [{"averageHR": 150}]}
        drift = ActivityDetailHelper.calculate_hr_drift(None, splits_data)
        assert drift is None

    def test_should_refetch_none(self):
        """Test should_refetch with no existing record."""
        assert ActivityDetailHelper.should_refetch(None, force=False) is True

    def test_should_refetch_force(self, db_session, sample_activity):
        """Test should_refetch with force flag."""
        detail = ActivityDetail(
            activity_id=sample_activity.id,
            fetched_at=datetime.utcnow(),
            is_complete=True
        )
        assert ActivityDetailHelper.should_refetch(detail, force=True) is True

    def test_should_refetch_incomplete_old(self, db_session, sample_activity):
        """Test should_refetch with incomplete old data."""
        detail = ActivityDetail(
            activity_id=sample_activity.id,
            fetched_at=datetime.utcnow() - timedelta(hours=2),
            is_complete=False
        )
        assert ActivityDetailHelper.should_refetch(detail, force=False) is True

    def test_should_refetch_complete_fresh(self, db_session, sample_activity):
        """Test should_refetch with complete fresh data."""
        detail = ActivityDetail(
            activity_id=sample_activity.id,
            fetched_at=datetime.utcnow(),
            is_complete=True
        )
        assert ActivityDetailHelper.should_refetch(detail, force=False) is False

    def test_create_or_update_new(
        self,
        db_session,
        sample_activity,
        sample_splits_data,
        sample_hr_zones_data,
        sample_weather_data
    ):
        """Test creating new ActivityDetail record."""
        detail = ActivityDetailHelper.create_or_update(
            db_session,
            sample_activity.id,
            sample_splits_data,
            sample_hr_zones_data,
            sample_weather_data,
            []
        )

        assert detail.activity_id == sample_activity.id
        assert detail.splits_data == sample_splits_data
        assert detail.hr_zones_data == sample_hr_zones_data
        assert detail.weather_data == sample_weather_data
        assert detail.is_complete is True
        assert detail.pace_consistency_score is not None
        assert detail.hr_drift_percent is not None

    def test_create_or_update_existing(
        self,
        db_session,
        sample_activity,
        sample_splits_data
    ):
        """Test updating existing ActivityDetail record."""
        # Create initial record
        detail = ActivityDetailHelper.create_or_update(
            db_session,
            sample_activity.id,
            sample_splits_data,
            None,
            None,
            ["hr_zones", "weather"]
        )
        assert detail.is_complete is False

        # Update with complete data
        detail = ActivityDetailHelper.create_or_update(
            db_session,
            sample_activity.id,
            sample_splits_data,
            {"timeInZones": []},
            {"temperature": 20.0},
            []
        )
        assert detail.is_complete is True

    def test_get_cached_detail(self, db_session, sample_activity, sample_splits_data):
        """Test retrieving cached detail."""
        # Create record
        ActivityDetailHelper.create_or_update(
            db_session,
            sample_activity.id,
            sample_splits_data,
            None,
            None,
            []
        )

        # Retrieve it
        cached = ActivityDetailHelper.get_cached_detail(db_session, sample_activity.id)
        assert cached is not None
        assert cached.activity_id == sample_activity.id

    def test_get_cached_detail_not_found(self, db_session):
        """Test retrieving non-existent cached detail."""
        cached = ActivityDetailHelper.get_cached_detail(db_session, 99999)
        assert cached is None


class TestActivityDetailService:
    """Test ActivityDetailService class."""

    @pytest.fixture
    def mock_garmin(self):
        """Create mock GarminService."""
        garmin = Mock()
        return garmin

    @pytest.fixture
    def service(self, mock_garmin, db_session):
        """Create ActivityDetailService instance."""
        return ActivityDetailService(mock_garmin, db_session)

    def test_fetch_and_store_details_success(
        self,
        service,
        mock_garmin,
        db_session,
        sample_activity,
        sample_splits_data,
        sample_hr_zones_data,
        sample_weather_data
    ):
        """Test successful fetch and store."""
        mock_garmin.get_detailed_activity_analysis.return_value = {
            "activity_id": sample_activity.id,
            "splits": sample_splits_data,
            "hr_zones": sample_hr_zones_data,
            "weather": sample_weather_data,
            "is_complete": True,
            "errors": []
        }

        result = service.fetch_and_store_details(sample_activity.id)

        assert result["cached"] is False
        assert result["is_complete"] is True
        assert result["splits"] == sample_splits_data
        assert result["hr_zones"] == sample_hr_zones_data
        assert result["weather"] == sample_weather_data
        assert len(result["errors"]) == 0

        # Verify stored in database
        detail = db_session.query(ActivityDetail).filter_by(
            activity_id=sample_activity.id
        ).first()
        assert detail is not None
        assert detail.is_complete is True

    def test_fetch_and_store_details_partial(
        self,
        service,
        mock_garmin,
        db_session,
        sample_activity,
        sample_splits_data
    ):
        """Test fetch with partial data (some API calls failed)."""
        mock_garmin.get_detailed_activity_analysis.return_value = {
            "activity_id": sample_activity.id,
            "splits": sample_splits_data,
            "hr_zones": None,
            "weather": None,
            "is_complete": False,
            "errors": ["hr_zones", "weather"]
        }

        result = service.fetch_and_store_details(sample_activity.id)

        assert result["cached"] is False
        assert result["is_complete"] is False
        assert result["splits"] is not None
        assert result["hr_zones"] is None
        assert result["weather"] is None
        assert len(result["errors"]) == 2

    def test_fetch_and_store_details_cached(
        self,
        service,
        mock_garmin,
        db_session,
        sample_activity,
        sample_splits_data
    ):
        """Test using cached data."""
        # Create cached record
        ActivityDetailHelper.create_or_update(
            db_session,
            sample_activity.id,
            sample_splits_data,
            {"timeInZones": []},
            {"temperature": 20.0},
            []
        )

        result = service.fetch_and_store_details(sample_activity.id, force_refetch=False)

        assert result["cached"] is True
        assert result["splits"] == sample_splits_data

        # Verify API was not called
        mock_garmin.get_detailed_activity_analysis.assert_not_called()

    def test_fetch_and_store_details_force_refetch(
        self,
        service,
        mock_garmin,
        db_session,
        sample_activity,
        sample_splits_data
    ):
        """Test force refetch ignores cache."""
        # Create cached record
        ActivityDetailHelper.create_or_update(
            db_session,
            sample_activity.id,
            sample_splits_data,
            None,
            None,
            []
        )

        # Mock API response
        mock_garmin.get_detailed_activity_analysis.return_value = {
            "activity_id": sample_activity.id,
            "splits": sample_splits_data,
            "hr_zones": {"timeInZones": []},
            "weather": {"temperature": 20.0},
            "is_complete": True,
            "errors": []
        }

        result = service.fetch_and_store_details(sample_activity.id, force_refetch=True)

        assert result["cached"] is False
        mock_garmin.get_detailed_activity_analysis.assert_called_once()

    def test_get_cached_details_exists(
        self,
        service,
        db_session,
        sample_activity,
        sample_splits_data
    ):
        """Test getting cached details when they exist."""
        # Create cached record
        ActivityDetailHelper.create_or_update(
            db_session,
            sample_activity.id,
            sample_splits_data,
            None,
            None,
            []
        )

        result = service.get_cached_details(sample_activity.id)

        assert result is not None
        assert result["activity_id"] == sample_activity.id
        assert result["splits"] == sample_splits_data

    def test_get_cached_details_not_exists(self, service, db_session):
        """Test getting cached details when they don't exist."""
        result = service.get_cached_details(99999)
        assert result is None

    def test_bulk_fetch_recent_activities(
        self,
        service,
        mock_garmin,
        db_session,
        sample_splits_data
    ):
        """Test bulk fetching multiple activities."""
        # Create test activities
        activities = []
        for i in range(5):
            activity = Activity(
                id=12345000 + i,
                date=datetime.now().date(),
                activity_type="running",
                duration_seconds=3600,
                start_time=datetime.now()
            )
            db_session.add(activity)
            activities.append(activity)
        db_session.commit()

        # Mock API responses
        mock_garmin.get_detailed_activity_analysis.return_value = {
            "activity_id": 0,
            "splits": sample_splits_data,
            "hr_zones": {"timeInZones": []},
            "weather": {"temperature": 20.0},
            "is_complete": True,
            "errors": []
        }

        activity_ids = [a.id for a in activities]
        result = service.bulk_fetch_recent_activities(activity_ids, limit=10)

        assert result["total"] == 5
        assert result["fetched"] == 5
        assert result["cached"] == 0
        assert result["failed"] == 0
        assert result["skipped"] == 0

    def test_bulk_fetch_with_limit(
        self,
        service,
        mock_garmin,
        db_session,
        sample_splits_data
    ):
        """Test bulk fetch respects limit."""
        # Create 10 activities
        activities = []
        for i in range(10):
            activity = Activity(
                id=12345000 + i,
                date=datetime.now().date(),
                activity_type="running",
                duration_seconds=3600,
                start_time=datetime.now()
            )
            db_session.add(activity)
            activities.append(activity)
        db_session.commit()

        mock_garmin.get_detailed_activity_analysis.return_value = {
            "activity_id": 0,
            "splits": sample_splits_data,
            "hr_zones": None,
            "weather": None,
            "is_complete": False,
            "errors": ["hr_zones", "weather"]
        }

        activity_ids = [a.id for a in activities]
        result = service.bulk_fetch_recent_activities(activity_ids, limit=3)

        assert result["total"] == 10
        assert result["fetched"] == 3
        assert result["skipped"] == 7
