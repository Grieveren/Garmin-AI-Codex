"""Data aggregation and baseline calculations for historical analysis."""
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.database_models import DailyMetric, Activity


class DataProcessor:
    """Calculate baselines and trends from historical data."""

    def __init__(self, db: Session | None = None):
        """Initialize with optional database session."""
        self.db = db or SessionLocal()

    def get_hrv_baseline(self, target_date: date, days: int = 30) -> dict[str, Any]:
        """
        Calculate HRV baseline from historical data.

        Args:
            target_date: Date to analyze
            days: Number of days to include in baseline (default: 30)

        Returns:
            Dict with baseline_hrv, current_hrv, deviation_pct, is_concerning
        """
        start_date = target_date - timedelta(days=days)

        metrics = (
            self.db.query(DailyMetric)
            .filter(
                DailyMetric.date >= start_date,
                DailyMetric.date <= target_date,
                DailyMetric.hrv_morning.isnot(None),
            )
            .order_by(DailyMetric.date)
            .all()
        )

        if not metrics:
            return {
                "baseline_hrv": None,
                "current_hrv": None,
                "deviation_pct": None,
                "is_concerning": False,
                "trend": "insufficient_data",
            }

        hrv_values = [m.hrv_morning for m in metrics if m.hrv_morning]

        if len(hrv_values) < 7:  # Need at least a week of data
            return {
                "baseline_hrv": None,
                "current_hrv": hrv_values[-1] if hrv_values else None,
                "deviation_pct": None,
                "is_concerning": False,
                "trend": "insufficient_data",
            }

        baseline = sum(hrv_values[:-1]) / len(hrv_values[:-1]) if len(hrv_values) > 1 else hrv_values[0]
        current = hrv_values[-1]
        deviation_pct = ((current - baseline) / baseline) * 100 if baseline > 0 else 0

        # Calculate 7-day average for trend
        recent_avg = sum(hrv_values[-7:]) / min(7, len(hrv_values))
        trend = "decreasing" if recent_avg < baseline * 0.95 else "stable" if recent_avg < baseline * 1.05 else "increasing"

        return {
            "baseline_hrv": round(baseline, 1),
            "current_hrv": current,
            "7_day_avg": round(recent_avg, 1),
            "deviation_pct": round(deviation_pct, 1),
            "is_concerning": deviation_pct < -10,  # >10% drop is concerning
            "trend": trend,
            "data_points": len(hrv_values),
        }

    def get_resting_hr_baseline(self, target_date: date, days: int = 30) -> dict[str, Any]:
        """Calculate resting heart rate baseline."""
        start_date = target_date - timedelta(days=days)

        metrics = (
            self.db.query(DailyMetric)
            .filter(
                DailyMetric.date >= start_date,
                DailyMetric.date <= target_date,
                DailyMetric.resting_hr.isnot(None),
            )
            .order_by(DailyMetric.date)
            .all()
        )

        if not metrics:
            return {
                "baseline_rhr": None,
                "current_rhr": None,
                "deviation_bpm": None,
                "is_elevated": False,
            }

        rhr_values = [m.resting_hr for m in metrics if m.resting_hr]

        if len(rhr_values) < 7:
            return {
                "baseline_rhr": None,
                "current_rhr": rhr_values[-1] if rhr_values else None,
                "deviation_bpm": None,
                "is_elevated": False,
            }

        baseline = sum(rhr_values[:-1]) / len(rhr_values[:-1]) if len(rhr_values) > 1 else rhr_values[0]
        current = rhr_values[-1]
        deviation = current - baseline

        return {
            "baseline_rhr": round(baseline, 1),
            "current_rhr": current,
            "deviation_bpm": round(deviation, 1),
            "is_elevated": deviation > 5,  # >5 bpm elevation is concerning
            "data_points": len(rhr_values),
        }

    def get_sleep_baseline(self, target_date: date, days: int = 30) -> dict[str, Any]:
        """Calculate sleep baseline."""
        start_date = target_date - timedelta(days=days)

        metrics = (
            self.db.query(DailyMetric)
            .filter(
                DailyMetric.date >= start_date,
                DailyMetric.date <= target_date,
                DailyMetric.sleep_seconds.isnot(None),
            )
            .order_by(DailyMetric.date)
            .all()
        )

        if not metrics:
            return {
                "baseline_hours": None,
                "current_hours": None,
                "sleep_debt_hours": None,
                "is_sleep_deprived": False,
            }

        sleep_hours = [m.sleep_seconds / 3600 for m in metrics if m.sleep_seconds]

        if len(sleep_hours) < 7:
            return {
                "baseline_hours": None,
                "current_hours": sleep_hours[-1] if sleep_hours else None,
                "sleep_debt_hours": None,
                "is_sleep_deprived": False,
            }

        baseline = sum(sleep_hours[:-1]) / len(sleep_hours[:-1]) if len(sleep_hours) > 1 else sleep_hours[0]
        current = sleep_hours[-1]

        # Calculate 7-day sleep debt
        recent_sleep = sum(sleep_hours[-7:]) / min(7, len(sleep_hours))
        weekly_debt = (baseline * 7) - (recent_sleep * 7)

        return {
            "baseline_hours": round(baseline, 1),
            "current_hours": round(current, 1),
            "7_day_avg": round(recent_sleep, 1),
            "sleep_debt_hours": round(weekly_debt, 1),
            "is_sleep_deprived": current < 6 or weekly_debt > 4,  # <6 hours or >4 hours debt
            "data_points": len(sleep_hours),
        }

    def calculate_acwr(self, target_date: date) -> dict[str, Any]:
        """
        Calculate Acute:Chronic Workload Ratio for injury prevention.

        ACWR = Acute Load (7 days) / Chronic Load (28 days)
        Optimal: 0.8-1.3
        >1.5 = high injury risk
        """
        # Get activities for the last 28 days
        start_date = target_date - timedelta(days=28)

        activities = (
            self.db.query(Activity)
            .filter(Activity.date >= start_date, Activity.date <= target_date)
            .order_by(Activity.date)
            .all()
        )

        if not activities:
            return {
                "acute_load": 0,
                "chronic_load": 0,
                "acwr": None,
                "status": "insufficient_data",
                "injury_risk": "unknown",
            }

        # Calculate training load (use aerobic_training_effect as proxy if training_load not available)
        def get_load(activity):
            if activity.training_load:
                return activity.training_load
            elif activity.aerobic_training_effect:
                return activity.aerobic_training_effect * 10  # Scale to similar range
            return 0

        # Separate acute (last 7 days) and chronic (last 28 days)
        acute_cutoff = target_date - timedelta(days=7)

        acute_activities = [a for a in activities if a.date > acute_cutoff]
        chronic_activities = activities  # All 28 days

        acute_load = sum(get_load(a) for a in acute_activities)
        chronic_load = sum(get_load(a) for a in chronic_activities) / 4  # Average per week

        if chronic_load == 0:
            acwr = None
            status = "no_chronic_baseline"
            injury_risk = "unknown"
        else:
            acwr = acute_load / chronic_load

            if acwr < 0.8:
                status = "undertraining"
                injury_risk = "low"
            elif 0.8 <= acwr <= 1.3:
                status = "optimal"
                injury_risk = "low"
            elif 1.3 < acwr <= 1.5:
                status = "approaching_risk"
                injury_risk = "moderate"
            else:
                status = "high_risk"
                injury_risk = "high"

        return {
            "acute_load": round(acute_load, 1),
            "chronic_load": round(chronic_load, 1),
            "acwr": round(acwr, 2) if acwr else None,
            "status": status,
            "injury_risk": injury_risk,
            "acute_activity_count": len(acute_activities),
            "chronic_activity_count": len(chronic_activities),
        }

    def get_training_trends(self, target_date: date, days: int = 30) -> dict[str, Any]:
        """Calculate training volume and intensity trends."""
        start_date = target_date - timedelta(days=days)

        activities = (
            self.db.query(Activity)
            .filter(Activity.date >= start_date, Activity.date <= target_date)
            .order_by(Activity.date)
            .all()
        )

        if not activities:
            return {
                "total_activities": 0,
                "total_distance_km": 0,
                "total_duration_hours": 0,
                "avg_weekly_distance": 0,
                "consecutive_training_days": 0,
            }

        total_distance = sum(a.distance_meters or 0 for a in activities) / 1000  # km
        total_duration = sum(a.duration_seconds or 0 for a in activities) / 3600  # hours

        # Calculate consecutive training days ending on target_date
        consecutive_days = 0
        check_date = target_date
        dates_with_activities = {a.date for a in activities}

        while check_date in dates_with_activities:
            consecutive_days += 1
            check_date -= timedelta(days=1)

        return {
            "total_activities": len(activities),
            "total_distance_km": round(total_distance, 1),
            "total_duration_hours": round(total_duration, 1),
            "avg_weekly_distance": round(total_distance / (days / 7), 1),
            "consecutive_training_days": consecutive_days,
        }

    def calculate_weekly_load_increase(self, target_date: date) -> float | None:
        """
        Calculate week-over-week training load increase percentage.

        Args:
            target_date: Date to calculate from

        Returns:
            Percentage increase (positive) or decrease (negative), or None if insufficient data
        """
        # Get last week's load (target_date - 6 to target_date)
        last_week_start = target_date - timedelta(days=6)
        last_week_end = target_date

        # Get previous week's load (target_date - 13 to target_date - 7)
        prev_week_start = target_date - timedelta(days=13)
        prev_week_end = target_date - timedelta(days=7)

        # Fetch activities for both weeks
        activities = (
            self.session.query(Activity)
            .filter(Activity.date >= prev_week_start)
            .filter(Activity.date <= last_week_end)
            .all()
        )

        last_week_load = 0.0
        prev_week_load = 0.0

        for activity in activities:
            # Calculate load (use training_load or estimate from training effect)
            if activity.training_load:
                load = float(activity.training_load)
            elif activity.aerobic_training_effect:
                load = float(activity.aerobic_training_effect) * 10
            else:
                continue

            if last_week_start <= activity.date <= last_week_end:
                last_week_load += load
            elif prev_week_start <= activity.date <= prev_week_end:
                prev_week_load += load

        # Calculate percentage increase
        if prev_week_load == 0:
            return None

        increase_pct = ((last_week_load - prev_week_load) / prev_week_load) * 100
        return round(increase_pct, 1)

    def get_all_baselines(self, target_date: date) -> dict[str, Any]:
        """Get all baselines and metrics for AI analysis."""
        return {
            "hrv": self.get_hrv_baseline(target_date),
            "resting_hr": self.get_resting_hr_baseline(target_date),
            "sleep": self.get_sleep_baseline(target_date),
            "acwr": self.calculate_acwr(target_date),
            "training_trends": self.get_training_trends(target_date),
            "weekly_load_increase_pct": self.calculate_weekly_load_increase(target_date),
        }
