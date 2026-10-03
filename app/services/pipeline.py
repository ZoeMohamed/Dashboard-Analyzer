"""Idempotent source orchestration and snapshot-first refresh behavior."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

from app.config import Settings
from app.contracts import (
    CollectionResult,
    ErrorCode,
    Evidence,
    RefreshRequest,
    RefreshResponse,
    RunTrigger,
    SourceName,
    SourceRun,
    SourceStatus,
    StreamEvent,
    StreamEventName,
    utc_now,
)
from app.database.repository import evidence_key
from app.errors import BudgetExhaustedError, DomainError, NotConfiguredError, ProviderTimeoutError
from app.services.events import EventBroker
from app.services.usage import UsageService

logger = logging.getLogger(__name__)


class SourceProvider(Protocol):
    source: SourceName
    provider_name: str

    async def collect(self, topic: object, *, limit: int) -> CollectionResult: ...


def _provider_name(provider: object) -> str:
    return str(getattr(provider, "provider_name", "apify"))


class PipelineService:
    def __init__(self, repository: object, settings: Settings, providers: dict[SourceName, SourceProvider] | None = None, broker: EventBroker | None = None, usage: UsageService | None = None, intelligence: Any | None = None) -> None:
        self.repository = repository
        self.settings = settings
        self.providers = providers or {}
        self.broker = broker or EventBroker()
        self.usage = usage or UsageService(repository, settings)
        # Optional so platform tests can run without the intelligence layer.
        self.intelligence = intelligence
        self._locks: dict[tuple[str, SourceName], asyncio.Lock] = {}
        self._tasks: set[asyncio.Task[object]] = set()

    def _lock_for(self, topic_id: str, source: SourceName) -> asyncio.Lock:
        return self._locks.setdefault((topic_id, source), asyncio.Lock())

    async def _emit(self, event: StreamEvent) -> None:
        await self.broker.publish(event)

    async def run_source(self, topic_id: str, source: SourceName, *, trigger: RunTrigger = RunTrigger.MANUAL) -> SourceRun:
        topic = await self.repository.get_topic(topic_id)
        lock = self._lock_for(topic_id, source)
        if lock.locked():
            # The in-flight run already covers this (topic, source). Waiting and
            # running again would pay the provider twice for the same data, and
            # persisting a second run would leave a stale "queued" row behind.
            return SourceRun(topic_id=topic_id, source=source, status=SourceStatus.RUNNING, trigger=trigger, error_code=ErrorCode.ALREADY_RUNNING, message="Sumber sedang diproses")
        async with lock:
            run_id = f"run-{uuid4().hex}"
            run = await self.repository.upsert_run(SourceRun(id=run_id, topic_id=topic_id, source=source, status=SourceStatus.QUEUED, trigger=trigger))
            await self._emit(StreamEvent(event=StreamEventName.SOURCE_STATUS, topic_id=topic_id, source=source, status=SourceStatus.QUEUED, run_id=run_id))
            provider = self.providers.get(source)
            if provider is None:
                return await self._finish(run, SourceStatus.MISCONFIGURED, ErrorCode.NOT_CONFIGURED, "Sumber belum dikonfigurasi")

            started = utc_now()
            run = await self.repository.upsert_run(run.model_copy(update={"status": SourceStatus.RUNNING, "started_at": started}))
            await self._emit(StreamEvent(event=StreamEventName.SOURCE_STATUS, topic_id=topic_id, source=source, status=SourceStatus.RUNNING, run_id=run_id, progress=0))
            try:
                provider_name = _provider_name(provider)
                if provider_name in {"apify", "gemini"}:
                    # Reserve a minimum unit before the network call. If the
                    # result reports a larger cost, account for the remainder.
                    await self.usage.reserve(provider_name, source, 1)
                result = await provider.collect(topic, limit=self.settings.source_result_limit)
                if provider_name in {"apify", "gemini"} and result.usage_units > 1:
                    # Already paid: record the real cost so the next reservation
                    # is blocked, but keep the data instead of discarding it.
                    await self.usage.record(provider_name, source, result.usage_units - 1)
                collected = [item.model_copy(update={"topic_id": topic_id, "provider_run_id": result.provider_run_id or run_id}) for item in result.items]
                relevant = self.intelligence.filter_relevant(topic, collected) if self.intelligence else collected
                # Use the storage key as the evidence id so analyses join to it.
                items = [item.model_copy(update={"id": evidence_key(topic_id, item)}) for item in relevant]
                inserted = await self.repository.upsert_evidence(items)
                await self._analyze(topic_id, source, run_id, items)
                status = SourceStatus.FRESH if items else SourceStatus.EMPTY
                final = await self._finish(run.model_copy(update={"provider_run_id": result.provider_run_id, "raw_count": result.raw_count, "relevant_count": len(items), "inserted_count": inserted}), status, None, "Sumber berhasil diproses" if items else "Tidak ada evidence relevan")
                await self._emit(StreamEvent(event=StreamEventName.PROGRESS, topic_id=topic_id, source=source, status=status, run_id=run_id, progress=1, message=final.message))
                return final
            except BudgetExhaustedError as exc:
                return await self._finish(run, SourceStatus.BUDGET_EXHAUSTED, ErrorCode.BUDGET_EXHAUSTED, str(exc))
            except NotConfiguredError as exc:
                return await self._finish(run, SourceStatus.MISCONFIGURED, ErrorCode.NOT_CONFIGURED, str(exc))
            except (ProviderTimeoutError, TimeoutError, asyncio.TimeoutError) as exc:
                return await self._finish(run, SourceStatus.ERROR, ErrorCode.PROVIDER_TIMEOUT, str(exc) or "Provider timeout")
            except DomainError as exc:
                return await self._finish(run, SourceStatus.ERROR, exc.code, str(exc))
            except Exception as exc:  # provider isolation: one source never cancels siblings
                return await self._finish(run, SourceStatus.ERROR, ErrorCode.INVALID_PAYLOAD, f"Provider gagal: {str(exc)[:400]}")

    async def _analyze(self, topic_id: str, source: SourceName, run_id: str, items: list[Evidence]) -> None:
        """Analyze evidence that has no analysis yet; never fails the source run."""
        if self.intelligence is None or not items:
            return
        try:
            missing = await self.repository.missing_analysis_ids(item.id for item in items)
            analyses = await self.intelligence.analyze([item for item in items if item.id in missing])
            for analysis in analyses:
                await self.repository.upsert_analysis(analysis)
        except Exception:
            logger.exception("Analisis %s gagal untuk %s; evidence tetap disimpan", source, topic_id)
            return
        if analyses:
            await self._emit(StreamEvent(event=StreamEventName.ANALYSIS_UPDATED, topic_id=topic_id, source=source, run_id=run_id, message=f"{len(analyses)} evidence dianalisis"))

    async def _finish(self, run: SourceRun, status: SourceStatus, code: ErrorCode | None, message: str) -> SourceRun:
        final = await self.repository.upsert_run(run.model_copy(update={"status": status, "error_code": code, "message": message, "finished_at": utc_now()}))
        await self._emit(StreamEvent(event=StreamEventName.SOURCE_STATUS if status != SourceStatus.ERROR else StreamEventName.ERROR, topic_id=final.topic_id, source=final.source, status=status, run_id=final.id, progress=1 if status in {SourceStatus.FRESH, SourceStatus.EMPTY} else None, message=message))
        return final

    async def refresh(self, topic_id: str, sources: list[SourceName] | None = None, *, trigger: RunTrigger = RunTrigger.MANUAL) -> list[SourceRun]:
        selected = sources or list(self.settings.active_sources)
        return list(await asyncio.gather(*(self.run_source(topic_id, source, trigger=trigger) for source in selected), return_exceptions=False))

    def start_refresh(self, topic_id: str, request: RefreshRequest | None = None) -> RefreshResponse:
        job_id = f"job-{uuid4().hex}"
        task = asyncio.create_task(self.refresh(topic_id, request.sources if request else None))
        self._tasks.add(task)
        task.add_done_callback(self._task_finished)
        return RefreshResponse(run_id=job_id, status=SourceStatus.QUEUED)

    def _task_finished(self, task: asyncio.Task[object]) -> None:
        self._tasks.discard(task)
        if not task.cancelled():
            task.exception()  # consume unexpected background failures

    async def snapshot(self, topic_id: str, *, limit: int | None = None, cursor: str | None = None):
        page_limit = min(limit or self.settings.snapshot_evidence_limit, self.settings.snapshot_evidence_limit)
        return await self.repository.snapshot(topic_id, limit=page_limit, cursor=cursor)
