"""Compatibility alias. The implementation lives in app.intelligence.gemini."""

from app.intelligence.gemini import BatchItem, GeminiAnalyzer, SYSTEM_PROMPT, parse_response

__all__ = ["BatchItem", "GeminiAnalyzer", "SYSTEM_PROMPT", "parse_response"]
