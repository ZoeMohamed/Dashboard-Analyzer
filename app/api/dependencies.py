from __future__ import annotations

from fastapi import Request

from app.database.repository import InMemoryRepository, PostgresRepository
from app.services.pipeline import PipelineService


def get_pipeline(request: Request) -> PipelineService:
    return request.app.state.pipeline


def get_repository(request: Request) -> InMemoryRepository | PostgresRepository:
    return request.app.state.repository
