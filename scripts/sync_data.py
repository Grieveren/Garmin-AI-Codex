"""Daily sync script - fetches yesterday's data and saves to database."""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal, run_migrations
from app.logging_config import configure_logging
from app.models.database_models import DailyMetric, Activity
from app.services.garmin_service import GarminService


logger = logging.getLogger("scripts.sync_data")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Daily Garmin data sync",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Sync yesterday's data (default for daily cron)
  python scripts/sync_data.py

  # Sync specific date
  python scripts/sync_data.py --date 2025-10-16

  # Force overwrite existing data
  python scripts/sync_data.py --force
        """
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Specific date to sync (YYYY-MM-DD). Defaults to yesterday."
    )
    parser.add_argument(
        "--mfa-code",
        type=str,
        help="Six-digit Garmin MFA code (only needed if token expired)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing data for the date"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output"
    )
    return parser.parse_args()


def fetch_daily_metrics(garmin: GarminService, target_date: date, verbose: bool = False) -> dict | None:
    """Fetch all metrics for a specific date."""
    date_str = target_date.isoformat()

    if verbose:
        logger.info("Fetching data for %s", date_str)

    try:
        # Fetch all relevant data
        stats = garmin._client.get_stats(date_str)
        sleep = garmin._client.get_sleep_data(date_str)
        hrv = garmin._client.get_hrv_data(date_str)
        hr = garmin._client.get_heart_rates(date_str)
        stress = garmin._client.get_stress_data(date_str)
        body_battery = garmin._client.get_body_battery(date_str)

        # Fetch enhanced metrics (Phase 1)
        try:
            training_readiness = garmin._client.get_training_readiness(date_str)
        except Exception:
            training_readiness = None

        try:
            training_status = garmin._client.get_training_status(date_str)
        except Exception:
            training_status = None

        try:
            spo2 = garmin._client.get_spo2_data(date_str)
        except Exception:
            spo2 = None

        try:
            respiration = garmin._client.get_respiration_data(date_str)
        except Exception:
            respiration = None

        # Extract metrics
        metrics = {
            "date": target_date,
            "steps": stats.get("totalSteps"),
            "distance_meters": stats.get("totalDistanceMeters"),
            "active_calories": stats.get("activeKilocalories"),
        }

        # Heart rate
        if hr and (not isinstance(hr, dict) or "error" not in hr):
            metrics["resting_hr"] = hr.get("restingHeartRate")
            metrics["max_hr"] = hr.get("maxHeartRate")

        # HRV
        if hrv and "hrvSummary" in hrv:
            metrics["hrv_morning"] = hrv["hrvSummary"].get("lastNightAvg")

        # Sleep
        if sleep and "dailySleepDTO" in sleep:
            sleep_dto = sleep["dailySleepDTO"]
            metrics["sleep_seconds"] = sleep_dto.get("sleepTimeSeconds")
            metrics["deep_sleep_seconds"] = sleep_dto.get("deepSleepSeconds")
            metrics["light_sleep_seconds"] = sleep_dto.get("lightSleepSeconds")
            metrics["rem_sleep_seconds"] = sleep_dto.get("remSleepSeconds")

            sleep_scores = sleep_dto.get("sleepScores", {}).get("overall", {})
            metrics["sleep_score"] = sleep_scores.get("value")

        # Stress
        if stress and isinstance(stress, list) and stress:
            stress_values = [s.get("stressLevel", 0) for s in stress if isinstance(s, dict) and "stressLevel" in s]
            if stress_values:
                metrics["stress_avg"] = int(sum(stress_values) / len(stress_values))

        # Body Battery
        if body_battery and isinstance(body_battery, list) and body_battery:
            latest = body_battery[-1]
            metrics["body_battery_charged"] = latest.get("charged")
            metrics["body_battery_drained"] = latest.get("drained")
            max_vals = [bb.get("charged", 0) for bb in body_battery if "charged" in bb]
            if max_vals:
                metrics["body_battery_max"] = max(max_vals)

        # Training Readiness Score (Garmin's AI readiness 0-100)
        # API returns a list, extract first item if available - uses "score" key
        if training_readiness and isinstance(training_readiness, list) and len(training_readiness) > 0:
            if isinstance(training_readiness[0], dict):
                metrics["training_readiness_score"] = training_readiness[0].get("score")
        elif training_readiness and isinstance(training_readiness, dict):
            metrics["training_readiness_score"] = training_readiness.get("score")

        # Training Status (VO2 max, training status)
        if training_status and isinstance(training_status, dict):
            # VO2 Max - nested in mostRecentVO2Max → generic → vo2MaxValue
            if "mostRecentVO2Max" in training_status:
                vo2_data = training_status.get("mostRecentVO2Max")
                if vo2_data and isinstance(vo2_data, dict):
                    generic = vo2_data.get("generic")
                    if generic and isinstance(generic, dict):
                        metrics["vo2_max"] = generic.get("vo2MaxValue")

            # Training Status - nested in mostRecentTrainingStatus → latestTrainingStatusData → {deviceId}
            if "mostRecentTrainingStatus" in training_status:
                status_data = training_status.get("mostRecentTrainingStatus")
                if status_data and isinstance(status_data, dict):
                    latest = status_data.get("latestTrainingStatusData")
                    if latest and isinstance(latest, dict):
                        # Get first device's data (usually primary device)
                        for device_id, device_data in latest.items():
                            if device_data and isinstance(device_data, dict):
                                metrics["training_status"] = device_data.get("trainingStatusFeedbackPhrase")
                                break

        # Recovery Time - from training_readiness API (in minutes, convert to hours)
        recovery_time_hours = garmin.extract_recovery_time(training_readiness)
        if recovery_time_hours is not None:
            metrics["recovery_time_hours"] = recovery_time_hours
            if verbose:
                logger.info("Recovery time: %d hours", recovery_time_hours)

        # SPO2 (Blood Oxygen) - Garmin uses different keys
        if spo2 and isinstance(spo2, dict):
            # Keys are at root level: avgSleepSpO2, lowestSpO2
            if "avgSleepSpO2" in spo2:
                metrics["spo2_avg"] = spo2.get("avgSleepSpO2")
            if "lowestSpO2" in spo2:
                metrics["spo2_min"] = spo2.get("lowestSpO2")

        # Respiration Rate - Garmin uses avgSleepRespirationValue
        if respiration and isinstance(respiration, dict):
            if "avgSleepRespirationValue" in respiration:
                metrics["respiration_avg"] = respiration.get("avgSleepRespirationValue")

        return metrics

    except Exception as e:
        logger.warning("Error fetching data for %s: %s", date_str, e)
        return None


def save_daily_metric(db: Session, metrics: dict, force: bool = False, verbose: bool = False) -> bool:
    """Save daily metrics to database."""
    existing = db.query(DailyMetric).filter(DailyMetric.date == metrics["date"]).first()

    if existing and not force:
        if verbose:
            logger.info("Data already exists for %s, skipping", metrics["date"])
        return False

    if existing:
        # Update existing
        for key, value in metrics.items():
            if key != "date":
                setattr(existing, key, value)
        existing.updated_at = datetime.utcnow()
        if verbose:
            logger.info("Updated existing daily metrics record for %s", metrics["date"])
    else:
        # Create new
        metric = DailyMetric(**metrics)
        db.add(metric)
        if verbose:
            logger.info("Created new daily metrics record for %s", metrics["date"])

    db.commit()
    return True


def fetch_and_save_activities(garmin: GarminService, target_date: date, db: Session, force: bool = False, verbose: bool = False) -> tuple[int, int]:
    """Fetch and save activities for the target date."""
    try:
        # Get recent activities (last 10 should cover today)
        activities = garmin._client.get_activities(0, 10)

        saved_count = 0
        skipped_count = 0

        for activity in activities:
            if not activity.get("startTimeLocal"):
                continue

            activity_date_str = activity["startTimeLocal"][:10]
            activity_date = date.fromisoformat(activity_date_str)

            # Only save if it's the target date
            if activity_date != target_date:
                continue

            activity_data = {
                "id": activity.get("activityId"),
                "date": activity_date,
                "activity_type": activity.get("activityType", {}).get("typeKey"),
                "activity_name": activity.get("activityName"),
                "duration_seconds": activity.get("duration"),
                "distance_meters": activity.get("distance"),
                "aerobic_training_effect": activity.get("aerobicTrainingEffect"),
                "anaerobic_training_effect": activity.get("anaerobicTrainingEffect"),
                "training_load": activity.get("trainingEffect"),
                "avg_hr": activity.get("averageHR"),
                "max_hr": activity.get("maxHR"),
                "avg_pace": activity.get("avgPace"),
                "elevation_gain": activity.get("elevationGain"),
                "calories": activity.get("calories"),
                "start_time": datetime.fromisoformat(activity["startTimeLocal"].replace("Z", "+00:00")) if activity.get("startTimeLocal") else None,
            }

            existing = db.query(Activity).filter(Activity.id == activity_data["id"]).first()

            if existing and not force:
                skipped_count += 1
                continue

            if existing:
                # Update
                for key, value in activity_data.items():
                    if key != "id":
                        setattr(existing, key, value)
                existing.updated_at = datetime.utcnow()
            else:
                # Create
                activity_obj = Activity(**activity_data)
                db.add(activity_obj)

            saved_count += 1
            if verbose:
                logger.info(
                    "Saved activity '%s' on %s",
                    activity_data["activity_name"],
                    activity_date,
                )

        db.commit()
        return saved_count, skipped_count

    except Exception as e:
        logger.warning("Error fetching activities for %s: %s", target_date, e)
        return 0, 0


def main() -> None:
    args = parse_args()

    configure_logging()
    # Validate configuration early to surface missing credentials before work begins.
    get_settings()

    # Determine target date
    if args.date:
        try:
            target_date = date.fromisoformat(args.date)
        except ValueError:
            logger.error("❌ Invalid date format: %s. Use YYYY-MM-DD", args.date)
            sys.exit(1)
    else:
        # Default to yesterday for daily cron
        target_date = date.today() - timedelta(days=1)

    logger.info("🔄 Syncing Garmin data for %s", target_date)
    logger.info("%s", "=" * 50)

    # Ensure database schema is up to date
    run_migrations()

    # Initialize Garmin service
    if args.verbose:
        logger.info("🔐 Connecting to Garmin Connect...")

    garmin = GarminService()

    try:
        garmin.login(mfa_code=args.mfa_code)
        if args.verbose:
            logger.info("✅ Logged in successfully")
    except Exception as e:
        logger.error("❌ Login failed: %s", e)
        logger.error("Note: If token expired, provide MFA code: --mfa-code 123456")
        sys.exit(1)

    db = SessionLocal()

    try:
        # Fetch and save daily metrics
        if args.verbose:
            logger.info("📊 Fetching daily metrics...")

        metrics = fetch_daily_metrics(garmin, target_date, args.verbose)

        if metrics:
            saved = save_daily_metric(db, metrics, force=args.force, verbose=args.verbose)
            if saved:
                logger.info("✅ Daily metrics saved")
            else:
                logger.info("⏭️  Daily metrics already exist (use --force to overwrite)")
        else:
            logger.warning("⚠️  No daily metrics available")

        # Fetch and save activities
        if args.verbose:
            logger.info("🏃 Fetching activities...")

        saved_count, skipped_count = fetch_and_save_activities(
            garmin, target_date, db, force=args.force, verbose=args.verbose
        )

        if saved_count > 0:
            logger.info("✅ Saved %d activity(ies)", saved_count)
        if skipped_count > 0:
            logger.info("⏭️  Skipped %d existing activity(ies)", skipped_count)
        if saved_count == 0 and skipped_count == 0:
            logger.info("ℹ️  No activities found for %s", target_date)

        logger.info("%s", "=" * 50)
        logger.info("✅ Sync complete for %s", target_date)

    finally:
        db.close()
        try:
            garmin.logout()
        except Exception:
            pass


if __name__ == "__main__":
    main()
