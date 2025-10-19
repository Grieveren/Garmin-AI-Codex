"""API endpoints for AI-powered training recommendations."""
from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Request

from app.services.ai_analyzer import AIAnalyzer


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


def _extract_locale(request: Request, lang_param: str | None) -> str | None:
    """Determine requested locale from query parameter or Accept-Language header."""

    if lang_param:
        return lang_param.strip()

    accept_language = request.headers.get("accept-language")
    if not accept_language:
        return None

    first = accept_language.split(",")[0].strip()
    if not first:
        return None

    return first.split(";")[0].strip()


@router.get("/today")
async def get_today_recommendation(request: Request, lang: str | None = None):
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
        locale = _extract_locale(request, lang)
        logger.info("Handling readiness request for today | locale=%s", locale or "default")
        analyzer = AIAnalyzer()
        recommendation = await analyzer.analyze_daily_readiness(date.today(), locale=locale)
        return recommendation
    except Exception as e:
        logger.exception("Failed to generate today's recommendation")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate recommendation: {str(e)}"
        )


@router.get("/{date_str}")
async def get_recommendation_for_date(request: Request, date_str: str, lang: str | None = None):
    """
    Get AI-powered training recommendation for a specific date.

    Args:
        date_str: Date in YYYY-MM-DD format

    Returns:
        dict: Structured recommendation with all analysis details
    """

    try:
        target_date = date.fromisoformat(date_str)
        locale = _extract_locale(request, lang)
        logger.info(
            "Handling readiness request for %s | locale=%s",
            target_date.isoformat(),
            locale or "default",
        )
        analyzer = AIAnalyzer()
        recommendation = await analyzer.analyze_daily_readiness(target_date, locale=locale)
        return recommendation
    except ValueError:
        logger.warning("Invalid readiness request date: %s", date_str)
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Use YYYY-MM-DD"
        )
    except Exception as e:
        logger.exception("Failed to generate recommendation for %s", date_str)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate recommendation: {str(e)}"
        )
