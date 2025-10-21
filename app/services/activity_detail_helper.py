"""Helper service for managing detailed activity data from Garmin API."""
import json
import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.database_models import ActivityDetail


logger = logging.getLogger(__name__)


class ActivityDetailHelper:
    """Helper for storing and calculating activity detail metrics."""

    @staticmethod
    def calculate_pace_consistency(splits_data: dict | None) -> float | None:
        """
        Calculate pace consistency score from splits data.

        Returns:
            float: Score from 0-100 (100 = perfect consistency)
            None: If insufficient data

        Algorithm:
            - Calculate coefficient of variation (CV) of pace across splits
            - Convert to 0-100 scale (lower CV = higher score)
            - CV of 0% = 100, CV of 20%+ = 0
        """
        if not splits_data or "lapDTOs" not in splits_data:
            return None

        laps = splits_data.get("lapDTOs", [])
        if len(laps) < 3:  # Need at least 3 splits for meaningful analysis
            return None

        # Extract pace from each lap (seconds per km)
        paces = []
        for lap in laps:
            distance_m = lap.get("distance")
            duration_s = lap.get("duration")

            if distance_m and distance_m > 0 and duration_s and duration_s > 0:
                pace_per_km = (duration_s / distance_m) * 1000
                paces.append(pace_per_km)

        if len(paces) < 3:
            return None

        # Calculate coefficient of variation
        mean_pace = sum(paces) / len(paces)
        if mean_pace == 0:
            return None

        variance = sum((p - mean_pace) ** 2 for p in paces) / len(paces)
        std_dev = variance ** 0.5
        cv = (std_dev / mean_pace) * 100  # As percentage

        # Convert CV to 0-100 score (lower CV = higher score)
        # CV of 0% = 100, CV of 20%+ = 0
        score = max(0, min(100, 100 - (cv * 5)))

        logger.debug(
            "Pace consistency: %d paces, CV=%.2f%%, score=%.1f",
            len(paces),
            cv,
            score
        )

        return round(score, 1)

    @staticmethod
    def calculate_hr_drift(hr_zones_data: dict | None, splits_data: dict | None) -> float | None:
        """
        Calculate HR drift (% increase from start to finish).

        Returns:
            float: HR drift as percentage (e.g., 5.2 means 5.2% increase)
            None: If insufficient data

        Algorithm:
            - Use first and last lap average HR from splits
            - Calculate percentage increase
        """
        if not splits_data or "lapDTOs" not in splits_data:
            return None

        laps = splits_data.get("lapDTOs", [])
        if len(laps) < 2:  # Need at least 2 laps
            return None

        # Get first and last lap HR
        first_hr = laps[0].get("averageHR")
        last_hr = laps[-1].get("averageHR")

        if not first_hr or not last_hr or first_hr == 0:
            return None

        # Calculate drift percentage
        drift = ((last_hr - first_hr) / first_hr) * 100

        logger.debug(
            "HR drift: first=%d, last=%d, drift=%.1f%%",
            first_hr,
            last_hr,
            drift
        )

        return round(drift, 1)

    @staticmethod
    def should_refetch(activity_detail: ActivityDetail | None, force: bool = False) -> bool:
        """
        Determine if activity details should be re-fetched.

        Args:
            activity_detail: Existing ActivityDetail record or None
            force: Force refetch regardless of cache status

        Returns:
            bool: True if should fetch from API
        """
        if force:
            return True

        if activity_detail is None:
            return True

        # If data is incomplete and more than 1 hour old, retry
        if not activity_detail.is_complete:
            age = datetime.utcnow() - activity_detail.fetched_at
            if age > timedelta(hours=1):
                logger.info(
                    "Activity detail %d incomplete and >1h old, refetching",
                    activity_detail.activity_id
                )
                return True

        # If complete and less than 24 hours old, skip
        if activity_detail.is_complete:
            age = datetime.utcnow() - activity_detail.fetched_at
            if age < timedelta(hours=24):
                logger.debug(
                    "Activity detail %d is complete and fresh (age=%s), skipping",
                    activity_detail.activity_id,
                    age
                )
                return False

        return True

    @staticmethod
    def create_or_update(
        session: Session,
        activity_id: int,
        splits_data: dict | None,
        hr_zones_data: dict | None,
        weather_data: dict | None,
        errors: list[str]
    ) -> ActivityDetail:
        """
        Create or update ActivityDetail record with fetched data.

        Args:
            session: Database session
            activity_id: Garmin activity ID
            splits_data: Raw splits data from API
            hr_zones_data: Raw HR zones data from API
            weather_data: Raw weather data from API
            errors: List of error messages encountered during fetch

        Returns:
            ActivityDetail: Created or updated record
        """
        # Check if record exists
        detail = session.query(ActivityDetail).filter_by(activity_id=activity_id).first()

        # Calculate derived metrics
        pace_consistency = ActivityDetailHelper.calculate_pace_consistency(splits_data)
        hr_drift = ActivityDetailHelper.calculate_hr_drift(hr_zones_data, splits_data)

        # Determine if fetch is complete
        is_complete = all([
            splits_data or "splits" in errors,  # Either have data or explicitly failed
            hr_zones_data or "hr_zones" in errors,
            weather_data or "weather" in errors
        ]) and len(errors) == 0

        if detail:
            # Update existing record
            detail.splits_data = splits_data
            detail.hr_zones_data = hr_zones_data
            detail.weather_data = weather_data
            detail.pace_consistency_score = pace_consistency
            detail.hr_drift_percent = hr_drift
            detail.fetched_at = datetime.utcnow()
            detail.is_complete = is_complete
            detail.fetch_errors = json.dumps(errors) if errors else None
            detail.updated_at = datetime.utcnow()

            logger.info(
                "Updated activity detail for activity_id=%d (complete=%s, errors=%d)",
                activity_id,
                is_complete,
                len(errors)
            )
        else:
            # Create new record
            detail = ActivityDetail(
                activity_id=activity_id,
                splits_data=splits_data,
                hr_zones_data=hr_zones_data,
                weather_data=weather_data,
                pace_consistency_score=pace_consistency,
                hr_drift_percent=hr_drift,
                fetched_at=datetime.utcnow(),
                is_complete=is_complete,
                fetch_errors=json.dumps(errors) if errors else None
            )
            session.add(detail)

            logger.info(
                "Created activity detail for activity_id=%d (complete=%s, errors=%d)",
                activity_id,
                is_complete,
                len(errors)
            )

        session.commit()
        return detail

    @staticmethod
    def get_cached_detail(session: Session, activity_id: int) -> ActivityDetail | None:
        """
        Retrieve cached activity detail if available.

        Args:
            session: Database session
            activity_id: Garmin activity ID

        Returns:
            ActivityDetail or None
        """
        return session.query(ActivityDetail).filter_by(activity_id=activity_id).first()
