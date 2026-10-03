from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_pipeline
from app.contracts import RefreshRequest, RefreshResponse
from app.errors import TopicNotFoundError
from app.services.pipeline import PipelineService

router = APIRouter(tags=["refresh"])


@router.post("/topics/{topic_id}/refresh", response_model=RefreshResponse, status_code=202)
async def refresh_topic(topic_id: str, payload: RefreshRequest | None = None, pipeline: PipelineService = Depends(get_pipeline)) -> RefreshResponse:
    try:
        await pipeline.repository.get_topic(topic_id)
        return pipeline.start_refresh(topic_id, payload)
    except TopicNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
