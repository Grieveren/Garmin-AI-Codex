"""Integration tests for training plan API endpoints."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient


def test_get_current_plan_no_active_plan(test_client: TestClient):
    """Test getting current plan when no active plan exists."""
    response = test_client.get("/api/training/plans/current")

    # Should return 404 when no active plan
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


def test_generate_training_plan(test_client: TestClient):
    """Test generating a new training plan."""
    start_date = date.today()
    target_date = start_date + timedelta(days=90)

    plan_data = {
        "name": "Test 10K Plan",
        "goal": "10k",
        "start_date": start_date.isoformat(),
        "target_date": target_date.isoformat(),
        "current_fitness_level": 60,
        "weekly_volume": 35,  # Required field
        "notes": "Test plan for integration testing"
    }

    response = test_client.post("/api/training/plans/generate", json=plan_data)

    assert response.status_code == 201
    data = response.json()

    # Validate response structure
    assert data["name"] == "Test 10K Plan"
    assert data["goal"] == "10k"
    assert data["is_active"] is True
    assert data["created_by_ai"] is True
    assert "workouts" in data
    assert isinstance(data["workouts"], list)


def test_generate_plan_invalid_goal(test_client: TestClient):
    """Test plan generation with invalid goal."""
    start_date = date.today()
    target_date = start_date + timedelta(days=90)

    plan_data = {
        "name": "Invalid Plan",
        "goal": "invalid_goal",
        "start_date": start_date.isoformat(),
        "target_date": target_date.isoformat(),
        "weekly_volume": 30,
    }

    response = test_client.post("/api/training/plans/generate", json=plan_data)

    # Should return validation error
    assert response.status_code == 422  # Pydantic validation error


def test_generate_plan_invalid_dates(test_client: TestClient):
    """Test plan generation with invalid date range."""
    start_date = date.today()
    target_date = start_date - timedelta(days=30)  # Target before start

    plan_data = {
        "name": "Invalid Date Plan",
        "goal": "5k",
        "start_date": start_date.isoformat(),
        "target_date": target_date.isoformat(),
        "weekly_volume": 30,
    }

    response = test_client.post("/api/training/plans/generate", json=plan_data)

    # Should return error for invalid dates
    assert response.status_code == 400


def test_get_current_plan_after_generation(test_client: TestClient):
    """Test retrieving current plan after generating one."""
    # First, generate a plan
    start_date = date.today()
    target_date = start_date + timedelta(days=60)

    plan_data = {
        "name": "Current Plan Test",
        "goal": "5k",
        "start_date": start_date.isoformat(),
        "target_date": target_date.isoformat(),
        "weekly_volume": 25,
    }

    create_response = test_client.post("/api/training/plans/generate", json=plan_data)
    assert create_response.status_code == 201

    # Now retrieve current plan
    response = test_client.get("/api/training/plans/current")

    assert response.status_code == 200
    data = response.json()

    assert data["name"] == "Current Plan Test"
    assert data["goal"] == "5k"
    assert data["is_active"] is True
    assert "workouts" in data

    # Should have workouts for next 14 days
    workouts = data["workouts"]
    assert isinstance(workouts, list)


def test_get_plan_by_id(test_client: TestClient):
    """Test retrieving a specific plan by ID."""
    # Generate a plan first
    start_date = date.today()
    target_date = start_date + timedelta(days=45)

    plan_data = {
        "name": "Plan by ID Test",
        "goal": "general_fitness",
        "start_date": start_date.isoformat(),
        "target_date": target_date.isoformat(),
        "weekly_volume": 20,
    }

    create_response = test_client.post("/api/training/plans/generate", json=plan_data)
    assert create_response.status_code == 201
    created_plan = create_response.json()
    plan_id = created_plan["id"]

    # Retrieve by ID
    response = test_client.get(f"/api/training/plans/{plan_id}")

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == plan_id
    assert data["name"] == "Plan by ID Test"
    assert "workouts" in data


def test_get_nonexistent_plan(test_client: TestClient):
    """Test retrieving a plan that doesn't exist."""
    response = test_client.get("/api/training/plans/99999")

    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


