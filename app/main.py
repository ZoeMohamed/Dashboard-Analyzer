"""FastAPI entrypoint for Dashboard Analyzer."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, refresh, snapshot, stream, topics
from app.config import get_settings
from app.database.connection import close_pool, create_pool
from app.database.repository import InMemoryRepository, PostgresRepository
from app.services.analysis import IntelligenceService
from app.services.pipeline import PipelineService
from app.services.providers import build_providers
from app.services.usage import UsageService


@asynccontextmanager
async def lifespan(application: FastAPI):
    settings = get_settings()
    pool = await create_pool(settings)
    repository = PostgresRepository(pool) if pool is not None else InMemoryRepository()
    usage = UsageService(repository, settings)
    providers, clients = build_providers(settings)
    application.state.settings = settings
    application.state.pool = pool
    application.state.repository = repository
    application.state.pipeline = PipelineService(
        repository, settings, providers=providers, usage=usage,
        intelligence=IntelligenceService.from_settings(settings, usage),
    )
    try:
        yield
    finally:
        for client in clients:
            await client.close()
        await close_pool(pool)


app = FastAPI(title="Dashboard Analyzer", version=get_settings().app_version, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)
app.include_router(health.router, prefix="/api")
app.include_router(topics.router, prefix="/api")
app.include_router(snapshot.router, prefix="/api")
app.include_router(refresh.router, prefix="/api")
app.include_router(stream.router, prefix="/api")
