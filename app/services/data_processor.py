"""Data aggregation and preprocessing helpers."""
from typing import Any, Dict, Iterable


class DataProcessor:
    """Prepare Garmin and user data for AI prompts."""

    def normalise_daily_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Return metrics untouched for now until transformation rules are defined."""

        return metrics

    def aggregate_activities(self, activities: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        """Placeholder aggregation implementation."""

        return {"activities": list(activities)}
