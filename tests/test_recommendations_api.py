"""Integration tests for the recommendation API endpoints."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import json
import pytest

from app.services.ai_analyzer import AIAnalyzer


@pytest.mark.asyncio
async def test_today_endpoint_returns_expected_payload(
    monkeypatch: pytest.MonkeyPatch,
    test_client,
    garmin_fixture,
    anthropic_fixture,
):
    """Ensure /api/recommendations/today returns data built from stubbed services."""

    class DummyGarminService:
        def login(self, *args, **kwargs) -> None:
            return None

        def logout(self) -> None:
            return None

    monkeypatch.setattr("app.services.ai_analyzer.GarminService", DummyGarminService)

    def fake_fetch(self: AIAnalyzer, garmin: DummyGarminService, target_date: date) -> dict[str, Any]:
        return garmin_fixture

    monkeypatch.setattr(AIAnalyzer, "_fetch_garmin_data", fake_fetch)
    monkeypatch.setattr(AIAnalyzer, "_get_historical_baselines", lambda self, target_date: None)
    monkeypatch.setattr(AIAnalyzer, "_get_readiness_history", lambda self, target_date: [])
    monkeypatch.setattr(
        AIAnalyzer,
        "_get_latest_metric_sync",
        lambda self: "2025-10-18T06:00:00Z",
    )

    class DummyMessages:
        def create(self, **kwargs):
            return SimpleNamespace(
                content=[SimpleNamespace(text=json.dumps(anthropic_fixture))]
            )

    class DummyAnthropic:
        def __init__(self, api_key: str):  # noqa: D401
            self.messages = DummyMessages()

    monkeypatch.setattr("app.services.ai_analyzer.Anthropic", DummyAnthropic)

    response = test_client.get("/api/recommendations/today")
    assert response.status_code == 200
    payload = response.json()

    assert payload["readiness_score"] == anthropic_fixture["readiness_score"]
    assert payload["recommendation"] == anthropic_fixture["recommendation"]
    assert payload["enhanced_metrics"]["training_readiness_score"] == garmin_fixture["training_readiness"][0]["score"]
    assert payload["latest_data_sync"] == "2025-10-18T06:00:00Z"
    assert payload["language"] == "en"
    assert "extended_signals" in payload


@pytest.mark.asyncio
async def test_date_endpoint_validates_isoformat(monkeypatch: pytest.MonkeyPatch, test_client):
    async def fake_analyze(self, target_date, locale=None):
        return {"readiness_score": 10}

    monkeypatch.setattr(
        AIAnalyzer,
        "analyze_daily_readiness",
        fake_analyze,
    )

    bad = test_client.get("/api/recommendations/not-a-date")
    assert bad.status_code == 400

    good = test_client.get("/api/recommendations/2025-10-18")
    assert good.status_code == 200
