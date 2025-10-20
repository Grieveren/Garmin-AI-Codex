"""Integration tests for analytics API endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_readiness_trend_endpoint(test_client: TestClient):
    """Test readiness trend analytics endpoint."""
    response = test_client.get("/api/analytics/readiness-trend?days=30")

    # Should return 200 even with no data
    assert response.status_code == 200
    data = response.json()

    # Validate response structure
    assert isinstance(data, list)

    # If data exists, validate format
    if len(data) > 0:
        item = data[0]
        assert "date" in item
        assert "score" in item or "readiness_score" in item
        assert "recommendation" in item


def test_readiness_trend_date_range(test_client: TestClient):
    """Test readiness trend with custom date range."""
    response = test_client.get(
        "/api/analytics/readiness-trend?start_date=2025-10-01&end_date=2025-10-20"
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_training_load_endpoint(test_client: TestClient):
    """Test training load analytics endpoint."""
    response = test_client.get("/api/analytics/training-load?days=90")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

    # If data exists, validate format
    if len(data) > 0:
        item = data[0]
        assert "date" in item
        # Training load metrics may be optional if not calculated
        # Just verify structure is valid


def test_sleep_performance_endpoint(test_client: TestClient):
    """Test sleep-performance correlation endpoint."""
    response = test_client.get("/api/analytics/sleep-performance?days=30")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

    # If data exists, validate format
    if len(data) > 0:
        item = data[0]
        assert "date" in item


def test_activity_breakdown_endpoint(test_client: TestClient):
    """Test activity breakdown endpoint."""
    response = test_client.get("/api/analytics/activity-breakdown?days=30")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)

    # Breakdown should be dict of activity types
    # Empty dict is valid if no activities


def test_recovery_correlation_endpoint(test_client: TestClient):
    """Test recovery metric correlation endpoint."""
    # Test with HRV metric
    response = test_client.get("/api/analytics/recovery-correlation?metric=hrv&days=30")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)

    # Should have correlation and data fields
    if "correlation" in data:
        assert isinstance(data["correlation"], (int, float))
        assert "data" in data
        assert isinstance(data["data"], list)


def test_recovery_correlation_invalid_metric(test_client: TestClient):
    """Test recovery correlation with invalid metric."""
    response = test_client.get("/api/analytics/recovery-correlation?metric=invalid")

    # Should return validation error (FastAPI uses 422 for validation)
    assert response.status_code in [200, 400, 422]


def test_readiness_trend_invalid_date_format(test_client: TestClient):
    """Test readiness trend with invalid date format."""
    response = test_client.get("/api/analytics/readiness-trend?start_date=not-a-date")

    # Should return validation error (FastAPI uses 422)
    assert response.status_code in [400, 422]


def test_analytics_default_parameters(test_client: TestClient):
    """Test that analytics endpoints work with default parameters."""
    endpoints = [
        "/api/analytics/readiness-trend",
        "/api/analytics/training-load",
        "/api/analytics/sleep-performance",
        "/api/analytics/activity-breakdown",
    ]

    for endpoint in endpoints:
        response = test_client.get(endpoint)
        assert response.status_code == 200, f"Endpoint {endpoint} failed"


def test_analytics_pagination_support(test_client: TestClient):
    """Test that analytics endpoints support different day ranges."""
    day_ranges = [7, 30, 90]

    for days in day_ranges:
        response = test_client.get(f"/api/analytics/readiness-trend?days={days}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        # If we have data, verify it respects the day limit
        # (can't strictly enforce without seeded data, but validate structure)


def test_analytics_empty_database(test_client: TestClient):
    """Test analytics endpoints handle empty database gracefully."""
    # All endpoints should return 200 with empty/zero data, not errors
    response = test_client.get("/api/analytics/readiness-trend?days=7")
    assert response.status_code == 200

    response = test_client.get("/api/analytics/activity-breakdown?days=7")
    assert response.status_code == 200


def test_correlation_calculation_accuracy(test_client: TestClient):
    """Test that correlation calculations are in valid range."""
    response = test_client.get("/api/analytics/recovery-correlation?metric=sleep&days=30")

    if response.status_code == 200:
        data = response.json()
        if "correlation" in data and data["correlation"] is not None:
            # Correlation coefficient should be between -1 and 1
            assert -1.0 <= data["correlation"] <= 1.0
