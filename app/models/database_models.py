"""SQLAlchemy ORM models for historical data tracking."""
from datetime import date, datetime
from sqlalchemy import Integer, Date, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

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
