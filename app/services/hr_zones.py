"""Heart rate zone calculation based on lactate threshold."""

from __future__ import annotations

import logging
from typing import Any


logger = logging.getLogger(__name__)


def calculate_max_hr_from_age(age: int) -> int:
    """
    Calculate estimated maximum heart rate from age.

    Uses the traditional formula: 220 - age.

    Args:
        age: Athlete's age in years

    Returns:
        Estimated maximum heart rate in bpm

    Example:
        >>> calculate_max_hr_from_age(30)
        190
    """
    return 220 - age


def calculate_hr_zones(
    lactate_threshold_hr: int | None,
    max_hr: int | None = None,
    age: int | None = None,
) -> dict[str, dict[str, int | str]]:
    """
    Calculate heart rate zones using lactate threshold-based methodology.

    Prioritizes lactate threshold (LTHR) over age-based formulas when available.
    LTHR-based zones are more accurate as they're individualized to the athlete's
    physiology rather than population averages.

    Zone definitions (LTHR-based):
        - Zone 1 (Recovery): 50-85% of LTHR - Easy aerobic, recovery runs
        - Zone 2 (Aerobic): 85-89% of LTHR - Aerobic base building
        - Zone 3 (Tempo): 90-94% of LTHR - Tempo runs, moderate effort
        - Zone 4 (Threshold): 95-105% of LTHR - Lactate threshold training
        - Zone 5 (VO2 Max): 105% of LTHR to max_hr - High intensity, VO2 max work

    Fallback (age-based, if LTHR unavailable):
        - Zone 1: 50-60% of max HR
        - Zone 2: 60-70% of max HR
        - Zone 3: 70-80% of max HR
        - Zone 4: 80-90% of max HR
        - Zone 5: 90-100% of max HR

    Args:
        lactate_threshold_hr: Lactate threshold heart rate in bpm (from Garmin)
        max_hr: Maximum heart rate in bpm (optional, calculated from age if not provided)
        age: Athlete's age in years (used to estimate max_hr if not provided)

    Returns:
        Dictionary mapping zone names to min/max bpm and description:
        {
            "zone_1": {"min": 80, "max": 136, "name": "Recovery", "description": "Easy aerobic, recovery"},
            "zone_2": {"min": 136, "max": 142, "name": "Aerobic", "description": "Base building"},
            ...
        }

    Raises:
        ValueError: If neither lactate_threshold_hr nor (max_hr or age) provided

    Example:
        >>> # LTHR-based zones (preferred)
        >>> zones = calculate_hr_zones(lactate_threshold_hr=160, max_hr=190)
        >>> print(zones["zone_2"])
        {"min": 136, "max": 142, "name": "Aerobic", "description": "Base building"}

        >>> # Fallback to age-based zones
        >>> zones = calculate_hr_zones(lactate_threshold_hr=None, age=30)
        >>> print(zones["zone_2"])
        {"min": 114, "max": 133, "name": "Aerobic", "description": "Base building"}
    """
    # Validate inputs
    if lactate_threshold_hr is None and max_hr is None and age is None:
        raise ValueError(
            "Must provide either lactate_threshold_hr or (max_hr or age) to calculate HR zones"
        )

    # Calculate max HR if not provided
    if max_hr is None:
        if age is not None:
            # Validate age before calculating max HR
            if not (10 <= age <= 100):
                raise ValueError(f"Age {age} outside valid range (10-100 years)")
            max_hr = calculate_max_hr_from_age(age)
            logger.info("Calculated max HR from age: %d bpm (age=%d)", max_hr, age)
        else:
            # Fallback if we only have LTHR
            max_hr = int(lactate_threshold_hr * 1.15) if lactate_threshold_hr else 200
            logger.warning(
                "No age or max_hr provided - estimating max_hr as 115%% of LTHR: %d bpm",
                max_hr
            )

    # Use LTHR-based zones if available (preferred)
    if lactate_threshold_hr is not None:
        # Issue #2: Validate LTHR is positive
        if lactate_threshold_hr <= 0:
            logger.warning(
                "Invalid LTHR value (%d) - must be positive. Falling back to age-based zones.",
                lactate_threshold_hr
            )
            lactate_threshold_hr = None
        # Issue #1: Validate physiological plausibility
        elif max_hr is not None and lactate_threshold_hr >= max_hr * 0.95:
            logger.warning(
                "LTHR (%d bpm) is too close to or exceeds max HR (%d bpm). "
                "Falling back to age-based zones.",
                lactate_threshold_hr, max_hr
            )
            lactate_threshold_hr = None
        # Validate LTHR is within normal physiological range
        elif lactate_threshold_hr < 80 or lactate_threshold_hr > 200:
            logger.warning(
                "LTHR (%d bpm) outside normal range (80-200 bpm). Verify data accuracy.",
                lactate_threshold_hr
            )
            # Continue with calculation but log warning

        # If LTHR passed validation, use LTHR-based zones
        if lactate_threshold_hr is not None:
            logger.info(
                "Using LTHR-based HR zones (LTHR=%d bpm, max_hr=%d bpm)",
                lactate_threshold_hr,
                max_hr
            )
            return _calculate_lthr_zones(lactate_threshold_hr, max_hr)

    # Fallback to age-based zones
    logger.info("Using age-based HR zones (max_hr=%d bpm)", max_hr)
    return _calculate_age_based_zones(max_hr)


