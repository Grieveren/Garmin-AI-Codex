"""Basic unit tests for GarminService stub."""
import pytest

from app.services.garmin_service import GarminService


def test_garmin_service_initialises():
    service = GarminService()
    assert service is not None
    # Avoid hitting the network in the stub
    assert hasattr(service, "get_daily_summary")
