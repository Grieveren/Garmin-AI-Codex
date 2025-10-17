"""Backfill historical Garmin data."""
import argparse
from datetime import date, timedelta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill Garmin data")
    parser.add_argument("--days", type=int, default=30, help="How many days to backfill")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    start = date.today() - timedelta(days=args.days)
    print(f"Backfilling data from {start} to {date.today()} (not yet implemented)")


if __name__ == "__main__":
    main()
