"""SQLAlchemy ORM models placeholder definitions."""
from datetime import date, datetime
from sqlalchemy import Integer, Date, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DailyMetric(Base):
    """Minimal daily metrics table for future expansion."""

    __tablename__ = "daily_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
