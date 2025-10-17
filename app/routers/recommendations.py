"""API endpoints for AI-powered training recommendations."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException

from app.services.ai_analyzer import AIAnalyzer

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.get("/today")
async def get_today_recommendation():
    """
    Get today's AI-powered training recommendation.

    Fetches live data from Garmin and analyzes with Claude AI to provide:
    - Readiness score (0-100)
    - Training recommendation (high_intensity, moderate, easy, rest)
    - Suggested workout with details
    - Key factors and recovery tips

    Returns:
        dict: Structured recommendation with all analysis details
    """

    try:
        analyzer = AIAnalyzer()
        recommendation = await analyzer.analyze_daily_readiness(date.today())
        return recommendation
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate recommendation: {str(e)}"
        )


@router.get("/{date_str}")
async def get_recommendation_for_date(date_str: str):
    """
    Get AI-powered training recommendation for a specific date.

    Args:
        date_str: Date in YYYY-MM-DD format

    Returns:
        dict: Structured recommendation with all analysis details
    """

    try:
        target_date = date.fromisoformat(date_str)
        analyzer = AIAnalyzer()
        recommendation = await analyzer.analyze_daily_readiness(target_date)
        return recommendation
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Use YYYY-MM-DD"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate recommendation: {str(e)}"
        )
