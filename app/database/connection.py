"""Optional async PostgreSQL connection pool.

The application deliberately has an in-memory repository fallback for local
development and contract tests. Production must provide DATABASE_URL.
"""

from __future__ import annotations

from typing import Any

from app.config import Settings


async def create_pool(settings: Settings) -> Any | None:
    if not settings.database_url:
        return None
    try:
        import asyncpg
    except ImportError as exc:  # pragma: no cover - only reached in bad deploys
        raise RuntimeError("asyncpg wajib terpasang saat DATABASE_URL digunakan") from exc

    return await asyncpg.create_pool(
        dsn=settings.database_url.get_secret_value(),
        min_size=settings.database_pool_min_size,
        max_size=settings.database_pool_max_size,
        command_timeout=settings.database_command_timeout_seconds,
        max_inactive_connection_lifetime=300,
    )


async def close_pool(pool: Any | None) -> None:
    if pool is not None:
        await pool.close()
