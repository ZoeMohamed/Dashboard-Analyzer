from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_pipeline
from app.contracts import Snapshot, SourceName
from app.errors import TopicNotFoundError
from app.services.pipeline import PipelineService

router = APIRouter(tags=["snapshot"])


@router.get("/topics/{topic_id}/snapshot", response_model=Snapshot)
async def get_snapshot(
    topic_id: str,
    limit: int | None = Query(default=None, ge=1, le=500),
    cursor: str | None = None,
    source: SourceName | None = Query(default=None, description="Batasi evidence, total, dan sentimen pada satu sumber"),
    pipeline: PipelineService = Depends(get_pipeline),
) -> Snapshot:
    try:
        return await pipeline.snapshot(topic_id, limit=limit, cursor=cursor, source=source)
    except TopicNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
