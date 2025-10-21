"""Alert management API endpoints."""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.database_models import TrainingAlert

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("/active")
async def get_active_alerts(
    days: int = 7,
    db: Session = Depends(get_db),
) -> dict:
    """
    Get active alerts from the last N days.

    Args:
        days: Number of days to look back (default: 7)
        db: Database session

    Returns:
        Dictionary with count and list of active alerts
    """
    # Validate days parameter to prevent excessive database queries
    if days < 1 or days > 365:
        raise HTTPException(
            status_code=400,
            detail="days parameter must be between 1 and 365"
        )

    cutoff_date = date.today() - timedelta(days=days)

    alerts = (
        db.query(TrainingAlert)
        .filter(
            TrainingAlert.trigger_date >= cutoff_date,
            TrainingAlert.status == "active",
        )
        .order_by(TrainingAlert.trigger_date.desc())
        .all()
    )

    return {
        "count": len(alerts),
        "alerts": [
            {
                "id": a.id,
                "alert_type": a.alert_type,
                "severity": a.severity,
                "title": a.title,
                "message": a.message,
                "recommendation": a.recommendation,
                "trigger_date": a.trigger_date.isoformat(),
                "trigger_metrics": a.trigger_metrics,
                "detected_at": a.created_at.isoformat(),
            }
            for a in alerts
        ],
    }


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """
    Mark an alert as acknowledged.

    Args:
        alert_id: ID of the alert to acknowledge
        db: Database session

    Returns:
        Success confirmation

    Raises:
        HTTPException: 404 if alert not found
    """
    alert = db.query(TrainingAlert).filter(TrainingAlert.id == alert_id).first()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = "acknowledged"
    alert.acknowledged_at = datetime.utcnow()
    db.commit()

    return {"status": "success", "message": "Alert acknowledged"}
