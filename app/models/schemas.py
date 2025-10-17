"""Pydantic models describing API payloads."""
from datetime import date
from pydantic import BaseModel, Field


class ReadinessResponse(BaseModel):
    """Schema for the daily readiness API response."""

    date: date
    readiness_score: int = Field(ge=0, le=100)
    recommendation: str
    key_factors: list[str] = []
