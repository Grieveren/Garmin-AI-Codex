"""Debug script to test Garmin personal info and lactate threshold fetching."""
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.garmin_service import GarminService


def main():
    """Test different Garmin API endpoints to find lactate threshold and personal data."""

    garmin = GarminService()

    try:
        print("Logging into Garmin...")
        garmin.login()
        print("✓ Login successful\n")

        # Test 1: Current implementation (personal-information endpoint)
        print("=" * 70)
        print("TEST 1: get_personal_info() - current implementation")
        print("=" * 70)
        personal_info = garmin.get_personal_info()
        print(json.dumps(personal_info, indent=2))
        print()

        # Test 2: Training status (might contain lactate threshold)
        print("=" * 70)
        print("TEST 2: get_training_status() - check for lactate threshold")
        print("=" * 70)
        try:
            from datetime import date
            training_status = garmin._client.get_training_status(date.today().isoformat())
            print(json.dumps(training_status, indent=2, default=str))
        except Exception as e:
            print(f"Error: {e}")
        print()

        # Test 3: Max metrics (might contain lactate threshold)
        print("=" * 70)
        print("TEST 3: get_max_metrics() - check for lactate threshold")
        print("=" * 70)
        try:
            max_metrics = garmin._client.get_max_metrics(date.today().isoformat())
            print(json.dumps(max_metrics, indent=2, default=str))
        except Exception as e:
            print(f"Error: {e}")
        print()

        # Test 4: User settings (might contain age/personal data)
        print("=" * 70)
        print("TEST 4: User settings via connectapi")
        print("=" * 70)
        try:
            settings = garmin._client.garth.connectapi("/userprofile-service/userprofile/user-settings")
            print(json.dumps(settings, indent=2, default=str))
        except Exception as e:
            print(f"Error: {e}")
        print()

        # Test 5: Social profile (might contain age)
        print("=" * 70)
        print("TEST 5: Social profile via connectapi")
        print("=" * 70)
        try:
            profile = garmin._client.garth.connectapi("/userprofile-service/socialProfile")
            print(json.dumps(profile, indent=2, default=str))
        except Exception as e:
            print(f"Error: {e}")
        print()

    finally:
        garmin.logout()
        print("\n✓ Logged out")


if __name__ == "__main__":
    main()
