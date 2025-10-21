"""Service for fetching and caching detailed activity data."""
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.services.garmin_service import GarminService
from app.services.activity_detail_helper import ActivityDetailHelper
from app.models.database_models import ActivityDetail


logger = logging.getLogger(__name__)


class ActivityDetailService:
    """
    Orchestrates fetching detailed activity data from Garmin API with caching.

    Combines GarminService API calls with ActivityDetailHelper for storage
    and cache management.
    """

    def __init__(self, garmin_service: GarminService, session: Session):
        """
        Initialize the service.

        Args:
            garmin_service: Authenticated GarminService instance
            session: SQLAlchemy database session
        """
        self.garmin = garmin_service
        self.session = session
        self.helper = ActivityDetailHelper()

    def fetch_and_store_details(
        self,
        activity_id: int,
        force_refetch: bool = False
    ) -> dict[str, Any]:
        """
        Fetch detailed activity data and store in database.

        This is the main entry point for getting detailed activity analysis.
        It handles caching, fetching from API, calculating derived metrics,
        and storing results.

        Args:
            activity_id: Garmin activity ID
            force_refetch: Skip cache and force fresh API call

        Returns:
            dict: Response containing:
                - cached: bool (was data from cache?)
                - activity_id: int
                - splits: dict | None
                - hr_zones: dict | None
                - weather: dict | None
                - pace_consistency_score: float | None
                - hr_drift_percent: float | None
                - is_complete: bool
                - errors: list[str]
                - fetched_at: datetime

        Example:
            >>> service = ActivityDetailService(garmin, session)
            >>> result = service.fetch_and_store_details(12345678)
            >>> if result["cached"]:
            ...     print("Using cached data")
            >>> else:
            ...     print(f"Fetched fresh data: {result['is_complete']}")
        """
        # Check cache first
        cached_detail = self.helper.get_cached_detail(self.session, activity_id)

        # Determine if we should refetch
        should_fetch = self.helper.should_refetch(cached_detail, force_refetch)

        if not should_fetch and cached_detail:
            logger.info("Using cached data for activity %d", activity_id)
            return {
                "cached": True,
                "activity_id": activity_id,
                "splits": cached_detail.splits_data,
                "hr_zones": cached_detail.hr_zones_data,
                "weather": cached_detail.weather_data,
                "pace_consistency_score": cached_detail.pace_consistency_score,
                "hr_drift_percent": cached_detail.hr_drift_percent,
                "is_complete": cached_detail.is_complete,
                "errors": [],
                "fetched_at": cached_detail.fetched_at
            }

        # Fetch from API
        logger.info(
            "Fetching activity details from API for activity %d (force=%s)",
            activity_id,
            force_refetch
        )
        api_result = self.garmin.get_detailed_activity_analysis(activity_id)

        # Store in database
        detail = self.helper.create_or_update(
            self.session,
            activity_id,
            api_result["splits"],
            api_result["hr_zones"],
            api_result["weather"],
            api_result["errors"]
        )

        return {
            "cached": False,
            "activity_id": activity_id,
            "splits": detail.splits_data,
            "hr_zones": detail.hr_zones_data,
            "weather": detail.weather_data,
            "pace_consistency_score": detail.pace_consistency_score,
            "hr_drift_percent": detail.hr_drift_percent,
            "is_complete": detail.is_complete,
            "errors": api_result["errors"],
            "fetched_at": detail.fetched_at
        }

    def get_cached_details(self, activity_id: int) -> dict[str, Any] | None:
        """
        Get cached activity details without fetching from API.

        Args:
            activity_id: Garmin activity ID

        Returns:
            dict: Cached data or None if not in cache
        """
        cached = self.helper.get_cached_detail(self.session, activity_id)

        if not cached:
            return None

        return {
            "activity_id": activity_id,
            "splits": cached.splits_data,
            "hr_zones": cached.hr_zones_data,
            "weather": cached.weather_data,
            "pace_consistency_score": cached.pace_consistency_score,
            "hr_drift_percent": cached.hr_drift_percent,
            "is_complete": cached.is_complete,
            "fetched_at": cached.fetched_at
        }

    def bulk_fetch_recent_activities(
        self,
        activity_ids: list[int],
        limit: int | None = None
    ) -> dict[str, Any]:
        """
        Fetch details for multiple activities efficiently.

        Uses caching to minimize API calls. Only fetches missing or stale data.

        Args:
            activity_ids: List of Garmin activity IDs
            limit: Optional limit on number of API calls (for rate limiting)

        Returns:
            dict: Summary of operation
                {
                    "total": int,
                    "cached": int,
                    "fetched": int,
                    "failed": int,
                    "skipped": int (if limit reached),
                    "activity_ids_fetched": list[int],
                    "activity_ids_failed": list[int]
                }

        Example:
            >>> service = ActivityDetailService(garmin, session)
            >>> result = service.bulk_fetch_recent_activities([123, 456, 789], limit=10)
            >>> print(f"Cached: {result['cached']}, Fetched: {result['fetched']}")
        """
        logger.info("Bulk fetching details for %d activities", len(activity_ids))

        total = len(activity_ids)
        cached = 0
        fetched = 0
        failed = 0
        skipped = 0
        fetched_ids = []
        failed_ids = []

        for i, activity_id in enumerate(activity_ids):
            # Check limit
            if limit and fetched >= limit:
                skipped = total - i
                logger.info("Reached fetch limit (%d), skipping remaining %d activities", limit, skipped)
                break

            # Check cache
            cached_detail = self.helper.get_cached_detail(self.session, activity_id)
            should_fetch = self.helper.should_refetch(cached_detail, force=False)

            if not should_fetch:
                cached += 1
                logger.debug("Activity %d already cached", activity_id)
                continue

            # Fetch from API
            try:
                result = self.fetch_and_store_details(activity_id, force_refetch=False)

                if result["is_complete"] or len(result["errors"]) < 3:  # Partial success is ok
                    fetched += 1
                    fetched_ids.append(activity_id)
                    logger.info(
                        "Fetched details for activity %d (%d/%d complete)",
                        activity_id,
                        3 - len(result["errors"]),
                        3
                    )
                else:
                    failed += 1
                    failed_ids.append(activity_id)
                    logger.warning("Failed to fetch any details for activity %d", activity_id)

            except Exception as err:
                failed += 1
                failed_ids.append(activity_id)
                logger.error("Exception fetching details for activity %d: %s", activity_id, err)

        summary = {
            "total": total,
            "cached": cached,
            "fetched": fetched,
            "failed": failed,
            "skipped": skipped,
            "activity_ids_fetched": fetched_ids,
            "activity_ids_failed": failed_ids
        }

        logger.info(
            "Bulk fetch complete: %d total, %d cached, %d fetched, %d failed, %d skipped",
            total,
            cached,
            fetched,
            failed,
            skipped
        )

        return summary
