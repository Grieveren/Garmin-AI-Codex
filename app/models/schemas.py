"""Pydantic models describing API payloads."""
from datetime import date, datetime
from pydantic import BaseModel, Field


class ReadinessResponse(BaseModel):
    """Schema for the daily readiness API response."""

    date: date
    readiness_score: int = Field(ge=0, le=100)
    recommendation: str
    key_factors: list[str] = []


# Training Plan Schemas
class TrainingPlanBase(BaseModel):
    """Base schema for training plans."""

    name: str
    goal: str
    start_date: date
    target_date: date
    notes: str | None = None


class TrainingPlanCreate(TrainingPlanBase):
    """Schema for creating a new training plan."""

    current_fitness_level: int = Field(ge=0, le=100, default=50)
    weekly_volume: int = Field(ge=0, description="Target weekly volume in km")


class TrainingPlanResponse(TrainingPlanBase):
    """Schema for training plan API response."""

    id: int
    is_active: bool
    created_by_ai: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PlannedWorkoutBase(BaseModel):
    """Base schema for planned workouts."""

    date: date
    workout_type: str
    description: str | None = None
    target_duration_minutes: int | None = None
    target_distance_meters: float | None = None
    target_heart_rate_zone: str | None = None
    intensity_level: int | None = Field(None, ge=1, le=10)


class PlannedWorkoutResponse(PlannedWorkoutBase):
    """Schema for planned workout API response."""

    id: int
    plan_id: int
    was_completed: bool
    actual_duration_minutes: int | None = None
    actual_distance_km: float | None = None
    completion_notes: str | None = None
    completed_at: datetime | None = None
    ai_reasoning: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkoutCompletionUpdate(BaseModel):
    """Schema for marking a workout as complete."""

    completed: bool
    actual_duration_min: int | None = None
    actual_distance_km: float | None = None
    notes: str | None = None
    completed_at: datetime | None = None


class TrainingPlanWithWorkouts(TrainingPlanResponse):
    """Schema for training plan with associated workouts."""

    workouts: list[PlannedWorkoutResponse] = []
