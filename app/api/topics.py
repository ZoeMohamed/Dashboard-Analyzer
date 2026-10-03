from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.dependencies import get_repository
from app.contracts import Topic, TopicCreate, TopicListResponse
from app.database.repository import InMemoryRepository, PostgresRepository
from app.errors import TopicNotFoundError

router = APIRouter(tags=["topics"])
Repository = InMemoryRepository | PostgresRepository


@router.get("/topics", response_model=TopicListResponse)
async def list_topics(repository: Repository = Depends(get_repository)) -> TopicListResponse:
    return TopicListResponse(topics=await repository.list_topics())


@router.post("/topics", response_model=Topic, status_code=status.HTTP_201_CREATED)
async def create_topic(payload: TopicCreate, repository: Repository = Depends(get_repository)) -> Topic:
    return await repository.create_topic(payload)


@router.delete("/topics/{topic_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_topic(topic_id: str, repository: Repository = Depends(get_repository)) -> Response:
    try:
        await repository.delete_topic(topic_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except TopicNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
