from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.contracts import Insights, SourceName
from app.errors import TopicNotFoundError
from app.services.insights import InsightsService

router = APIRouter(tags=["insights"])


def get_insights(request: Request) -> InsightsService:
    return request.app.state.insights


@router.get("/topics/{topic_id}/insights", response_model=Insights)
async def get_topic_insights(
    topic_id: str,
    source: SourceName | None = Query(default=None, description="Batasi agregat pada satu sumber"),
    days: int = Query(default=30, ge=7, le=90, description="Panjang jendela tren sentimen harian"),
    service: InsightsService = Depends(get_insights),
) -> Insights:
    try:
        return await service.build(topic_id, source=source, days=days)
    except TopicNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
