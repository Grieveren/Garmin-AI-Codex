"""Unit tests for TrainingPlanner stub."""
from datetime import date

from app.services.training_planner import TrainingPlanner


def test_generate_plan_returns_structure():
    planner = TrainingPlanner()
    plan = planner.generate_plan("5k", date.today())
    assert plan["goal"] == "5k"
    assert "weeks" in plan
