"""API endpoints for training analytics and insights."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.database_models import Activity, DailyMetric
from app.services.data_processor import DataProcessor


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _calculate_pearson_correlation(x_values: list[float], y_values: list[float]) -> float:
    """
    Calculate Pearson correlation coefficient between two datasets.

    Returns value between -1 and 1, where:
    - 1 = perfect positive correlation
    - 0 = no correlation
    - -1 = perfect negative correlation
    """
    if len(x_values) != len(y_values) or len(x_values) < 2:
        return 0.0

    n = len(x_values)
    mean_x = sum(x_values) / n
    mean_y = sum(y_values) / n

    numerator = sum((x_values[i] - mean_x) * (y_values[i] - mean_y) for i in range(n))

    std_x = sum((x - mean_x) ** 2 for x in x_values) ** 0.5
    std_y = sum((y - mean_y) ** 2 for y in y_values) ** 0.5

    if std_x == 0 or std_y == 0:
        return 0.0

    denominator = std_x * std_y

    return numerator / denominator if denominator != 0 else 0.0


@router.get("/readiness-trend")
async def get_readiness_trend(
    days: int = Query(default=30, ge=1, le=365),
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    """
    Get time series of readiness scores.

    Query parameters:
        days: Number of days to retrieve (default 30)
        start_date: Optional start date (YYYY-MM-DD)
        end_date: Optional end date (YYYY-MM-DD)

    Returns:
        List of readiness data points with date, score, recommendation, and key factors
    """
    db: Session = SessionLocal()

    try:
        # Determine date range
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=days - 1)

        logger.info(
            "Fetching readiness trend | start=%s end=%s",
            start_date.isoformat(),
            end_date.isoformat()
        )

        # Query daily metrics with readiness proxy (we'll use combination of HRV, sleep, resting HR)
        metrics = (
            db.query(DailyMetric)
            .filter(
                DailyMetric.date >= start_date,
                DailyMetric.date <= end_date,
            )
            .order_by(DailyMetric.date)
            .all()
        )

        if not metrics:
            logger.warning("No metrics found for date range")
            return []

        # Calculate readiness-like scores based on available metrics
        result = []
        for metric in metrics:
            # Simple readiness calculation (0-100)
            # This is a proxy until we have actual stored readiness scores
            score_components = []

            # HRV component (higher is better, normalize to 0-100)
            if metric.hrv_morning:
                hrv_score = min(100, (metric.hrv_morning / 100) * 100)
                score_components.append(hrv_score)

            # Sleep component (7-8 hours optimal)
            if metric.sleep_seconds:
                sleep_hours = metric.sleep_seconds / 3600
                if sleep_hours >= 7 and sleep_hours <= 8:
                    sleep_score = 100
                elif sleep_hours >= 6:
                    sleep_score = 70
                else:
                    sleep_score = 40
                score_components.append(sleep_score)

            # Resting HR component (lower is better relative to baseline)
            if metric.resting_hr:
                # Assume 60 is optimal, scale accordingly
                rhr_score = max(0, min(100, 100 - (metric.resting_hr - 60) * 2))
                score_components.append(rhr_score)

            # Training readiness if available
            if metric.training_readiness_score:
                score_components.append(metric.training_readiness_score)

            # Average the components
            readiness_score = int(sum(score_components) / len(score_components)) if score_components else 50

            # Determine recommendation based on score
            if readiness_score >= 80:
                recommendation = "high_intensity"
            elif readiness_score >= 60:
                recommendation = "moderate"
            elif readiness_score >= 40:
                recommendation = "easy"
            else:
                recommendation = "rest"

            # Determine key factors
            key_factors = []
            if metric.hrv_morning:
                key_factors.append(f"HRV: {metric.hrv_morning}ms")
            if metric.sleep_seconds:
                key_factors.append(f"Sleep: {metric.sleep_seconds / 3600:.1f}h")
            if metric.resting_hr:
                key_factors.append(f"RHR: {metric.resting_hr} bpm")

            result.append({
                "date": metric.date.isoformat(),
                "score": readiness_score,
                "recommendation": recommendation,
                "key_factors": key_factors,
            })

        logger.info("Retrieved %d readiness data points", len(result))
        return result

    except Exception as e:
        logger.exception("Failed to fetch readiness trend")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch readiness trend: {str(e)}"
        )
    finally:
        db.close()


@router.get("/training-load")
async def get_training_load(
    days: int = Query(default=90, ge=1, le=365),
) -> list[dict[str, Any]]:
    """
    Get training load metrics over time (ACWR, fitness, fatigue, form).

    Query parameters:
        days: Number of days to retrieve (default 90)

    Returns:
        List of training load data points with ACWR, fitness, fatigue, and form
    """
    db: Session = SessionLocal()
    processor = DataProcessor(db)

    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)

        logger.info(
            "Calculating training load | start=%s end=%s days=%d",
            start_date.isoformat(),
            end_date.isoformat(),
            days
        )

        result = []
        current_date = start_date

        while current_date <= end_date:
            # Get ACWR for this date
            acwr_data = processor.calculate_acwr(current_date)

            # Calculate simple fitness/fatigue/form metrics
            # Fitness = 42-day exponentially weighted moving average (chronic load)
            # Fatigue = 7-day exponentially weighted moving average (acute load)
            # Form = Fitness - Fatigue

            # Get activities for fitness calculation (42 days)
            fitness_start = current_date - timedelta(days=42)
            fitness_activities = (
                db.query(Activity)
                .filter(
                    Activity.date >= fitness_start,
                    Activity.date <= current_date
                )
                .all()
            )

            # Calculate fitness (chronic load)
            fitness = 0.0
            if fitness_activities:
                total_load = sum(
                    a.training_load or (a.aerobic_training_effect or 0) * 10
                    for a in fitness_activities
                )
                fitness = total_load / 6  # Normalize by weeks

            # Fatigue = acute load (already calculated in ACWR)
            fatigue = acwr_data.get("acute_load", 0)

            # Form = Fitness - Fatigue
            form = fitness - fatigue

            result.append({
                "date": current_date.isoformat(),
                "acwr": acwr_data.get("acwr"),
                "fitness": round(fitness, 1),
                "fatigue": round(fatigue, 1),
                "form": round(form, 1),
            })

            current_date += timedelta(days=1)

        logger.info("Calculated training load for %d days", len(result))
        return result

    except Exception as e:
        logger.exception("Failed to calculate training load")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate training load: {str(e)}"
        )
    finally:
        db.close()


@router.get("/sleep-performance")
async def get_sleep_performance(
    days: int = Query(default=30, ge=1, le=365),
) -> list[dict[str, Any]]:
    """
    Get sleep metrics correlated with readiness.

    Query parameters:
        days: Number of days to retrieve (default 30)

    Returns:
        List of data points with sleep score, duration, HRV, and readiness
    """
    db: Session = SessionLocal()

    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)

        logger.info(
            "Fetching sleep performance | start=%s end=%s",
            start_date.isoformat(),
            end_date.isoformat()
        )

        # Query daily metrics with sleep data
        metrics = (
            db.query(DailyMetric)
            .filter(
                DailyMetric.date >= start_date,
                DailyMetric.date <= end_date,
            )
            .order_by(DailyMetric.date)
            .all()
        )

        if not metrics:
            logger.warning("No sleep metrics found for date range")
            return []

        result = []
        for metric in metrics:
            # Calculate readiness score (same logic as readiness-trend)
            score_components = []

            if metric.hrv_morning:
                hrv_score = min(100, (metric.hrv_morning / 100) * 100)
                score_components.append(hrv_score)

            if metric.sleep_seconds:
                sleep_hours = metric.sleep_seconds / 3600
                if sleep_hours >= 7 and sleep_hours <= 8:
                    sleep_score = 100
                elif sleep_hours >= 6:
                    sleep_score = 70
                else:
                    sleep_score = 40
                score_components.append(sleep_score)

            if metric.resting_hr:
                rhr_score = max(0, min(100, 100 - (metric.resting_hr - 60) * 2))
                score_components.append(rhr_score)

            if metric.training_readiness_score:
                score_components.append(metric.training_readiness_score)

            readiness = int(sum(score_components) / len(score_components)) if score_components else 50

            # Only include if we have sleep data
            if metric.sleep_seconds:
                result.append({
                    "date": metric.date.isoformat(),
                    "sleep_score": metric.sleep_score or 0,
                    "sleep_duration": round(metric.sleep_seconds / 3600, 1),
                    "hrv": metric.hrv_morning or 0,
                    "readiness": readiness,
                })

        logger.info("Retrieved %d sleep performance data points", len(result))
        return result

    except Exception as e:
        logger.exception("Failed to fetch sleep performance")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch sleep performance: {str(e)}"
        )
    finally:
        db.close()


@router.get("/activity-breakdown")
async def get_activity_breakdown(
    days: int = Query(default=30, ge=1, le=365),
) -> dict[str, dict[str, Any]]:
    """
    Get activity type distribution and statistics.

    Query parameters:
        days: Number of days to retrieve (default 30)

    Returns:
        Dictionary with activity types as keys and statistics (count, distance, duration, avg pace)
    """
    db: Session = SessionLocal()

    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)

        logger.info(
            "Fetching activity breakdown | start=%s end=%s",
            start_date.isoformat(),
            end_date.isoformat()
        )

        # Query activities
        activities = (
            db.query(Activity)
            .filter(
                Activity.date >= start_date,
                Activity.date <= end_date,
            )
            .all()
        )

        if not activities:
            logger.warning("No activities found for date range")
            return {}

        # Group by activity type
        breakdown: dict[str, dict[str, Any]] = {}

        for activity in activities:
            activity_type = activity.activity_type or "unknown"

            if activity_type not in breakdown:
                breakdown[activity_type] = {
                    "count": 0,
                    "distance_km": 0.0,
                    "duration_min": 0.0,
                    "total_pace_seconds": 0.0,
                    "pace_count": 0,
                }

            breakdown[activity_type]["count"] += 1

            if activity.distance_meters:
                breakdown[activity_type]["distance_km"] += activity.distance_meters / 1000

            if activity.duration_seconds:
                breakdown[activity_type]["duration_min"] += activity.duration_seconds / 60

            if activity.avg_pace:
                breakdown[activity_type]["total_pace_seconds"] += activity.avg_pace
                breakdown[activity_type]["pace_count"] += 1

        # Calculate averages and format output
        result = {}
        for activity_type, stats in breakdown.items():
            avg_pace = None
            if stats["pace_count"] > 0:
                avg_pace = int(stats["total_pace_seconds"] / stats["pace_count"])

            result[activity_type] = {
                "count": stats["count"],
                "distance_km": round(stats["distance_km"], 1),
                "duration_min": round(stats["duration_min"], 0),
                "avg_pace": avg_pace,
            }

        logger.info("Activity breakdown for %d activity types", len(result))
        return result

    except Exception as e:
        logger.exception("Failed to fetch activity breakdown")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch activity breakdown: {str(e)}"
        )
    finally:
        db.close()


@router.get("/recovery-correlation")
async def get_recovery_correlation(
    metric: str = Query(default="hrv", regex="^(hrv|sleep|rhr)$"),
    days: int = Query(default=30, ge=7, le=365),
) -> dict[str, Any]:
    """
    Get correlation between recovery metric and readiness.

    Query parameters:
        metric: Metric to correlate (hrv, sleep, or rhr)
        days: Number of days to analyze (default 30, min 7)

    Returns:
        Correlation coefficient and data points for visualization
    """
    db: Session = SessionLocal()

    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)

        logger.info(
            "Calculating recovery correlation | metric=%s start=%s end=%s",
            metric,
            start_date.isoformat(),
            end_date.isoformat()
        )

        # Query daily metrics
        metrics = (
            db.query(DailyMetric)
            .filter(
                DailyMetric.date >= start_date,
                DailyMetric.date <= end_date,
            )
            .order_by(DailyMetric.date)
            .all()
        )

        if not metrics:
            logger.warning("No metrics found for correlation analysis")
            return {
                "correlation_coefficient": 0.0,
                "data": [],
            }

        # Prepare data arrays for correlation
        metric_values: list[float] = []
        readiness_values: list[float] = []
        data_points: list[dict[str, Any]] = []

        for daily_metric in metrics:
            # Get metric value based on type
            metric_value = None
            if metric == "hrv" and daily_metric.hrv_morning:
                metric_value = float(daily_metric.hrv_morning)
            elif metric == "sleep" and daily_metric.sleep_seconds:
                metric_value = daily_metric.sleep_seconds / 3600  # Convert to hours
            elif metric == "rhr" and daily_metric.resting_hr:
                metric_value = float(daily_metric.resting_hr)

            if metric_value is None:
                continue

            # Calculate readiness score (same logic as other endpoints)
            score_components = []

            if daily_metric.hrv_morning:
                hrv_score = min(100, (daily_metric.hrv_morning / 100) * 100)
                score_components.append(hrv_score)

            if daily_metric.sleep_seconds:
                sleep_hours = daily_metric.sleep_seconds / 3600
                if sleep_hours >= 7 and sleep_hours <= 8:
                    sleep_score = 100
                elif sleep_hours >= 6:
                    sleep_score = 70
                else:
                    sleep_score = 40
                score_components.append(sleep_score)

            if daily_metric.resting_hr:
                rhr_score = max(0, min(100, 100 - (daily_metric.resting_hr - 60) * 2))
                score_components.append(rhr_score)

            if daily_metric.training_readiness_score:
                score_components.append(daily_metric.training_readiness_score)

            readiness = sum(score_components) / len(score_components) if score_components else 50.0

            metric_values.append(metric_value)
            readiness_values.append(readiness)

            data_points.append({
                "date": daily_metric.date.isoformat(),
                "metric_value": round(metric_value, 1),
                "readiness": round(readiness, 1),
            })

        # Calculate Pearson correlation coefficient
        correlation = 0.0
        if len(metric_values) >= 2:
            correlation = _calculate_pearson_correlation(metric_values, readiness_values)

        logger.info(
            "Calculated correlation | metric=%s points=%d r=%.3f",
            metric,
            len(data_points),
            correlation
        )

        return {
            "correlation_coefficient": round(correlation, 3),
            "data": data_points,
        }

    except Exception as e:
        logger.exception("Failed to calculate recovery correlation")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate recovery correlation: {str(e)}"
        )
    finally:
        db.close()
