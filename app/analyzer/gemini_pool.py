"""Compatibility alias. The implementation lives in app.intelligence.gemini_pool."""

from app.intelligence.gemini_pool import GeminiClientPool, GeminiPoolExhaustedError, is_auth_error, is_retryable_key_error, is_transient_error

__all__ = ["GeminiClientPool", "GeminiPoolExhaustedError", "is_auth_error", "is_retryable_key_error", "is_transient_error"]
