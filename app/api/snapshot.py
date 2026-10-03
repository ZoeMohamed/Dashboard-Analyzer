from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_pipeline
from app.contracts import Snapshot
from app.errors import TopicNotFoundError
from app.services.pipeline import PipelineService

router = APIRouter(tags=["snapshot"])


@router.get("/topics/{topic_id}/snapshot", response_model=Snapshot)
async def get_snapshot(topic_id: str, pipeline: PipelineService = Depends(get_pipeline)) -> Snapshot:
    try:
        return await pipeline.snapshot(topic_id)
    except TopicNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
