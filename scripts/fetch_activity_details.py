#!/usr/bin/env python3
"""
Script to fetch detailed activity data from Garmin API.

Usage:
    # Fetch details for a specific activity
    python scripts/fetch_activity_details.py --activity-id 12345678

    # Fetch details for recent activities (last 30 days)
    python scripts/fetch_activity_details.py --recent-days 30 --limit 20

    # Force refetch (ignore cache)
    python scripts/fetch_activity_details.py --activity-id 12345678 --force

Example:
    $ python scripts/fetch_activity_details.py --activity-id 12345678
    Fetching details for activity 12345678...
    ✓ Splits: 10 laps
    ✓ HR Zones: 5 zones
    ✓ Weather: 15°C, cloudy
    Pace Consistency: 87.5/100
    HR Drift: +4.8%
"""
import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal, engine, Base
from app.models.database_models import Activity
from app.services.garmin_service import GarminService
from app.services.activity_detail_service import ActivityDetailService


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_single_activity(
    service: ActivityDetailService,
    activity_id: int,
    force: bool = False
) -> None:
    """Fetch and display details for a single activity."""
    logger.info("Fetching details for activity %d", activity_id)

    result = service.fetch_and_store_details(activity_id, force_refetch=force)

    # Display results
    print(f"\n{'='*60}")
    print(f"Activity {activity_id} Details")
    print(f"{'='*60}")

    if result["cached"]:
        print("✓ Using cached data")
    else:
        print("✓ Fetched from API")

    print(f"\nData Completeness: {'✓ Complete' if result['is_complete'] else '⚠ Partial'}")

    # Splits
    if result["splits"]:
        laps = result["splits"].get("lapDTOs", [])
        print(f"✓ Splits: {len(laps)} laps")
    else:
        print("✗ Splits: Not available")

    # HR Zones
    if result["hr_zones"]:
        zones = result["hr_zones"].get("timeInZones", [])
        print(f"✓ HR Zones: {len(zones)} zones")

        # Show zone distribution
        total_time = sum(z.get("duration", 0) for z in zones)
        if total_time > 0:
            print("\n  Zone Distribution:")
            for zone in zones:
                zone_num = zone.get("zone", 0)
                duration = zone.get("duration", 0)
                percent = (duration / total_time) * 100
                print(f"    Zone {zone_num}: {duration}s ({percent:.1f}%)")
    else:
        print("✗ HR Zones: Not available")

    # Weather
    if result["weather"]:
        temp = result["weather"].get("temperature")
        condition = result["weather"].get("weatherCondition", "unknown")
        humidity = result["weather"].get("humidity")

        weather_str = f"{temp}°C, {condition}" if temp else condition
        if humidity:
            weather_str += f", {humidity}% humidity"

        print(f"✓ Weather: {weather_str}")
    else:
        print("✗ Weather: Not available")

    # Derived metrics
    print("\nDerived Metrics:")
    if result["pace_consistency_score"] is not None:
        score = result["pace_consistency_score"]
        rating = "Excellent" if score >= 90 else "Good" if score >= 75 else "Fair" if score >= 60 else "Poor"
        print(f"  Pace Consistency: {score:.1f}/100 ({rating})")
    else:
        print("  Pace Consistency: Not available")

    if result["hr_drift_percent"] is not None:
        drift = result["hr_drift_percent"]
        direction = "↑" if drift > 0 else "↓" if drift < 0 else "→"
        print(f"  HR Drift: {direction} {abs(drift):.1f}%")
    else:
        print("  HR Drift: Not available")

    # Errors
    if result["errors"]:
        print(f"\n⚠ Failed to fetch: {', '.join(result['errors'])}")

    print(f"\nFetched at: {result['fetched_at']}")
    print(f"{'='*60}\n")


def fetch_recent_activities(
    service: ActivityDetailService,
    session: Session,
    days: int = 30,
    limit: int | None = None
) -> None:
    """Fetch details for recent activities."""
    start_date = date.today() - timedelta(days=days)

    # Get recent activities
    activities = (
        session.query(Activity)
        .filter(Activity.date >= start_date)
        .order_by(Activity.date.desc())
        .all()
    )

    if not activities:
        print(f"No activities found in the last {days} days")
        return

    print(f"\nFound {len(activities)} activities in the last {days} days")
    activity_ids = [a.id for a in activities]

    # Bulk fetch
    result = service.bulk_fetch_recent_activities(activity_ids, limit=limit)

    # Display summary
    print(f"\n{'='*60}")
    print("Bulk Fetch Summary")
    print(f"{'='*60}")
    print(f"Total activities: {result['total']}")
    print(f"Cached: {result['cached']}")
    print(f"Fetched: {result['fetched']}")
    print(f"Failed: {result['failed']}")
    print(f"Skipped (limit): {result['skipped']}")

    if result["activity_ids_fetched"]:
        print(f"\nSuccessfully fetched: {result['activity_ids_fetched'][:5]}")
        if len(result["activity_ids_fetched"]) > 5:
            print(f"  ... and {len(result['activity_ids_fetched']) - 5} more")

    if result["activity_ids_failed"]:
        print(f"\nFailed: {result['activity_ids_failed']}")

    print(f"{'='*60}\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch detailed activity data from Garmin API"
    )

    parser.add_argument(
        "--activity-id",
        type=int,
        help="Specific activity ID to fetch"
    )

    parser.add_argument(
        "--recent-days",
        type=int,
        help="Fetch details for activities in the last N days"
    )

    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of API calls (for rate limiting)"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force refetch, ignore cache"
    )

    parser.add_argument(
        "--mfa-code",
        type=str,
        help="Garmin MFA code (if needed)"
    )

    args = parser.parse_args()

    if not args.activity_id and not args.recent_days:
        parser.error("Must specify either --activity-id or --recent-days")

    # Initialize database
    Base.metadata.create_all(engine)
    session = SessionLocal()

    try:
        # Initialize Garmin service
        garmin = GarminService()

        try:
            logger.info("Logging in to Garmin...")
            garmin.login(mfa_code=args.mfa_code)
        except RuntimeError as err:
            if "MFA" in str(err):
                print("\n⚠ MFA code required. Provide with --mfa-code argument")
                sys.exit(1)
            raise

        # Initialize activity detail service
        detail_service = ActivityDetailService(garmin, session)

        # Fetch based on arguments
        if args.activity_id:
            fetch_single_activity(detail_service, args.activity_id, args.force)
        elif args.recent_days:
            fetch_recent_activities(
                detail_service,
                session,
                args.recent_days,
                args.limit
            )

    except Exception as err:
        logger.exception("Error fetching activity details")
        print(f"\n✗ Error: {err}")
        sys.exit(1)

    finally:
        try:
            garmin.logout()
        except Exception:
            pass
        session.close()

    print("✓ Done")


if __name__ == "__main__":
    main()
