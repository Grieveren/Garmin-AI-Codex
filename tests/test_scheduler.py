"""Tests for the asynchronous scheduler job."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict

import pytest

from scripts import run_scheduler


@pytest.mark.asyncio
async def test_run_daily_job_invokes_sync_and_analysis(monkeypatch):
    recorded: Dict[str, Any] = {}

    def fake_sync() -> Dict[str, Dict[str, Any]]:
        recorded["sync_called"] = True
        return {date.today().isoformat(): {"metrics": "saved", "activities_saved": 1, "activities_skipped": 0}}

    async def fake_analyze(self, target_date: date) -> Dict[str, Any]:
        recorded["analyze_target"] = target_date
        return {"readiness_score": 75, "recommendation": "moderate", "confidence": "medium"}

    monkeypatch.setattr(run_scheduler, "perform_daily_sync", fake_sync)
    monkeypatch.setattr(run_scheduler.AIAnalyzer, "analyze_daily_readiness", fake_analyze)

    await run_scheduler.run_daily_job()

    assert recorded["sync_called"] is True
    assert recorded["analyze_target"] == date.today()


@pytest.mark.asyncio
async def test_run_daily_job_stops_when_sync_fails(monkeypatch):
    called = {"analyze": False}

    def fake_sync_failure() -> Dict[str, Dict[str, Any]]:
        raise RuntimeError("boom")

    async def fake_analyze(self, target_date: date) -> Dict[str, Any]:
        called["analyze"] = True
        return {}

    monkeypatch.setattr(run_scheduler, "perform_daily_sync", fake_sync_failure)
    monkeypatch.setattr(run_scheduler.AIAnalyzer, "analyze_daily_readiness", fake_analyze)

    await run_scheduler.run_daily_job()

    assert called["analyze"] is False
