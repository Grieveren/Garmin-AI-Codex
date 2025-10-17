"""Manual data sync entry point."""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import date

from app.services.garmin_service import GarminService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manual Garmin data sync")
    parser.add_argument(
        "--mfa-code",
        help="Six-digit Garmin MFA code (required if no cached token exists)",
    )
    parser.add_argument(
        "--request-code",
        action="store_true",
        help="Trigger Garmin to send a new MFA code without completing login",
    )
    return parser.parse_args()


async def main(mfa_code: str | None) -> None:
    service = GarminService()

    if not service.has_token_cache and not (mfa_code or os.getenv("GARMIN_MFA_CODE")):
        print(
            "Garmin token cache not found.\n"
            "Provide the latest six-digit code via --mfa-code or GARMIN_MFA_CODE before running this script."
        )
        sys.exit(1)

    code = mfa_code or os.getenv("GARMIN_MFA_CODE")

    try:
        service.login(mfa_code=code)
    except RuntimeError as err:
        print(f"Login failed: {err}")
        sys.exit(1)

    try:
        summary = service.get_daily_summary(date.today())
        print(summary)
    finally:
        service.logout()


if __name__ == "__main__":
    args = parse_args()
    if args.request_code:
        service = GarminService()
        try:
            service.login()
        except RuntimeError as err:
            if "code required" in str(err).lower():
                print("Verification code requested. Check your email/SMS.")
                sys.exit(0)
            print(f"Login failed: {err}")
            sys.exit(1)
        else:
            print("Existing token cache allowed login without MFA.")
        finally:
            try:
                service.logout()
            except Exception:
                pass
        sys.exit(0)
    asyncio.run(main(args.mfa_code))
