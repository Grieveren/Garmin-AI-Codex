#!/usr/bin/env python3
"""Test script to explore what activity details are available from Garmin API."""

import json
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.garmin_service import GarminService


def explore_activity_details():
    """Fetch and display activity details to see available fields."""

    print("Connecting to Garmin...")
    garmin = GarminService()

    try:
        garmin.login()
        print("✓ Logged in successfully\n")

        # Get recent activities
        print("Fetching recent activities...")
        activities = garmin._client.get_activities(0, 5)  # Get last 5 activities

        if not activities:
            print("No activities found")
            return

        print(f"Found {len(activities)} recent activities\n")

        # Pick the first running activity if available
        running_activity = None
        for activity in activities:
            activity_type = activity.get("activityType", {}).get("typeKey", "")
            if "running" in activity_type.lower():
                running_activity = activity
                break

        # If no running activity, just use the first one
        test_activity = running_activity or activities[0]
        activity_id = test_activity.get("activityId")
        activity_name = test_activity.get("activityName", "Unknown")
        activity_type = test_activity.get("activityType", {}).get("typeKey", "Unknown")

        print(f"Testing with activity: {activity_name}")
        print(f"  Type: {activity_type}")
        print(f"  ID: {activity_id}\n")

        # Get basic activity data (what we currently use)
        print("=" * 80)
        print("BASIC ACTIVITY DATA (from get_activities):")
        print("=" * 80)
        basic_fields = {
            "activityId": test_activity.get("activityId"),
            "activityName": test_activity.get("activityName"),
            "activityType": test_activity.get("activityType", {}).get("typeKey"),
            "duration": test_activity.get("duration"),
            "distance": test_activity.get("distance"),
            "averageHR": test_activity.get("averageHR"),
            "maxHR": test_activity.get("maxHR"),
            "aerobicTrainingEffect": test_activity.get("aerobicTrainingEffect"),
            "anaerobicTrainingEffect": test_activity.get("anaerobicTrainingEffect"),
            "elevationGain": test_activity.get("elevationGain"),
            "calories": test_activity.get("calories"),
        }
        print(json.dumps(basic_fields, indent=2))

        # Get detailed activity data
        print("\n" + "=" * 80)
        print("DETAILED ACTIVITY DATA (from get_activity_details):")
        print("=" * 80)

        details = garmin._client.get_activity_details(activity_id)

        # Look for running dynamics fields
        running_dynamics_keywords = [
            "cadence", "power", "stride", "groundContact", "verticalOscillation",
            "verticalRatio", "groundContactTime", "gct", "dynamics", "impact",
            "stress", "balance", "form"
        ]

        print("\nSearching for running dynamics fields...")
        found_fields = {}

        def search_dict(d, prefix=""):
            """Recursively search for running dynamics fields."""
            if not isinstance(d, dict):
                return

            for key, value in d.items():
                full_key = f"{prefix}.{key}" if prefix else key

                # Check if this key matches any running dynamics keyword
                for keyword in running_dynamics_keywords:
                    if keyword.lower() in key.lower():
                        found_fields[full_key] = value
                        break

                # Recurse into nested dicts
                if isinstance(value, dict):
                    search_dict(value, full_key)
                elif isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                    # Only search first item in lists to avoid spam
                    search_dict(value[0], f"{full_key}[0]")

        search_dict(details)

        if found_fields:
            print(f"\n✓ FOUND {len(found_fields)} running dynamics-related fields:")
            print(json.dumps(found_fields, indent=2))
        else:
            print("\n✗ No running dynamics fields found in activity details")

        # Save full details to file for manual inspection
        output_file = Path(__file__).parent / "activity_details_sample.json"
        with open(output_file, "w") as f:
            json.dump(details, f, indent=2, default=str)
        print(f"\n✓ Full activity details saved to: {output_file}")

        # Show top-level keys
        print("\n" + "=" * 80)
        print("TOP-LEVEL KEYS IN ACTIVITY DETAILS:")
        print("=" * 80)
        print(json.dumps(list(details.keys()), indent=2))

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            garmin.logout()
        except:
            pass


if __name__ == "__main__":
    explore_activity_details()
