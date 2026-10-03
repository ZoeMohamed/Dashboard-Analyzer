"""Bounded Gemini key rotation (docs/SYSTEM.md section 7)."""

from types import SimpleNamespace

import pytest

from app.intelligence.gemini_pool import GeminiClientPool, GeminiPoolExhaustedError


class _Models:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls = 0

    async def generate_content(self, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return {"ok": True}


def _pool(models: list[_Models], **options) -> GeminiClientPool:
    pool = GeminiClientPool(client=SimpleNamespace(aio=SimpleNamespace(models=models[0])), **options)
    pool._clients = [SimpleNamespace(aio=SimpleNamespace(models=item)) for item in models]
    pool._cursor = 0
    return pool


async def test_one_request_tries_at_most_max_attempts_keys() -> None:
    models = [_Models(RuntimeError("429 RESOURCE_EXHAUSTED")) for _ in range(45)]
    pool = _pool(models, max_attempts=2)
    with pytest.raises(GeminiPoolExhaustedError):
        await pool.generate_content(model="m", contents="x")
    assert sum(item.calls for item in models) == 2


async def test_quota_error_cools_key_down_until_cooldown_ends() -> None:
    now = [0.0]
    models = [_Models(RuntimeError("quota exceeded")), _Models()]
    pool = _pool(models, cooldown_seconds=60, clock=lambda: now[0])
    assert await pool.generate_content(model="m", contents="x") == {"ok": True}
    pool._cursor = 0
    await pool.generate_content(model="m", contents="x")
    assert models[0].calls == 1  # skipped while cooling down
    now[0] = 61
    models[0].error = None
    pool._cursor = 0
    await pool.generate_content(model="m", contents="x")
    assert models[0].calls == 2
    assert pool.healthy_count == 2


async def test_invalid_key_is_benched_for_the_process() -> None:
    now = [0.0]
    models = [_Models(RuntimeError("API key not valid")), _Models()]
    pool = _pool(models, cooldown_seconds=1, clock=lambda: now[0])
    await pool.generate_content(model="m", contents="x")
    now[0] = 10_000
    assert pool.healthy_count == 1


class _ServerError(RuntimeError):
    code = 503


async def test_transient_server_error_tries_next_key_once_without_cooldown() -> None:
    models = [_Models(_ServerError("503 UNAVAILABLE")), _Models()]
    pool = _pool(models)
    assert await pool.generate_content(model="m", contents="x") == {"ok": True}
    assert pool.healthy_count == 2  # the key was fine; nothing is cooled down

    models = [_Models(_ServerError("503 UNAVAILABLE")) for _ in range(3)]
    pool = _pool(models)
    with pytest.raises(_ServerError):
        await pool.generate_content(model="m", contents="x")
    assert sum(item.calls for item in models) == 2
