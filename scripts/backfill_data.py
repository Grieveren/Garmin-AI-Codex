"""Backfill historical Garmin data into database."""
import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal, run_migrations
from app.models.database_models import DailyMetric, Activity
from app.services.garmin_service import GarminService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill historical Garmin data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Backfill 30 days (default)
  python scripts/backfill_data.py

  # Backfill 60 days
  python scripts/backfill_data.py --days 60

  # Backfill with MFA code
  python scripts/backfill_data.py --days 30 --mfa-code 123456
        """
    )
    parser.add_argument("--days", type=int, default=30, help="How many days to backfill (default: 30)")
    parser.add_argument("--mfa-code", type=str, help="6-digit MFA code if needed")
    parser.add_argument("--force", action="store_true", help="Overwrite existing data")
    return parser.parse_args()


def fetch_daily_metrics(garmin: GarminService, target_date: date) -> dict | None:
    """Fetch all metrics for a specific date."""
    date_str = target_date.isoformat()

    try:
        # Fetch all relevant data
        stats = garmin._client.get_stats(date_str)
        sleep = garmin._client.get_sleep_data(date_str)
        hrv = garmin._client.get_hrv_data(date_str)
        hr = garmin._client.get_heart_rates(date_str)
        stress = garmin._client.get_stress_data(date_str)
        body_battery = garmin._client.get_body_battery(date_str)

        # Extract metrics
        metrics = {
            "date": target_date,
            "steps": stats.get("totalSteps"),
            "distance_meters": stats.get("totalDistanceMeters"),
            "active_calories": stats.get("activeKilocalories"),
        }

        # Heart rate
        if hr and not isinstance(hr, dict) or "error" not in hr:
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
            # Calculate max from charged values
            max_vals = [bb.get("charged", 0) for bb in body_battery if "charged" in bb]
            if max_vals:
                metrics["body_battery_max"] = max(max_vals)

        return metrics

    except Exception as e:
        print(f"  ⚠️  Error fetching data for {date_str}: {e}")
        return None


def save_daily_metric(db: Session, metrics: dict, force: bool = False) -> bool:
    """Save daily metrics to database."""
    existing = db.query(DailyMetric).filter(DailyMetric.date == metrics["date"]).first()

    if existing and not force:
        return False  # Skip existing

    if existing:
        # Update existing
        for key, value in metrics.items():
            if key != "date":
                setattr(existing, key, value)
        existing.updated_at = datetime.utcnow()
    else:
        # Create new
        metric = DailyMetric(**metrics)
        db.add(metric)

    db.commit()
    return True


def fetch_activities(garmin: GarminService, days: int) -> list[dict]:
    """Fetch activities for the specified time period."""
    try:
        # Get more activities than days to ensure coverage
        activities = garmin._client.get_activities(0, days * 3)

        cutoff_date = date.today() - timedelta(days=days)
        filtered = []

        for activity in activities:
            if not activity.get("startTimeLocal"):
                continue

            activity_date_str = activity["startTimeLocal"][:10]
            activity_date = date.fromisoformat(activity_date_str)

            if activity_date >= cutoff_date:
                filtered.append({
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
                })

        return filtered

    except Exception as e:
        print(f"⚠️  Error fetching activities: {e}")
        return []


def save_activity(db: Session, activity_data: dict, force: bool = False) -> bool:
    """Save activity to database."""
    existing = db.query(Activity).filter(Activity.id == activity_data["id"]).first()

    if existing and not force:
        return False  # Skip existing

    if existing:
        # Update existing
        for key, value in activity_data.items():
            if key != "id":
                setattr(existing, key, value)
        existing.updated_at = datetime.utcnow()
    else:
        # Create new
        activity = Activity(**activity_data)
        db.add(activity)

    db.commit()
    return True


def main() -> None:
    args = parse_args()
    get_settings()
    print("Ensuring database schema is up to date...")
    run_migrations()

    # Initialize Garmin service
    print(f"\n🔐 Connecting to Garmin Connect...")
    garmin = GarminService()

    try:
        garmin.login(mfa_code=args.mfa_code)
        print("✅ Logged in successfully\n")
    except Exception as e:
        print(f"❌ Login failed: {e}")
        return

    # Calculate date range
    start_date = date.today() - timedelta(days=args.days)
    end_date = date.today()
    total_days = (end_date - start_date).days

    print(f"📅 Backfilling data from {start_date} to {end_date} ({total_days} days)")
    print(f"{'='*60}\n")

    db = SessionLocal()
    saved_metrics = 0
    skipped_metrics = 0
    failed_metrics = 0

    # Fetch daily metrics
    print("Fetching daily metrics...")
    for i in range(total_days):
        current_date = start_date + timedelta(days=i)
        print(f"  [{i+1}/{total_days}] {current_date}...", end=" ")

        metrics = fetch_daily_metrics(garmin, current_date)

        if metrics:
            saved = save_daily_metric(db, metrics, force=args.force)
            if saved:
                print("✅ Saved")
                saved_metrics += 1
            else:
                print("⏭️  Skipped (already exists)")
                skipped_metrics += 1
        else:
            print("❌ Failed")
            failed_metrics += 1

    # Fetch activities
    print(f"\nFetching activities...")
    activities = fetch_activities(garmin, args.days)
    print(f"Found {len(activities)} activities in the last {args.days} days")

    saved_activities = 0
    skipped_activities = 0

    for activity in activities:
        existing = db.query(Activity).filter(Activity.id == activity["id"]).first()
        if existing and not args.force:
            skipped_activities += 1
            continue

        saved = save_activity(db, activity, force=args.force)
        if saved:
            saved_activities += 1

    print(f"✅ Saved {saved_activities} activities")
    if skipped_activities > 0:
        print(f"⏭️  Skipped {skipped_activities} activities (already exist)")

    # Summary
    print(f"\n{'='*60}")
    print(f"📊 Summary:")
    print(f"  Daily Metrics: {saved_metrics} saved, {skipped_metrics} skipped, {failed_metrics} failed")
    print(f"  Activities: {saved_activities} saved, {skipped_activities} skipped")
    print(f"\n✅ Backfill complete!")

    db.close()
    garmin.logout()


if __name__ == "__main__":
    main()
