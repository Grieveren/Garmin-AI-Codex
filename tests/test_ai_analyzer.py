"""Unit tests for AIAnalyzer stub."""
from datetime import date

from app.services.ai_analyzer import AIAnalyzer


def test_analyze_daily_readiness_returns_placeholder():
    analyzer = AIAnalyzer()
    result = analyzer.analyze_daily_readiness(date.today())
    assert result["recommendation"] == "easy"
    assert 0 <= result["readiness_score"] <= 100