def _calculate_lthr_zones(
    lthr: int,
    max_hr: int,
) -> dict[str, dict[str, int | str]]:
    """
    Calculate HR zones based on lactate threshold.

    This is the preferred method as it's individualized to the athlete.

    Args:
        lthr: Lactate threshold heart rate in bpm
        max_hr: Maximum heart rate in bpm

    Returns:
        Dictionary of zone definitions with min/max bpm
    """
    zones = {
        "zone_1": {
            "min": round(lthr * 0.50),
            "max": round(lthr * 0.85),
            "name": "Recovery",
            "description": "Easy aerobic, recovery runs",
            "effort": "Very easy - can hold conversation",
        },
        "zone_2": {
            "min": round(lthr * 0.85),
            "max": round(lthr * 0.89),
            "name": "Aerobic",
            "description": "Base building, long runs",
            "effort": "Easy - comfortable pace",
        },
        "zone_3": {
            "min": round(lthr * 0.90),
            "max": round(lthr * 0.94),
            "name": "Tempo",
            "description": "Tempo runs, moderate effort",
            "effort": "Moderately hard - can speak in short sentences",
        },
        "zone_4": {
            "min": round(lthr * 0.95),
            "max": round(lthr * 1.05),
            "name": "Threshold",
            "description": "Lactate threshold training",
            "effort": "Hard - challenging but sustainable for 20-60 min",
        },
        "zone_5": {
            "min": round(lthr * 1.05),
            "max": max_hr,
            "name": "VO2 Max",
            "description": "High intensity, VO2 max work",
            "effort": "Very hard - short bursts only",
        },
    }

    return zones


def _calculate_age_based_zones(max_hr: int) -> dict[str, dict[str, int | str]]:
    """
    Calculate HR zones based on maximum heart rate (age-based fallback).

    Less accurate than LTHR-based zones but better than nothing.

    Args:
        max_hr: Maximum heart rate in bpm

    Returns:
        Dictionary of zone definitions with min/max bpm
    """
    zones = {
        "zone_1": {
            "min": round(max_hr * 0.50),
            "max": round(max_hr * 0.60),
            "name": "Recovery",
            "description": "Easy aerobic, recovery runs",
            "effort": "Very easy - can hold conversation",
        },
        "zone_2": {
            "min": round(max_hr * 0.60),
            "max": round(max_hr * 0.70),
            "name": "Aerobic",
            "description": "Base building, long runs",
            "effort": "Easy - comfortable pace",
        },
        "zone_3": {
            "min": round(max_hr * 0.70),
            "max": round(max_hr * 0.80),
            "name": "Tempo",
            "description": "Tempo runs, moderate effort",
            "effort": "Moderately hard - can speak in short sentences",
        },
        "zone_4": {
            "min": round(max_hr * 0.80),
            "max": round(max_hr * 0.90),
            "name": "Threshold",
            "description": "Lactate threshold training",
            "effort": "Hard - challenging but sustainable for 20-60 min",
        },
        "zone_5": {
            "min": round(max_hr * 0.90),
            "max": max_hr,
            "name": "VO2 Max",
            "description": "High intensity, VO2 max work",
            "effort": "Very hard - short bursts only",
        },
    }

    return zones


def format_hr_zones_for_prompt(zones: dict[str, dict[str, Any]]) -> str:
    """
    Format HR zones into human-readable string for AI prompt.

    Args:
        zones: Dictionary of zone definitions from calculate_hr_zones()

    Returns:
        Multi-line formatted string:
            Zone 1 (Recovery): 80-136 bpm - Easy aerobic, recovery runs
            Zone 2 (Aerobic): 136-142 bpm - Base building, long runs
            ...

    Example:
        >>> zones = calculate_hr_zones(lactate_threshold_hr=160, max_hr=190)
        >>> print(format_hr_zones_for_prompt(zones))
        Zone 1 (Recovery): 80-136 bpm - Easy aerobic, recovery runs
        Zone 2 (Aerobic): 136-142 bpm - Base building, long runs
        ...
    """
    lines = []
    for zone_num in range(1, 6):
        zone_key = f"zone_{zone_num}"
        if zone_key not in zones:
            continue

        zone = zones[zone_key]
        min_hr = zone["min"]
        max_hr = zone["max"]
        name = zone["name"]
        description = zone["description"]

        lines.append(
            f"Zone {zone_num} ({name}): {min_hr}-{max_hr} bpm - {description}"
        )

    return "\n".join(lines)
