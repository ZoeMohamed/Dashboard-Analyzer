from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Request

from app.contracts import SourceName

router = APIRouter(tags=["health"])


async def _database_ready(pool: object | None) -> bool:
    if pool is None:
        return True
    try:
        await asyncio.wait_for(pool.fetchval("select 1"), timeout=2)
    except Exception:
        return False
    return True


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    """Process liveness plus dependency readiness, without secret values.

    Always HTTP 200 while the process runs, so a slow provider or database
    never makes the platform restart the service; ``ready`` reports dependencies.
    """
    state = request.app.state
    settings = state.settings
    database_ready = await _database_ready(state.pool)
    active = set(settings.active_sources)
    providers = state.pipeline.providers
    return {
        "status": "ok" if database_ready else "degraded",
        "ready": database_ready,
        "service": "dashboard-analyzer",
        "version": settings.app_version,
        "database": "postgres" if state.pool is not None else "memory",
        "sources": {
            source.value: "configured" if source in providers else "not_configured" if source in active else "inactive"
            for source in SourceName
        },
        "analyzer": "gemini" if getattr(state.intelligence, "gemini", None) is not None else "local_fallback",
        "scheduler_enabled": settings.scheduler_enabled,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
