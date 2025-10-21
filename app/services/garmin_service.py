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
            # Fetch user settings which contains personal data
            settings_data = self._client.garth.connectapi(
                "/userprofile-service/userprofile/user-settings"
            )

            age = None
            lactate_threshold_hr = None
            vo2_max = None
            max_hr = None

            if isinstance(settings_data, dict):
                user_data = settings_data.get("userData", {})

                # Extract age from birthDate
                birth_date_str = user_data.get("birthDate")
                if birth_date_str:
                    from datetime import date as date_class
                    birth_date = date_class.fromisoformat(birth_date_str)
                    today = date_class.today()
                    age = today.year - birth_date.year - (
                        (today.month, today.day) < (birth_date.month, birth_date.day)
                    )

                # Extract lactate threshold HR
                lactate_threshold_hr = user_data.get("lactateThresholdHeartRate")
                if isinstance(lactate_threshold_hr, (int, float)):
                    lactate_threshold_hr = int(lactate_threshold_hr)

                # Extract VO2 max (running)
                vo2_max = user_data.get("vo2MaxRunning")
                if isinstance(vo2_max, (int, float)):
                    vo2_max = float(vo2_max)

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

    def get_activity_splits(self, activity_id: int) -> dict[str, Any] | None:
        """
        Fetch lap-by-lap split data for an activity.

        Args:
            activity_id: Garmin activity ID

        Returns:
            dict: Splits data with lap metrics (pace, HR, distance per lap)
            None: If data unavailable or error occurred

        Example response structure:
            {
                "lapDTOs": [
                    {
                        "distance": 1000.0,
                        "duration": 300.0,
                        "averageHR": 145,
                        "maxHR": 152,
                        "averageSpeed": 3.33,
                        ...
                    },
                    ...
                ]
            }
        """
        try:
            logger.info("Fetching activity splits for activity_id=%d", activity_id)
            data = self._client.get_activity_splits(activity_id)

            if data:
                num_laps = len(data.get("lapDTOs", []))
                logger.info("Successfully fetched %d splits for activity %d", num_laps, activity_id)
                return data
            else:
                logger.warning("No splits data returned for activity %d", activity_id)
                return None

        except Exception as err:
            logger.warning(
                "Failed to fetch splits for activity %d: %s",
                activity_id,
                str(err),
                exc_info=True
            )
            return None

    def get_activity_hr_zones(self, activity_id: int) -> dict[str, Any] | None:
        """
        Fetch heart rate zone distribution for an activity.

        Args:
            activity_id: Garmin activity ID

        Returns:
            dict: HR zone data with time spent in each zone
            None: If data unavailable or error occurred

        Example response structure:
            {
                "timeInZones": [
                    {"zone": 1, "duration": 120},  # seconds in Zone 1
                    {"zone": 2, "duration": 600},
                    ...
                ]
            }
        """
        try:
            logger.info("Fetching HR zones for activity_id=%d", activity_id)
            data = self._client.get_activity_hr_in_timezones(activity_id)

            if data:
                logger.info("Successfully fetched HR zone data for activity %d", activity_id)
                return data
            else:
                logger.warning("No HR zone data returned for activity %d", activity_id)
                return None

        except Exception as err:
            logger.warning(
                "Failed to fetch HR zones for activity %d: %s",
                activity_id,
                str(err),
                exc_info=True
            )
            return None

    def get_activity_weather(self, activity_id: int) -> dict[str, Any] | None:
        """
        Fetch weather conditions during an activity.

        Args:
            activity_id: Garmin activity ID

        Returns:
            dict: Weather data (temperature, humidity, wind, etc.)
            None: If data unavailable or error occurred

        Example response structure:
            {
                "temperature": 15.0,  # Celsius
                "apparentTemperature": 13.0,
                "humidity": 65,  # percent
                "windSpeed": 12.0,  # km/h
                "weatherCondition": "cloudy"
            }
        """
        try:
            logger.info("Fetching weather for activity_id=%d", activity_id)
            data = self._client.get_activity_weather(activity_id)

            if data:
                logger.info("Successfully fetched weather data for activity %d", activity_id)
                return data
            else:
                logger.warning("No weather data returned for activity %d", activity_id)
                return None

        except Exception as err:
            logger.warning(
                "Failed to fetch weather for activity %d: %s",
                activity_id,
                str(err),
                exc_info=True
            )
            return None

    def get_detailed_activity_analysis(self, activity_id: int) -> dict[str, Any]:
        """
        Fetch all detailed activity data in a single call.

        Combines splits, HR zones, and weather data with graceful degradation
        if individual API calls fail.

        Args:
            activity_id: Garmin activity ID

        Returns:
            dict: Structured response with all available data
                {
                    "activity_id": int,
                    "splits": dict | None,
                    "hr_zones": dict | None,
                    "weather": dict | None,
                    "is_complete": bool,  # True if all data fetched successfully
                    "errors": list[str]  # List of failed fetches
                }

        Example:
            >>> garmin = GarminService()
            >>> garmin.login()
            >>> details = garmin.get_detailed_activity_analysis(12345678)
            >>> print(details["is_complete"])
            True
            >>> print(len(details["splits"]["lapDTOs"]))
            10
        """
        logger.info("Fetching detailed analysis for activity %d", activity_id)

        errors = []
        splits = None
        hr_zones = None
        weather = None

        # Fetch splits (most important for pacing analysis)
        try:
            splits = self.get_activity_splits(activity_id)
            if splits is None:
                errors.append("splits")
        except Exception as err:
            logger.error("Splits fetch failed: %s", err)
            errors.append("splits")

        # Fetch HR zones (important for intensity analysis)
        try:
            hr_zones = self.get_activity_hr_zones(activity_id)
            if hr_zones is None:
                errors.append("hr_zones")
        except Exception as err:
            logger.error("HR zones fetch failed: %s", err)
            errors.append("hr_zones")

        # Fetch weather (nice to have, not critical)
        try:
            weather = self.get_activity_weather(activity_id)
            if weather is None:
                errors.append("weather")
        except Exception as err:
            logger.error("Weather fetch failed: %s", err)
            errors.append("weather")

        is_complete = len(errors) == 0

        result = {
            "activity_id": activity_id,
            "splits": splits,
            "hr_zones": hr_zones,
            "weather": weather,
            "is_complete": is_complete,
            "errors": errors
        }

        logger.info(
            "Detailed analysis for activity %d complete: %d/%d successful (%s)",
            activity_id,
            3 - len(errors),
            3,
            "complete" if is_complete else f"missing: {', '.join(errors)}"
        )

        return result
