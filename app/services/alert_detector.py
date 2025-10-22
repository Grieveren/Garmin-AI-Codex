"""Alert detection service for identifying training risks."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.database_models import Activity, DailyMetric, TrainingAlert


logger = logging.getLogger(__name__)


def sanitize_trigger_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitize trigger metrics for safe JSON storage.

    Removes any non-primitive types to prevent injection attacks
    and ensure JSON serialization safety.

    Args:
        metrics: Dictionary of trigger metrics

    Returns:
        Sanitized dictionary with only primitive types
    """
    if not isinstance(metrics, dict):
        return {}

    safe_metrics = {}
    for key, value in metrics.items():
        if not isinstance(key, str):
            continue

        if isinstance(value, (str, int, float, bool, type(None))):
            safe_metrics[key] = value
        elif isinstance(value, list):
            safe_metrics[key] = [
                v for v in value
                if isinstance(v, (str, int, float, bool, type(None)))
            ]

    return safe_metrics


class AlertDetectorHelper:
    """Helper class for alert detection utility methods."""

    @staticmethod
    def count_consecutive_hard_days(
        activities: list[Activity],
        target_date: date,
        training_effect_threshold: float = 3.0,
    ) -> int:
        """
        Count consecutive days of high-intensity training ending on target_date.

        Args:
            activities: List of Activity objects
            target_date: Date to count backwards from
            training_effect_threshold: Minimum training effect to count as "hard" (default: 3.0)

        Returns:
            Number of consecutive hard training days
        """
        # Create set of dates with hard workouts
        hard_workout_dates = set()
        for activity in activities:
            if activity.aerobic_training_effect and activity.aerobic_training_effect >= training_effect_threshold:
                hard_workout_dates.add(activity.date)

        # Count backwards from target_date
        consecutive = 0
        check_date = target_date
        while check_date in hard_workout_dates:
            consecutive += 1
            check_date -= timedelta(days=1)

        return consecutive

    @staticmethod
    def calculate_weekly_load_increase(
        activities: list[Activity],
        target_date: date,
    ) -> float | None:
        """
        Calculate week-over-week training load increase percentage.

        Args:
            activities: List of Activity objects
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


class AlertDetector:
    """Detects training alerts based on physiological metrics."""

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize alert detector.

        Args:
            config: Optional pre-loaded configuration (defaults to loading from prompts.yaml)
        """
        self.helper = AlertDetectorHelper()
        self.config = config or self._load_config()

    def _load_config(self) -> dict[str, Any]:
        """Load alert detection configuration from prompts.yaml."""
        settings = get_settings()
        config_path = settings.prompt_config_path

        with Path(config_path).open("r", encoding="utf-8") as f:
            full_config = yaml.safe_load(f)

        alert_config = full_config.get("alert_detection", {})
        if not alert_config:
            logger.warning("No alert_detection config found in prompts.yaml - using defaults")
            return self._default_config()

        return alert_config

    def _default_config(self) -> dict[str, Any]:
        """Return default configuration if config file is missing."""
        return {
            "overtraining": {
                "hrv_drop": {"warning": 15, "critical": 25},
                "consecutive_hard_days": {"warning": 3, "critical": 5},
                "sleep_debt": {"warning": 3, "critical": 6},
            },
            "illness": {
                "warning": {"hrv_drop_percent": 20, "rhr_increase_bpm": 5, "consecutive_days": 2},
                "critical": {"hrv_drop_percent": 30, "rhr_increase_bpm": 10, "consecutive_days": 1},
            },
            "injury": {
                "acwr": {"warning": 1.3, "critical": 1.5},
                "weekly_load_increase": {"warning": 15, "critical": 25},
            },
        }

    def detect_alerts(
        self,
        target_date: date,
        session: Session,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Detect all active alerts for a given date.

        Checks for:
        1. Overtraining: HRV drop + consecutive high-intensity training
        2. Illness risk: HRV drop + elevated resting HR
        3. Injury risk: ACWR > 1.5

        Args:
            target_date: Date to analyze
            session: Database session
            context: Optional pre-calculated context (baselines, metrics) to avoid redundant queries

        Returns:
            List of alert dictionaries with:
            - alert_type: str
            - severity: "warning" | "critical"
            - title: str
            - message: str
            - recommendation: str
            - trigger_metrics: dict
        """
        logger.info("Detecting alerts for %s", target_date.isoformat())

        # Calculate baselines (or use provided context)
        baselines = context if context else self._calculate_baselines(target_date, session)

        alerts: list[dict[str, Any]] = []

        # Check each alert type
        overtraining_alert = self._check_overtraining_risk(target_date, baselines, session)
        if overtraining_alert:
            alerts.append(overtraining_alert)
            logger.warning("Overtraining alert detected: %s", overtraining_alert["severity"])

        illness_alert = self._check_illness_risk(target_date, baselines, session)
        if illness_alert:
            alerts.append(illness_alert)
            logger.warning("Illness risk alert detected: %s", illness_alert["severity"])

        injury_alert = self._check_injury_risk(target_date, baselines, session)
        if injury_alert:
            alerts.append(injury_alert)
            logger.warning("Injury risk alert detected: %s", injury_alert["severity"])

        # Store alerts in database
        for alert in alerts:
            self._store_alert(session, alert)

        logger.info("Detected %d alerts for %s", len(alerts), target_date.isoformat())
        return alerts

    def _check_overtraining_risk(
        self,
        target_date: date,
        baselines: dict[str, Any],
        session: Session,
    ) -> dict[str, Any] | None:
        """
        Check for overtraining signals.

        Criteria:
        - HRV drop: >15% warning, >25% critical
        - Consecutive hard days: 3+ warning, 5+ critical
        - Sleep debt: >3h warning, >6h critical

        Args:
            target_date: Date to analyze
            baselines: Calculated baseline metrics

        Returns:
            Alert dictionary or None if no overtraining detected
        """
        config = self.config.get("overtraining", {})
        hrv_thresholds = config.get("hrv_drop", {})
        hard_days_thresholds = config.get("consecutive_hard_days", {})
        sleep_debt_thresholds = config.get("sleep_debt", {})

        # Extract baseline data
        hrv_data = baselines.get("hrv_baseline", {})
        sleep_data = baselines.get("sleep_baseline", {})
        consecutive_hard = baselines.get("consecutive_hard_days", 0)
        sleep_debt = sleep_data.get("sleep_debt_hours", 0) or 0

        hrv_deviation_pct = hrv_data.get("deviation_pct")

        # Count indicators
        indicators: list[str] = []
        severity_scores: list[int] = []  # 1=warning, 2=critical

        # Check HRV drop (negative deviation = drop)
        if hrv_deviation_pct is not None and hrv_deviation_pct < 0:
            hrv_drop_abs = abs(hrv_deviation_pct)
            if hrv_drop_abs >= hrv_thresholds.get("critical", 25):
                indicators.append(f"HRV dropped {hrv_drop_abs:.1f}%")
                severity_scores.append(2)
            elif hrv_drop_abs >= hrv_thresholds.get("warning", 15):
                indicators.append(f"HRV dropped {hrv_drop_abs:.1f}%")
                severity_scores.append(1)

        # Check consecutive hard days
        if consecutive_hard >= hard_days_thresholds.get("critical", 5):
            indicators.append(f"{consecutive_hard} consecutive high-intensity days")
            severity_scores.append(2)
        elif consecutive_hard >= hard_days_thresholds.get("warning", 3):
            indicators.append(f"{consecutive_hard} consecutive high-intensity days")
            severity_scores.append(1)

        # Check sleep debt
        if sleep_debt >= sleep_debt_thresholds.get("critical", 6):
            indicators.append(f"{sleep_debt:.1f}h sleep debt")
            severity_scores.append(2)
        elif sleep_debt >= sleep_debt_thresholds.get("warning", 3):
            indicators.append(f"{sleep_debt:.1f}h sleep debt")
            severity_scores.append(1)

        # No overtraining indicators
        if not indicators:
            return None

        # Determine overall severity (critical if any critical indicator)
        severity = "critical" if max(severity_scores, default=0) == 2 else "warning"

        # Build message
        messages = config.get("messages", {}).get(severity, {})
        title = messages.get("title", f"Overtraining {severity.title()}")
        recommendation = messages.get("recommendation", "Consider rest or reduced training.")

        # Format message with actual indicators
        indicator_text = "; ".join(indicators)
        message_template = messages.get("message", "Overtraining indicators: {indicators}")
        message = message_template.replace("{indicators}", indicator_text)

        # Format with placeholders (if template uses them)
        hrv_info = f" HRV: {hrv_deviation_pct:.1f}%;" if hrv_deviation_pct else ""
        consecutive_days_info = f" {consecutive_hard} hard days;" if consecutive_hard >= hard_days_thresholds.get("warning", 3) else ""
        sleep_info = f" Sleep debt: {sleep_debt:.1f}h" if sleep_debt >= sleep_debt_thresholds.get("warning", 3) else ""

        message = message.format(
            hrv_info=hrv_info,
            consecutive_days_info=consecutive_days_info,
            sleep_info=sleep_info,
        )

        return {
            "alert_type": "overtraining",
            "severity": severity,
            "title": title,
            "message": message,
            "recommendation": recommendation,
            "trigger_metrics": {
                "hrv_deviation_pct": hrv_deviation_pct,
                "consecutive_hard_days": consecutive_hard,
                "sleep_debt_hours": sleep_debt,
                "indicators": indicators,
            },
            "trigger_date": target_date,
        }

    def _check_illness_risk(
        self,
        target_date: date,
        baselines: dict[str, Any],
        session: Session,
    ) -> dict[str, Any] | None:
        """
        Check for illness risk signals.

        Criteria:
        - HRV drop + elevated RHR
        - Warning: 20% HRV drop + 5 bpm RHR increase for 2 days
        - Critical: 30% HRV drop + 10 bpm RHR increase for 1 day

        Args:
            target_date: Date to analyze
            baselines: Calculated baseline metrics

        Returns:
            Alert dictionary or None if no illness risk detected
        """
        config = self.config.get("illness", {})
        warning_thresholds = config.get("warning", {})
        critical_thresholds = config.get("critical", {})

        hrv_data = baselines.get("hrv_baseline", {})
        rhr_data = baselines.get("rhr_baseline", {})

        hrv_deviation_pct = hrv_data.get("deviation_pct")
        rhr_deviation_bpm = rhr_data.get("deviation_bpm")

        # Need both HRV drop and RHR elevation
        if hrv_deviation_pct is None or rhr_deviation_bpm is None:
            return None

        if hrv_deviation_pct >= 0 or rhr_deviation_bpm <= 0:
            # No drop in HRV or no elevation in RHR
            return None

        hrv_drop_abs = abs(hrv_deviation_pct)
        rhr_increase = rhr_deviation_bpm

        # Check if consecutive days requirement is met
        consecutive_days = self._count_consecutive_illness_signals(
            target_date,
            session,
            hrv_drop_threshold=warning_thresholds.get("hrv_drop_percent", 20),
            rhr_increase_threshold=warning_thresholds.get("rhr_increase_bpm", 5),
        )

        # Determine severity
        severity = None
        if (hrv_drop_abs >= critical_thresholds.get("hrv_drop_percent", 30)
                and rhr_increase >= critical_thresholds.get("rhr_increase_bpm", 10)
                and consecutive_days >= critical_thresholds.get("consecutive_days", 1)):
            severity = "critical"
        elif (hrv_drop_abs >= warning_thresholds.get("hrv_drop_percent", 20)
                and rhr_increase >= warning_thresholds.get("rhr_increase_bpm", 5)
                and consecutive_days >= warning_thresholds.get("consecutive_days", 2)):
            severity = "warning"

        if not severity:
            return None

        # Build message
        messages = config.get("messages", {}).get(severity, {})
        title = messages.get("title", f"Illness Risk {severity.title()}")
        recommendation = messages.get("recommendation", "Monitor symptoms and prioritize rest.")

        message_template = messages.get(
            "message",
            "HRV down {hrv_drop}%, RHR up {rhr_increase} bpm for {days} days."
        )
        message = message_template.format(
            hrv_drop=hrv_drop_abs,
            rhr_increase=rhr_increase,
            days=consecutive_days,
        )

        return {
            "alert_type": "illness",
            "severity": severity,
            "title": title,
            "message": message,
            "recommendation": recommendation,
            "trigger_metrics": {
                "hrv_drop_percent": hrv_drop_abs,
                "rhr_increase_bpm": rhr_increase,
                "consecutive_days": consecutive_days,
            },
            "trigger_date": target_date,
        }

    def _check_injury_risk(
        self,
        target_date: date,
        baselines: dict[str, Any],
        session: Session,
    ) -> dict[str, Any] | None:
        """
        Check for injury risk signals.

        Criteria:
        - ACWR: >1.3 warning, >1.5 critical
        - Weekly load increase: >15% warning, >25% critical

        Args:
            target_date: Date to analyze
            baselines: Calculated baseline metrics

        Returns:
            Alert dictionary or None if no injury risk detected
        """
        config = self.config.get("injury", {})
        acwr_thresholds = config.get("acwr", {})
        load_increase_thresholds = config.get("weekly_load_increase", {})

        acwr = baselines.get("acwr")
        weekly_load_increase = baselines.get("weekly_load_increase_pct")

        indicators: list[str] = []
        severity_scores: list[int] = []

        # Check ACWR
        if acwr is not None:
            if acwr >= acwr_thresholds.get("critical", 1.5):
                indicators.append(f"ACWR {acwr:.2f} (critical threshold)")
                severity_scores.append(2)
            elif acwr >= acwr_thresholds.get("warning", 1.3):
                indicators.append(f"ACWR {acwr:.2f} (approaching risk zone)")
                severity_scores.append(1)

        # Check weekly load increase
        if weekly_load_increase is not None and weekly_load_increase > 0:
            if weekly_load_increase >= load_increase_thresholds.get("critical", 25):
                indicators.append(f"{weekly_load_increase:.1f}% load increase")
                severity_scores.append(2)
            elif weekly_load_increase >= load_increase_thresholds.get("warning", 15):
                indicators.append(f"{weekly_load_increase:.1f}% load increase")
                severity_scores.append(1)

        if not indicators:
            return None

        severity = "critical" if max(severity_scores, default=0) == 2 else "warning"

        # Determine message context based on ACWR pattern
        comeback_threshold = config.get("acwr", {}).get("comeback_threshold", 0.8)
        message_key = severity  # default fallback

        if acwr is not None:
            # Context-aware message selection
            if acwr < comeback_threshold:
                # Comeback injury pattern: low ACWR + spike = too much too soon
                message_key = f"comeback_{severity}"
            elif acwr >= acwr_thresholds.get("warning", 1.3):
                # Overtraining injury pattern: high ACWR + spike = chronic overload
                message_key = f"overtraining_{severity}"
            # else: normal ACWR (0.8-1.3) uses generic fallback messages

        # Build context-aware message
        messages = config.get("messages", {}).get(message_key, config.get("messages", {}).get(severity, {}))
        title = messages.get("title", f"Injury Risk {severity.title()}")
        recommendation = messages.get("recommendation", "Reduce training volume.")

        load_info = "; ".join(indicators)
        message_template = messages.get("message", "Training load concerns: {load_info}")

        # Format message with context (include ACWR if available)
        if acwr is not None:
            message = message_template.format(load_info=load_info, acwr=acwr)
        else:
            message = message_template.format(load_info=load_info)

        return {
            "alert_type": "injury",
            "severity": severity,
            "title": title,
            "message": message,
            "recommendation": recommendation,
            "trigger_metrics": {
                "acwr": acwr,
                "weekly_load_increase_pct": weekly_load_increase,
                "indicators": indicators,
            },
            "trigger_date": target_date,
        }

    def _calculate_baselines(self, target_date: date, session: Session) -> dict[str, Any]:
        """
        Calculate baseline metrics for comparison.

        Returns:
        - hrv_baseline: 7-day and 30-day average with deviation
        - rhr_baseline: 7-day average with deviation
        - sleep_baseline: 7-day average with sleep debt
        - acwr: acute:chronic workload ratio
        - consecutive_hard_days: count
        - weekly_load_increase_pct: percent change

        Args:
            target_date: Date to calculate baselines for
            session: Database session

        Returns:
            Dictionary with all baseline metrics
        """
        # HRV baseline (30-day)
        hrv_baseline = self._get_hrv_baseline(session, target_date, days=30)

        # RHR baseline (7-day)
        rhr_baseline = self._get_rhr_baseline(session, target_date, days=7)

        # Sleep baseline (7-day)
        sleep_baseline = self._get_sleep_baseline(session, target_date, days=7)

        # ACWR (28-day chronic, 7-day acute)
        acwr = self._calculate_acwr(session, target_date)

        # Consecutive hard days
        activities = self._get_recent_activities(session, target_date, days=14)
        consecutive_hard_days = self.helper.count_consecutive_hard_days(activities, target_date)

        # Weekly load increase
        weekly_load_increase = self.helper.calculate_weekly_load_increase(activities, target_date)

        return {
            "hrv_baseline": hrv_baseline,
            "rhr_baseline": rhr_baseline,
            "sleep_baseline": sleep_baseline,
            "acwr": acwr,
            "consecutive_hard_days": consecutive_hard_days,
            "weekly_load_increase_pct": weekly_load_increase,
        }

    def _get_hrv_baseline(
        self,
        session: Session,
        target_date: date,
        days: int = 30,
    ) -> dict[str, Any]:
        """
        Calculate HRV baseline from historical data.

        Args:
            session: Database session
            target_date: Date to calculate baseline for
            days: Number of days to look back

        Returns:
            Dictionary with baseline_hrv, current_hrv, and deviation_pct
        """
        start_date = target_date - timedelta(days=days)

        # Get historical metrics (EXCLUDE current day)
        metrics = (
            session.query(DailyMetric)
            .filter(
                DailyMetric.date >= start_date,
                DailyMetric.date < target_date,  # EXCLUDE current
                DailyMetric.hrv_morning.isnot(None),
            )
            .order_by(DailyMetric.date)
            .all()
        )

        # Get current day separately
        current_metric = (
            session.query(DailyMetric)
            .filter(
                DailyMetric.date == target_date,
                DailyMetric.hrv_morning.isnot(None),
            )
            .first()
        )

        if not metrics or not current_metric:
            return {"baseline_hrv": None, "current_hrv": None, "deviation_pct": None}

        if len(metrics) < 7:  # Need minimum 7 days
            return {
                "baseline_hrv": None,
                "current_hrv": current_metric.hrv_morning,
                "deviation_pct": None,
            }

        baseline = sum(m.hrv_morning for m in metrics) / len(metrics)
        current = current_metric.hrv_morning
        deviation_pct = ((current - baseline) / baseline) * 100

        return {
            "baseline_hrv": round(baseline, 1),
            "current_hrv": current,
            "deviation_pct": round(deviation_pct, 1),
        }

    def _get_rhr_baseline(
        self,
        session: Session,
        target_date: date,
        days: int = 7,
    ) -> dict[str, Any]:
        """
        Calculate resting heart rate baseline.

        Args:
            session: Database session
            target_date: Date to calculate baseline for
            days: Number of days to look back

        Returns:
            Dictionary with baseline_rhr, current_rhr, and deviation_bpm
        """
        start_date = target_date - timedelta(days=days)

        metrics = (
            session.query(DailyMetric)
            .filter(
                DailyMetric.date >= start_date,
                DailyMetric.date <= target_date,
                DailyMetric.resting_hr.isnot(None),
            )
            .order_by(DailyMetric.date)
            .all()
        )

        if not metrics:
            return {"baseline_rhr": None, "current_rhr": None, "deviation_bpm": None}

        rhr_values = [m.resting_hr for m in metrics]

        if len(rhr_values) < 3:
            return {"baseline_rhr": None, "current_rhr": rhr_values[-1], "deviation_bpm": None}

        baseline = sum(rhr_values[:-1]) / len(rhr_values[:-1])
        current = rhr_values[-1]
        deviation_bpm = current - baseline

        return {
            "baseline_rhr": round(baseline, 1),
            "current_rhr": current,
            "deviation_bpm": round(deviation_bpm, 1),
        }

    def _get_sleep_baseline(
        self,
        session: Session,
        target_date: date,
        days: int = 7,
    ) -> dict[str, Any]:
        """
        Calculate sleep baseline and debt.

        Args:
            session: Database session
            target_date: Date to calculate baseline for
            days: Number of days to look back

        Returns:
            Dictionary with baseline_hours, current_hours, and sleep_debt_hours
        """
        start_date = target_date - timedelta(days=days)

        metrics = (
            session.query(DailyMetric)
            .filter(
                DailyMetric.date >= start_date,
                DailyMetric.date <= target_date,
                DailyMetric.sleep_seconds.isnot(None),
            )
            .order_by(DailyMetric.date)
            .all()
        )

        if not metrics:
            return {"baseline_hours": None, "current_hours": None, "sleep_debt_hours": None}

        sleep_hours = [m.sleep_seconds / 3600 for m in metrics]

        if len(sleep_hours) < 3:
            return {
                "baseline_hours": None,
                "current_hours": sleep_hours[-1],
                "sleep_debt_hours": None,
            }

        baseline = sum(sleep_hours[:-1]) / len(sleep_hours[:-1])
        current = sleep_hours[-1]

        # Calculate cumulative debt (baseline * days - actual total)
        total_baseline = baseline * len(sleep_hours)
        total_actual = sum(sleep_hours)
        sleep_debt = total_baseline - total_actual

        return {
            "baseline_hours": round(baseline, 1),
            "current_hours": round(current, 1),
            "sleep_debt_hours": round(sleep_debt, 1),
        }

    def _calculate_acwr(self, session: Session, target_date: date) -> float | None:
        """
        Calculate acute:chronic workload ratio.

        Args:
            session: Database session
            target_date: Date to calculate ACWR for

        Returns:
            ACWR value or None if insufficient data
        """
        # Get last 28 days of activities
        start_date = target_date - timedelta(days=28)
        activities = (
            session.query(Activity)
            .filter(Activity.date >= start_date, Activity.date <= target_date)
            .all()
        )

        if not activities:
            return None

        # Separate acute (last 7 days) and chronic (last 28 days)
        acute_cutoff = target_date - timedelta(days=7)
        acute_load = 0.0
        chronic_load = 0.0

        for activity in activities:
            # Calculate load
            if activity.training_load:
                load = float(activity.training_load)
            elif activity.aerobic_training_effect:
                load = float(activity.aerobic_training_effect) * 10
            else:
                continue

            chronic_load += load
            if activity.date > acute_cutoff:
                acute_load += load

        # Chronic load is average per week
        chronic_load_weekly = chronic_load / 4

        if chronic_load_weekly == 0:
            return None

        acwr = acute_load / chronic_load_weekly
        return round(acwr, 2)

    def _get_recent_activities(
        self,
        session: Session,
        target_date: date,
        days: int = 14,
    ) -> list[Activity]:
        """
        Get recent activities for analysis.

        Args:
            session: Database session
            target_date: Date to get activities up to
            days: Number of days to look back

        Returns:
            List of Activity objects
        """
        start_date = target_date - timedelta(days=days)
        return (
            session.query(Activity)
            .filter(Activity.date >= start_date, Activity.date <= target_date)
            .order_by(Activity.date)
            .all()
        )

    def _count_consecutive_illness_signals(
        self,
        target_date: date,
        session: Session,
        hrv_drop_threshold: float,
        rhr_increase_threshold: float,
    ) -> int:
        """
        Count consecutive days with both HRV drop and RHR elevation.

        Args:
            target_date: Date to count backwards from
            session: Database session
            hrv_drop_threshold: Minimum HRV drop percentage
            rhr_increase_threshold: Minimum RHR increase in bpm

        Returns:
            Number of consecutive days with both signals
        """
        consecutive = 0
        check_date = target_date

        # Check up to 7 days back
        for _ in range(7):
            # Get baselines for this date
            hrv_data = self._get_hrv_baseline(session, check_date, days=30)
            rhr_data = self._get_rhr_baseline(session, check_date, days=7)

            hrv_deviation = hrv_data.get("deviation_pct")
            rhr_deviation = rhr_data.get("deviation_bpm")

            # Check if both conditions met
            if (hrv_deviation is not None
                    and rhr_deviation is not None
                    and hrv_deviation < 0
                    and abs(hrv_deviation) >= hrv_drop_threshold
                    and rhr_deviation >= rhr_increase_threshold):
                consecutive += 1
                check_date -= timedelta(days=1)
            else:
                break

        return consecutive

    def _store_alert(self, session: Session, alert_data: dict[str, Any]) -> None:
        """
        Store alert in database with race condition protection.

        Uses optimistic locking pattern: attempt INSERT first,
        then UPDATE on conflict. This prevents TOCTOU race conditions.

        Args:
            session: Database session
            alert_data: Alert dictionary from detection methods
        """
        from datetime import datetime

        from sqlalchemy import and_
        from sqlalchemy.exc import IntegrityError

        try:
            # Optimistic INSERT - attempt to create new alert
            alert = TrainingAlert(
                alert_type=alert_data["alert_type"],
                severity=alert_data["severity"],
                title=alert_data["title"],
                message=alert_data["message"],
                recommendation=alert_data["recommendation"],
                trigger_date=alert_data["trigger_date"],
                trigger_metrics=sanitize_trigger_metrics(alert_data["trigger_metrics"]),
                status="active",
                priority=1 if alert_data["severity"] == "critical" else 2,
            )

            session.add(alert)
            session.flush()

            logger.info(
                "Created new %s alert for %s",
                alert_data["alert_type"],
                alert_data["trigger_date"].isoformat(),
            )

        except IntegrityError:
            # Alert exists, update it with row-level lock
            session.rollback()

            existing = (
                session.query(TrainingAlert)
                .filter(
                    and_(
                        TrainingAlert.trigger_date == alert_data["trigger_date"],
                        TrainingAlert.alert_type == alert_data["alert_type"],
                        TrainingAlert.status == "active",
                    )
                )
                .with_for_update()
                .first()
            )

            if existing:
                existing.severity = alert_data["severity"]
                existing.title = alert_data["title"]
                existing.message = alert_data["message"]
                existing.recommendation = alert_data["recommendation"]
                existing.trigger_metrics = sanitize_trigger_metrics(alert_data["trigger_metrics"])
                existing.updated_at = datetime.utcnow()

                logger.info(
                    "Updated existing %s alert for %s",
                    alert_data["alert_type"],
                    alert_data["trigger_date"].isoformat(),
                )

        session.commit()
