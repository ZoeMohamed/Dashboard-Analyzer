"""Bounded background refresh of stale sources (single replica only).

Disabled unless SCHEDULER_ENABLED=true because each scheduled Apify run spends
budget. A source is due when its latest run, successful or not, started more
than SOURCE_TTL_MINUTES ago, so a failing provider is not retried every tick.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from app.config import Settings
from app.contracts import RunTrigger, SourceName, utc_now
from app.services.pipeline import PipelineService

logger = logging.getLogger(__name__)


class RefreshScheduler:
    def __init__(self, pipeline: PipelineService, settings: Settings) -> None:
        self.pipeline = pipeline
        self.settings = settings
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    async def due_sources(self, now: datetime | None = None) -> list[tuple[str, SourceName]]:
        now = now or utc_now()
        cutoff = now - timedelta(minutes=self.settings.source_ttl_minutes)
        repository = self.pipeline.repository
        due: list[tuple[str, SourceName]] = []
        for topic in await repository.list_topics():
            for source in self.settings.active_sources:
                if source not in self.pipeline.providers:
                    continue
                latest = await repository.latest_run(topic.id, source)
                if latest is None or latest.started_at <= cutoff:
                    due.append((topic.id, SourceName(source)))
        return due[: self.settings.scheduler_max_runs_per_tick]

    async def tick(self, now: datetime | None = None) -> int:
        due = await self.due_sources(now)
        for topic_id, source in due:
            # Sequential on purpose: keeps Apify concurrency and spend predictable.
            await self.pipeline.run_source(topic_id, source, trigger=RunTrigger.SCHEDULED)
        return len(due)

    async def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                await self.tick()
            except Exception:
                logger.exception("Scheduler refresh gagal; dicoba lagi pada tick berikutnya")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.settings.scheduler_interval_seconds)
            except asyncio.TimeoutError:
                pass

    def start(self) -> None:
        if self._task is None:
            self._stop.clear()
            self._task = asyncio.create_task(self._loop(), name="refresh-scheduler")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
