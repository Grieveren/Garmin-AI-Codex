"""SQLAlchemy ORM models for historical data tracking."""
from datetime import date, datetime
from sqlalchemy import Integer, Date, DateTime, Float, String, Boolean, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DailyMetric(Base):
    """Daily physiological metrics from Garmin."""

    __tablename__ = "daily_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, unique=True, nullable=False, index=True)

    # Heart metrics
    resting_hr: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_hr: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hrv_morning: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Morning HRV in ms

    # Sleep metrics
    sleep_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deep_sleep_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    light_sleep_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rem_sleep_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Activity metrics
    steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distance_meters: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_calories: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Stress & Recovery
    stress_avg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    body_battery_charged: Mapped[int | None] = mapped_column(Integer, nullable=True)
    body_battery_drained: Mapped[int | None] = mapped_column(Integer, nullable=True)
    body_battery_max: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Training Readiness & Performance (Garmin's AI metrics)
    training_readiness_score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-100
    vo2_max: Mapped[float | None] = mapped_column(Float, nullable=True)  # ml/kg/min
    training_status: Mapped[str | None] = mapped_column(String(50), nullable=True)  # productive, maintaining, peaking, etc.

    # Advanced Health Metrics
    spo2_avg: Mapped[float | None] = mapped_column(Float, nullable=True)  # Blood oxygen % average
    spo2_min: Mapped[float | None] = mapped_column(Float, nullable=True)  # Blood oxygen % minimum
    respiration_avg: Mapped[float | None] = mapped_column(Float, nullable=True)  # Breaths per minute

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Activity(Base):
    """Training activities from Garmin."""

    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # Use Garmin's activity ID
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Activity details
    activity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    activity_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Duration & Distance
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distance_meters: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Training load metrics
    aerobic_training_effect: Mapped[float | None] = mapped_column(Float, nullable=True)
    anaerobic_training_effect: Mapped[float | None] = mapped_column(Float, nullable=True)
    training_load: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Garmin's training load score

    # Heart rate
    avg_hr: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_hr: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Performance
    avg_pace: Mapped[float | None] = mapped_column(Float, nullable=True)  # seconds per km
    elevation_gain: Mapped[float | None] = mapped_column(Float, nullable=True)  # meters
    calories: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Timestamps
    start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TrainingPlan(Base):
    """Training plan with periodized structure."""

    __tablename__ = "training_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    goal: Mapped[str] = mapped_column(String(100), nullable=False)  # marathon, 5k, 10k, general_fitness
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_ai: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    workouts: Mapped[list["PlannedWorkout"]] = relationship("PlannedWorkout", back_populates="plan", cascade="all, delete-orphan")


class PlannedWorkout(Base):
    """Individual workout within a training plan."""

    __tablename__ = "planned_workouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(Integer, ForeignKey("training_plans.id"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Workout details
    workout_type: Mapped[str] = mapped_column(String(50), nullable=False)  # easy_run, intervals, tempo, long_run, rest
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_distance_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_heart_rate_zone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    intensity_level: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-10 scale

    # Completion tracking
    was_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    actual_activity_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("activities.id"), nullable=True)
    actual_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    completion_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # AI reasoning
    ai_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    plan: Mapped["TrainingPlan"] = relationship("TrainingPlan", back_populates="workouts")
    activity: Mapped["Activity | None"] = relationship("Activity", foreign_keys=[actual_activity_id])
