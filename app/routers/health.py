"""Router exposing basic system endpoints."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException

from app.database import SessionLocal
from app.models.database_models import DailyMetric, Activity


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/status")
async def get_status() -> dict[str, str]:
    """Return a minimal status payload."""
    return {"status": "online"}


@router.get("/sync-status")
async def get_sync_status() -> dict:
    """
    Check the staleness of synced data.

    Returns information about when data was last synced and whether
    it needs to be refreshed.

    Returns:
        dict: {
            "last_sync": ISO timestamp or None,
            "is_stale": bool,
            "staleness_threshold_hours": int,
            "needs_sync": bool
        }
    """
    staleness_threshold_hours = 1
    db = SessionLocal()  # Let it fail naturally - FastAPI will handle connection errors

    try:
        # Get the most recent data timestamp from both tables
        latest_metric = (
            db.query(DailyMetric)
            .order_by(DailyMetric.updated_at.desc())
            .first()
        )
        latest_activity = (
            db.query(Activity)
            .order_by(Activity.updated_at.desc())
            .first()
        )

        # Determine the most recent update time
        timestamps = []
        if latest_metric and latest_metric.updated_at:
            timestamps.append(latest_metric.updated_at)
        if latest_activity and latest_activity.updated_at:
            timestamps.append(latest_activity.updated_at)

        if not timestamps:
            # No data at all - definitely needs sync
            return {
                "last_sync": None,
                "is_stale": True,
                "staleness_threshold_hours": staleness_threshold_hours,
                "needs_sync": True,
            }

        last_sync = max(timestamps)
        # Use timezone-aware datetime for proper comparison
        threshold = datetime.now(timezone.utc) - timedelta(hours=staleness_threshold_hours)

        # Ensure last_sync is timezone-aware for comparison
        if last_sync.tzinfo is None:
            # Assume UTC if naive datetime
            last_sync = last_sync.replace(tzinfo=timezone.utc)

        is_stale = last_sync < threshold

        return {
            "last_sync": last_sync.isoformat(),
            "is_stale": is_stale,
            "staleness_threshold_hours": staleness_threshold_hours,
            "needs_sync": is_stale,
        }

    except Exception as e:
        logger.exception("Sync status check failed")
        db.rollback()  # CRITICAL: Ensure uncommitted transactions are rolled back
        raise HTTPException(status_code=500, detail="Failed to check sync status")
    finally:
        db.close()
