"""Service for interacting with the Garmin Connect API."""
import logging
from datetime import date
from pathlib import Path
from typing import Any

import app.compat  # noqa: F401  # Ensure compatibility patches load early.
from garminconnect import Garmin
from garth.exc import GarthHTTPError
from garth.users import UserProfile, UserSettings

from app.config import get_settings


logger = logging.getLogger(__name__)


class GarminService:
    """Thin wrapper around the garminconnect client with authentication helpers."""

    def __init__(self) -> None:
        settings = get_settings()
        self._pending_mfa_code: str | None = None
        self._token_store = (
            Path(settings.garmin_token_store)
            if settings.garmin_token_store
            else None
        )
        self._client = Garmin(
            settings.garmin_email,
            settings.garmin_password,
            prompt_mfa=self._prompt_mfa,
        )

    def login(self, mfa_code: str | None = None) -> None:
        """Authenticate with Garmin Connect."""

        self._pending_mfa_code = mfa_code
        try:
            logger.info("Attempting Garmin login (token cache: %s)", bool(self._token_store))
            if self._token_store and self._token_store.exists():
                self._client.login(tokenstore=str(self._token_store))
            else:
                self._client.login()
                self._persist_tokens()
            logger.info("Garmin login successful")
        except GarthHTTPError as err:
            logger.exception("Garmin login failed with HTTP error")
            raise RuntimeError(
                f"Garmin login failed with HTTP {getattr(err, 'response', None).status_code if getattr(err, 'response', None) else 'error'} – {err}"
            ) from err
        except AssertionError as err:
            # Distinguish between invalid MFA (no tokens) and profile fetch issue.
            oauth1 = getattr(self._client.garth, "oauth1_token", None)
            if oauth1 is None:
                logger.exception("Garmin login failed (likely invalid MFA code)")
                raise RuntimeError(
                    "Garmin login failed (check MFA code)."
                ) from err

            # Tokens exist, try to fetch profile data but don't fail if it's unavailable
            try:
                profile_raw = self._client.garth.connectapi(
                    "/userprofile-service/socialProfile"
                )
                settings_raw = self._client.garth.connectapi(
                    "/userprofile-service/userprofile/user-settings"
                )
                if isinstance(profile_raw, dict):
                    self._client.display_name = profile_raw.get("displayName", "")
                    self._client.full_name = profile_raw.get("fullName", "")
                if isinstance(settings_raw, dict):
                    user_data = settings_raw.get("userData", {})
                    self._client.unit_system = user_data.get("measurementSystem", "metric")
            except Exception:
                # Profile fetch failed, but we have tokens - proceed anyway
                logger.warning("Garmin profile fetch failed; continuing with cached tokens", exc_info=True)
                self._client.display_name = "User"
                self._client.full_name = "Garmin User"
                self._client.unit_system = "metric"

            # Save tokens regardless of profile data availability
            self._persist_tokens()

    def _persist_tokens(self) -> None:
        if self._token_store:
            self._token_store.parent.mkdir(parents=True, exist_ok=True)
            self._client.garth.dump(str(self._token_store))

    @property
    def has_token_cache(self) -> bool:
        return bool(self._token_store and self._token_store.exists())

    def logout(self) -> None:
        """Terminate the Garmin session."""

        self._client.logout()

    @staticmethod
    def _mfa_error() -> None:
        raise RuntimeError(
            "Garmin MFA code required. Provide it via GARMIN_MFA_CODE env var or login() argument."
        )

    def _prompt_mfa(self) -> str:
        """Prompt user for Garmin MFA code when required."""

        if self._pending_mfa_code:
            code = self._pending_mfa_code
            self._pending_mfa_code = None
            return code
        self._mfa_error()

    def get_personal_info(self) -> dict[str, Any]:
        """
        Fetch personal information including age, lactate threshold, and VO2 max.

        Returns:
            Dictionary with:
                - age: int | None - Athlete's age in years
                - lactate_threshold_hr: int | None - LTHR in bpm
                - vo2_max: float | None - VO2 max estimate
                - max_hr: int | None - Calculated from age if available

        Example:
            >>> garmin = GarminService()
            >>> garmin.login()
            >>> info = garmin.get_personal_info()
            >>> print(info)
            {"age": 30, "lactate_threshold_hr": 160, "vo2_max": 52.0, "max_hr": 190}
        """
        try:
            # Fetch personal information from Garmin API
            personal_data = self._client.garth.connectapi(
                "/userprofile-service/userprofile/personal-information"
            )

            age = None
            lactate_threshold_hr = None
            vo2_max = None
            max_hr = None

            if isinstance(personal_data, dict):
                # Extract age
                age = personal_data.get("age")

                # Extract lactate threshold HR
                # API may return as lactateThresholdHeartRate or lactateThreshold
                lactate_threshold_hr = personal_data.get("lactateThresholdHeartRate")
                if lactate_threshold_hr is None:
                    lactate_threshold_hr = personal_data.get("lactateThreshold")

                # Convert to int if numeric
                if isinstance(lactate_threshold_hr, (int, float)):
                    lactate_threshold_hr = int(lactate_threshold_hr)

                # Extract VO2 max (may be in various formats)
                vo2_max = personal_data.get("vo2Max")
                if vo2_max is None:
                    vo2_max = personal_data.get("vo2MaxValue")

                # Calculate max HR from age if available
                if age is not None and isinstance(age, int):
                    max_hr = 220 - age

            logger.info(
                "Fetched personal info: age=%s, LTHR=%s, VO2max=%s, max_hr=%s",
                age,
                lactate_threshold_hr,
                vo2_max,
                max_hr
            )

            return {
                "age": age,
                "lactate_threshold_hr": lactate_threshold_hr,
                "vo2_max": vo2_max,
                "max_hr": max_hr,
            }

        except Exception as err:
            logger.exception("Failed to fetch personal information from Garmin")
            return {
                "age": None,
                "lactate_threshold_hr": None,
                "vo2_max": None,
                "max_hr": None,
                "error": str(err),
            }

    def get_daily_summary(self, target_date: date) -> dict[str, Any]:
        """Fetch the user summary for a single date."""

        try:
            return self._client.get_user_summary(target_date.isoformat())
        except (TypeError, KeyError) as err:
            # Workaround: get_user_summary has a bug, try alternative methods
            try:
                # Try getting stats directly
                stats = self._client.get_stats(target_date.isoformat())
                return {"stats": stats, "note": "Retrieved via get_stats() due to library bug"}
            except Exception:
                # Last resort: return available methods
                return {
                    "error": f"get_user_summary failed: {err}",
                    "note": "Tokens are cached - future calls should work",
                    "available_methods": [
                        "get_stats(date)",
                        "get_heart_rates(date)",
                        "get_sleep_data(date)",
                        "get_activities(start, limit)"
                    ]
                }
