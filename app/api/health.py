from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    return {
        "status": "ok",
        "service": "dashboard-analyzer",
        "version": settings.app_version,
        "database": "postgres" if request.app.state.pool is not None else "memory",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
