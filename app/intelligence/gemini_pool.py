"""Small server-side Gemini client pool with quota-aware key rotation."""

from __future__ import annotations

import secrets
import time
from collections.abc import Callable
from typing import Any, Iterable


class GeminiPoolExhaustedError(RuntimeError):
    """All configured credentials were unavailable for the current request."""


def is_auth_error(exc: Exception) -> bool:
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    message = str(exc).casefold()
    return code in {401, 403} or any(
        signal in message for signal in ("api key not valid", "api_key_invalid", "permission denied")
    )


def is_transient_error(exc: Exception) -> bool:
    """Server-side or network trouble that is not caused by the key itself."""
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    message = str(exc).casefold()
    return code in {500, 502, 503, 504} or any(
        signal in message for signal in ("unavailable", "deadline exceeded", "timed out", "internal error")
    )


def is_retryable_key_error(exc: Exception) -> bool:
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    message = str(exc).casefold()
    return code in {401, 403, 429} or any(
        signal in message
        for signal in (
            "resource exhausted",
            "resource_exhausted",
            "quota",
            "rate limit",
            "api key not valid",
            "api_key_invalid",
            "permission denied",
        )
    )


class GeminiClientPool:
    def __init__(
        self, keys: Iterable[str] = (), *, client: Any | None = None,
        max_attempts: int | None = None, cooldown_seconds: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if client is not None:
            self._clients = [client]
        else:
            unique = list(dict.fromkeys(key.strip() for key in keys if key.strip()))
            if not unique:
                raise ValueError("GEMINI_API_KEY atau GEMINI_API_KEYS wajib diisi")
            try:
                from google import genai
            except ImportError as exc:  # pragma: no cover - deployment dependency guard
                raise RuntimeError("Paket google-genai belum terpasang") from exc
            self._clients = [genai.Client(api_key=key) for key in unique]
        self._cursor = secrets.randbelow(len(self._clients))
        # Bounded rotation (docs/SYSTEM.md section 7): a quota/rate-limit error
        # cools the key down, an auth error benches it for this process, and one
        # request never walks the whole pool.
        self.max_attempts = max_attempts
        self.cooldown_seconds = cooldown_seconds
        self._clock = clock
        self._unavailable_until: dict[int, float] = {}

    @property
    def size(self) -> int:
        return len(self._clients)

    @property
    def healthy_count(self) -> int:
        now = self._clock()
        return sum(1 for index in range(len(self._clients)) if self._unavailable_until.get(index, 0.0) <= now)

    async def generate_content(self, **kwargs: Any) -> Any:
        last_error: Exception | None = None
        now = self._clock()
        healthy = [
            (self._cursor + offset) % len(self._clients)
            for offset in range(len(self._clients))
            if self._unavailable_until.get((self._cursor + offset) % len(self._clients), 0.0) <= now
        ]
        transient_retried = False
        for index in healthy[: self.max_attempts or len(healthy)]:
            try:
                response = await self._clients[index].aio.models.generate_content(**kwargs)
            except Exception as exc:
                if is_transient_error(exc) and not transient_retried:
                    # Timeouts and 5xx may try the next key once (SYSTEM.md
                    # section 7); the key itself is fine, so no cooldown.
                    transient_retried = True
                    last_error = exc
                    continue
                if not is_retryable_key_error(exc):
                    raise
                pause = float("inf") if is_auth_error(exc) else self.cooldown_seconds
                self._unavailable_until[index] = self._clock() + pause
                last_error = exc
                continue
            self._cursor = (index + 1) % len(self._clients)
            return response
        raise GeminiPoolExhaustedError(
            "Semua key Gemini sedang kehabisan kuota atau tidak tersedia"
        ) from last_error
