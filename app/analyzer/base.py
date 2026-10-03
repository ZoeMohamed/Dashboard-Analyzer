"""Compatibility alias. The implementation lives in app.intelligence.base."""

from app.intelligence.base import AnalyzerError, BaseAnalyzer, RateLimitedError, SentimentResult

__all__ = ["AnalyzerError", "BaseAnalyzer", "RateLimitedError", "SentimentResult"]