def test_complete_workout(test_client: TestClient):
    """Test marking a workout as complete."""
    # Generate a plan first
    start_date = date.today()
    target_date = start_date + timedelta(days=30)

    plan_data = {
        "name": "Workout Completion Test",
        "goal": "10k",
        "start_date": start_date.isoformat(),
        "target_date": target_date.isoformat(),
        "weekly_volume": 30,
    }

    create_response = test_client.post("/api/training/plans/generate", json=plan_data)
    assert create_response.status_code == 201
    plan = create_response.json()

    # Get first workout
    workouts = plan["workouts"]
    assert len(workouts) > 0
    workout_id = workouts[0]["id"]

    # Mark as complete
    completion_data = {
        "completed": True,
        "actual_duration_min": 45,
        "actual_distance_km": 8.2,
        "notes": "Felt strong, good pace"
    }

    response = test_client.put(
        f"/api/training/workouts/{workout_id}/complete",
        json=completion_data
    )

    assert response.status_code == 200
    data = response.json()

    assert data["was_completed"] is True
    assert data["actual_duration_minutes"] == 45
    assert data["actual_distance_km"] == 8.2
    assert data["completion_notes"] == "Felt strong, good pace"
    assert data["completed_at"] is not None


def test_uncomplete_workout(test_client: TestClient):
    """Test unmarking a completed workout."""
    # Generate plan and complete a workout
    start_date = date.today()
    target_date = start_date + timedelta(days=30)

    plan_data = {
        "name": "Uncomplete Test",
        "goal": "5k",
        "start_date": start_date.isoformat(),
        "target_date": target_date.isoformat(),
        "weekly_volume": 25,
    }

    create_response = test_client.post("/api/training/plans/generate", json=plan_data)
    plan = create_response.json()
    workout_id = plan["workouts"][0]["id"]

    # First complete it
    test_client.put(
        f"/api/training/workouts/{workout_id}/complete",
        json={"completed": True}
    )

    # Then uncomplete it
    response = test_client.put(
        f"/api/training/workouts/{workout_id}/complete",
        json={"completed": False}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["was_completed"] is False


def test_complete_nonexistent_workout(test_client: TestClient):
    """Test completing a workout that doesn't exist."""
    response = test_client.put(
        "/api/training/workouts/99999/complete",
        json={"completed": True}
    )

    assert response.status_code == 404


def test_deactivate_plan(test_client: TestClient):
    """Test deactivating a training plan."""
    # Generate a plan
    start_date = date.today()
    target_date = start_date + timedelta(days=30)

    plan_data = {
        "name": "Plan to Deactivate",
        "goal": "general_fitness",
        "start_date": start_date.isoformat(),
        "target_date": target_date.isoformat(),
        "weekly_volume": 20,
    }

    create_response = test_client.post("/api/training/plans/generate", json=plan_data)
    plan = create_response.json()
    plan_id = plan["id"]

    # Deactivate it
    response = test_client.delete(f"/api/training/plans/{plan_id}")

    assert response.status_code == 200
    data = response.json()
    assert "deactivated successfully" in data["message"].lower()

    # Verify it's no longer the current plan
    current_response = test_client.get("/api/training/plans/current")
    assert current_response.status_code == 404


def test_deactivate_nonexistent_plan(test_client: TestClient):
    """Test deactivating a plan that doesn't exist."""
    response = test_client.delete("/api/training/plans/99999")

    assert response.status_code == 404


def test_multiple_plan_generation_deactivates_previous(test_client: TestClient):
    """Test that generating a new plan deactivates the previous active plan."""
    start_date = date.today()
    target_date = start_date + timedelta(days=30)

    # Create first plan
    plan1_data = {
        "name": "First Plan",
        "goal": "5k",
        "start_date": start_date.isoformat(),
        "target_date": target_date.isoformat(),
        "weekly_volume": 25,
    }

    response1 = test_client.post("/api/training/plans/generate", json=plan1_data)
    assert response1.status_code == 201
    plan1 = response1.json()

    # Create second plan
    plan2_data = {
        "name": "Second Plan",
        "goal": "10k",
        "start_date": start_date.isoformat(),
        "target_date": (target_date + timedelta(days=30)).isoformat(),
        "weekly_volume": 35,
    }

    response2 = test_client.post("/api/training/plans/generate", json=plan2_data)
    assert response2.status_code == 201
    plan2 = response2.json()

    # Current plan should be the second one
    current_response = test_client.get("/api/training/plans/current")
    assert current_response.status_code == 200
    current_plan = current_response.json()
    assert current_plan["id"] == plan2["id"]

    # First plan should be deactivated
    plan1_response = test_client.get(f"/api/training/plans/{plan1['id']}")
    assert plan1_response.status_code == 200
    retrieved_plan1 = plan1_response.json()
    assert retrieved_plan1["is_active"] is False
