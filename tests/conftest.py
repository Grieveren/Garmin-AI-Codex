"""Pytest configuration for global fixtures and logging setup."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, AsyncGenerator, Dict

import pytest
from fastapi.testclient import TestClient

os.environ["SECRET_KEY"] = os.environ.get("SECRET_KEY") or "test-secret-key"
os.environ["GARMIN_EMAIL"] = os.environ.get("GARMIN_EMAIL") or "test@example.com"
os.environ["GARMIN_PASSWORD"] = os.environ.get("GARMIN_PASSWORD") or "hunter2"
os.environ["ANTHROPIC_API_KEY"] = os.environ.get("ANTHROPIC_API_KEY") or "test-anthropic-key"

from app.logging_config import configure_logging

configure_logging()

from app.main import app

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def test_client() -> TestClient:
    """Provide a FastAPI test client."""

    return TestClient(app)


@pytest.fixture(scope="session")
def garmin_fixture() -> Dict[str, Any]:
    """Return Garmin daily metrics fixture data."""

    with (FIXTURES_DIR / "garmin_daily_metrics.json").open("r", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="session")
def anthropic_fixture() -> Dict[str, Any]:
    """Return Anthropic readiness payload fixture data."""

    with (FIXTURES_DIR / "anthropic_response.json").open("r", encoding="utf-8") as fh:
        return json.load(fh)
