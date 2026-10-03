"""Repository boundary for topics, evidence, analysis, runs, and usage.

Routes and orchestration never contain SQL. The in-memory implementation keeps
the same async API so the app can be started before a Supabase project exists.
"""

from __future__ import annotations

import asyncio
import json
from collections import Counter
from datetime import date, datetime, timezone
from typing import Any, Iterable

from app.contracts import (
    Analysis,
    Evidence,
    EvidenceItem,
    EvidenceMetrics,
    ProviderUsage,
    Snapshot,
    SourceName,
    SourceRun,
    SourceStatus,
    SourceSummary,
    Topic,
    TopicCreate,
    utc_now,
)
from app.errors import TopicNotFoundError


def _topic_slug(name: str) -> str:
    value = "-".join(part for part in name.casefold().split() if part)
    return "".join(char for char in value if char.isalnum() or char == "-")[:110] or "topic"


def evidence_key(topic_id: str, evidence: Evidence) -> str:
    # The same public post may be relevant to more than one monitoring topic.
    # Namespacing by topic prevents a primary-key collision and cross-topic
    # overwrite while the unique constraint remains the deduplication key.
    return f"{topic_id}:{evidence.source}:{evidence.external_id}"


class InMemoryRepository:
    """Deterministic repository used by local dev and unit tests."""

    def __init__(self) -> None:
        self.topics: dict[str, Topic] = {}
        self.evidence: dict[str, Evidence] = {}
        self.analyses: dict[str, Analysis] = {}
        self.runs: dict[str, SourceRun] = {}
        self.usage: dict[tuple[str, str, date], ProviderUsage] = {}
        self._lock = asyncio.Lock()

    async def create_topic(self, payload: TopicCreate) -> Topic:
        async with self._lock:
            base = _topic_slug(payload.name)
            topic_id = base
            suffix = 2
            while topic_id in self.topics:
                topic_id = f"{base}-{suffix}"
                suffix += 1
            now = utc_now()
            topic = Topic(id=topic_id, **payload.model_dump(), created_at=now, updated_at=now)
            self.topics[topic.id] = topic
            return topic

    async def list_topics(self, *, active_only: bool = True) -> list[Topic]:
        values = [item for item in self.topics.values() if item.is_active or not active_only]
        return sorted(values, key=lambda item: item.created_at, reverse=True)

    async def get_topic(self, topic_id: str) -> Topic:
        topic = self.topics.get(topic_id)
        if topic is None or not topic.is_active:
            raise TopicNotFoundError(f"Topic tidak ditemukan: {topic_id}")
        return topic

    async def delete_topic(self, topic_id: str) -> None:
        topic = await self.get_topic(topic_id)
        self.topics[topic_id] = topic.model_copy(update={"is_active": False, "updated_at": utc_now()})

    async def upsert_run(self, run: SourceRun) -> SourceRun:
        run_id = run.id or f"run-{run.topic_id}-{run.source}-{int(utc_now().timestamp() * 1000)}"
        value = run.model_copy(update={"id": run_id})
        async with self._lock:
            self.runs[run_id] = value
        return value

    async def upsert_evidence(self, items: Iterable[Evidence]) -> int:
        inserted = 0
        async with self._lock:
            for item in items:
                key = evidence_key(item.topic_id, item)
                if key not in self.evidence:
                    inserted += 1
                self.evidence[key] = item.model_copy(update={"id": key})
        return inserted

    async def upsert_analysis(self, analysis: Analysis) -> None:
        async with self._lock:
            self.analyses[analysis.evidence_id] = analysis

    async def missing_analysis_ids(self, evidence_ids: Iterable[str]) -> set[str]:
        return {evidence_id for evidence_id in evidence_ids if evidence_id not in self.analyses}

    async def record_usage(self, usage: ProviderUsage) -> ProviderUsage:
        source = usage.source.value if isinstance(usage.source, SourceName) else (usage.source or "global")
        key = (usage.provider, source, usage.usage_date)
        async with self._lock:
            current = self.usage.get(key)
            if current is None:
                current = usage.model_copy(update={"source": None if source == "global" else source})
            else:
                current = current.model_copy(
                    update={
                        "requests": current.requests + usage.requests,
                        "units": current.units + usage.units,
                    }
                )
            self.usage[key] = current
            return current

    async def reserve_usage(self, provider: str, source: SourceName | None, usage_date: date, units: int, limit: int) -> ProviderUsage | None:
        source_key = source.value if isinstance(source, SourceName) else (source or "global")
        key = (provider, source_key, usage_date)
        async with self._lock:
            current = self.usage.get(key) or ProviderUsage(provider=provider, source=None if source_key == "global" else source_key, usage_date=usage_date)
            if current.units + units > limit:
                return None
            reserved = current.model_copy(update={"requests": current.requests + 1, "units": current.units + units})
            self.usage[key] = reserved
            return reserved

    async def get_usage(self, provider: str, source: SourceName | None, usage_date: date) -> ProviderUsage:
        source_key = source.value if isinstance(source, SourceName) else (source or "global")
        value = self.usage.get((provider, source_key, usage_date))
        return value or ProviderUsage(provider=provider, source=None if source_key == "global" else source_key, usage_date=usage_date)

    async def snapshot(self, topic_id: str, *, limit: int = 100, cursor: str | None = None) -> Snapshot:
        topic = await self.get_topic(topic_id)
        values = [item for item in self.evidence.values() if item.topic_id == topic_id]
        values.sort(key=lambda item: (item.collected_at, item.id or ""), reverse=True)
        start = 0
        if cursor:
            start = next((index + 1 for index, item in enumerate(values) if item.id == cursor), 0)
        available = values[start:]
        page = available[:limit]
        all_analyses = [self.analyses[item.id] for item in values if item.id in self.analyses]
        analyses = [self.analyses[item.id] for item in page if item.id in self.analyses]
        evidence_page = [EvidenceItem(**item.model_dump(), analysis=self.analyses.get(item.id)) for item in page]
        runs = [run for run in self.runs.values() if run.topic_id == topic_id]
        runs.sort(key=lambda item: item.started_at, reverse=True)
        counts = Counter(item.label for item in all_analyses)
        aspects = Counter(aspect for item in all_analyses for aspect in item.aspects)
        latest: dict[SourceName, SourceRun] = {}
        for run in runs:
            if run.source not in latest:
                latest[run.source] = run
        summaries = []
        for source in SourceName:
            run = latest.get(source)
            source_count = sum(1 for item in values if item.source == source)
            summaries.append(
                SourceSummary(
                    source=source,
                    evidence_count=source_count,
                    status=run.status if run else SourceStatus.MISCONFIGURED,
                    last_finished_at=run.finished_at if run else None,
                    updated_at=run.finished_at or run.started_at if run else None,
                    message=run.message if run else "Belum ada adapter aktif",
                )
            )
        return Snapshot(
            topic=topic,
            total_evidence=len(values),
            positive_count=counts.get("positif", 0),
            negative_count=counts.get("negatif", 0),
            neutral_count=counts.get("netral", 0),
            pending_count=counts.get("pending", 0) + max(0, len(values) - len(all_analyses)),
            top_aspects=[name for name, _ in aspects.most_common(10)],
            source_summaries=summaries,
            evidence=evidence_page,
            analyses=analyses,
            source_runs=runs[:20],
            updated_at=max((item.collected_at for item in values), default=None),
            next_cursor=page[-1].id if len(available) > limit and page else None,
        )


class PostgresRepository:
    """PostgreSQL implementation matching the in-memory repository contract."""

    def __init__(self, pool: Any) -> None:
        self.pool = pool

    async def create_topic(self, payload: TopicCreate) -> Topic:
        base = _topic_slug(payload.name)
        topic_id = base
        for suffix in range(2, 1000):
            try:
                row = await self.pool.fetchrow(
                    """insert into topics (id, name, keywords, product_terms, exclude_terms, cities)
                       values ($1, $2, $3, $4, $5, $6)
                       returning *""",
                    topic_id,
                    payload.name,
                    payload.keywords,
                    payload.product_terms,
                    payload.exclude_terms,
                    payload.cities,
                )
                return _topic(row)
            except Exception as exc:
                if "duplicate key" not in str(exc).lower():
                    raise
                topic_id = f"{base}-{suffix}"
        raise RuntimeError("Tidak dapat membuat ID topic unik")

    async def list_topics(self, *, active_only: bool = True) -> list[Topic]:
        clause = "where is_active = true" if active_only else ""
        rows = await self.pool.fetch(f"select * from topics {clause} order by created_at desc")
        return [_topic(row) for row in rows]

    async def get_topic(self, topic_id: str) -> Topic:
        row = await self.pool.fetchrow("select * from topics where id = $1 and is_active = true", topic_id)
        if not row:
            raise TopicNotFoundError(f"Topic tidak ditemukan: {topic_id}")
        return _topic(row)

    async def delete_topic(self, topic_id: str) -> None:
        result = await self.pool.execute("update topics set is_active = false, updated_at = now() where id = $1 and is_active = true", topic_id)
        if result.endswith("0"):
            raise TopicNotFoundError(f"Topic tidak ditemukan: {topic_id}")

    async def upsert_run(self, run: SourceRun) -> SourceRun:
        value = run if run.id else run.model_copy(update={"id": f"run-{run.topic_id}-{run.source}-{int(utc_now().timestamp() * 1000)}"})
        row = await self.pool.fetchrow(
            """insert into source_runs
              (id, topic_id, source, status, trigger, provider_run_id, raw_count, relevant_count,
               inserted_count, error_code, message, started_at, finished_at)
              values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
              on conflict (id) do update set status=excluded.status, provider_run_id=excluded.provider_run_id,
                raw_count=excluded.raw_count, relevant_count=excluded.relevant_count,
                inserted_count=excluded.inserted_count, error_code=excluded.error_code,
                message=excluded.message, finished_at=excluded.finished_at
              returning *""",
            value.id, value.topic_id, value.source, value.status, value.trigger, value.provider_run_id,
            value.raw_count, value.relevant_count, value.inserted_count, value.error_code, value.message,
            value.started_at, value.finished_at,
        )
        return _run(row)

    async def upsert_evidence(self, items: Iterable[Evidence]) -> int:
        inserted = 0
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                for item in items:
                    evidence_id = evidence_key(item.topic_id, item)
                    was_inserted = await connection.fetchval(
                        """insert into evidence
                          (id, topic_id, source, external_id, provider_run_id, title, text, author, url,
                           published_at, collected_at, relevance_score, views, likes, comments, shares,
                           rating, review_count, price, original_price, sold, metadata)
                          values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22)
                          on conflict (topic_id, source, external_id) do update set
                            title=excluded.title, text=excluded.text, author=excluded.author, url=excluded.url,
                            published_at=excluded.published_at, collected_at=excluded.collected_at,
                            relevance_score=excluded.relevance_score, views=excluded.views, likes=excluded.likes,
                            comments=excluded.comments, shares=excluded.shares, rating=excluded.rating,
                            review_count=excluded.review_count, price=excluded.price, original_price=excluded.original_price,
                            sold=excluded.sold, metadata=excluded.metadata
                          returning (xmax = 0) as inserted""",
                        evidence_id, item.topic_id, item.source, item.external_id, item.provider_run_id,
                        item.title, item.text, item.author, item.url, item.published_at, item.collected_at,
                        item.relevance_score, item.metrics.views, item.metrics.likes, item.metrics.comments,
                        item.metrics.shares, item.metrics.rating, item.metrics.review_count, item.metrics.price,
                        item.metrics.original_price, item.metrics.sold, json.dumps(item.metadata),
                    )
                    if was_inserted:
                        inserted += 1
        return inserted

    async def upsert_analysis(self, analysis: Analysis) -> None:
        await self.pool.execute(
            """insert into analyses (evidence_id, label, score, confidence, aspects, analyzer, analyzed_at)
               values ($1,$2,$3,$4,$5,$6,$7)
               on conflict (evidence_id) do update set label=excluded.label, score=excluded.score,
                 confidence=excluded.confidence, aspects=excluded.aspects, analyzer=excluded.analyzer,
                 analyzed_at=excluded.analyzed_at""",
            analysis.evidence_id, analysis.label, analysis.score, analysis.confidence, analysis.aspects,
            analysis.analyzer, analysis.analyzed_at,
        )

    async def missing_analysis_ids(self, evidence_ids: Iterable[str]) -> set[str]:
        ids = list(dict.fromkeys(evidence_ids))
        if not ids:
            return set()
        rows = await self.pool.fetch("select evidence_id from analyses where evidence_id = any($1::text[])", ids)
        return set(ids) - {row["evidence_id"] for row in rows}

    async def record_usage(self, usage: ProviderUsage) -> ProviderUsage:
        source = usage.source.value if isinstance(usage.source, SourceName) else (usage.source or "global")
        row = await self.pool.fetchrow(
            """insert into provider_usage (provider, source, usage_date, requests, units)
               values ($1,$2,$3,$4,$5)
               on conflict (provider, source, usage_date) do update set
                 requests=provider_usage.requests + excluded.requests,
                 units=provider_usage.units + excluded.units
               returning *""",
            usage.provider, source, usage.usage_date, usage.requests, usage.units,
        )
        return _usage(row)

    async def reserve_usage(self, provider: str, source: SourceName | None, usage_date: date, units: int, limit: int) -> ProviderUsage | None:
        source_key = source.value if isinstance(source, SourceName) else (source or "global")
        row = await self.pool.fetchrow(
            """insert into provider_usage (provider, source, usage_date, requests, units)
               values ($1,$2,$3,1,$4)
               on conflict (provider, source, usage_date) do update set
                 requests=provider_usage.requests + 1,
                 units=provider_usage.units + excluded.units
               where provider_usage.units + excluded.units <= $5
               returning *""",
            provider, source_key, usage_date, units, limit,
        )
        return _usage(row) if row else None

    async def get_usage(self, provider: str, source: SourceName | None, usage_date: date) -> ProviderUsage:
        source_key = source.value if isinstance(source, SourceName) else (source or "global")
        row = await self.pool.fetchrow("select * from provider_usage where provider=$1 and source=$2 and usage_date=$3", provider, source_key, usage_date)
        return _usage(row) if row else ProviderUsage(provider=provider, source=None if source_key == "global" else source_key, usage_date=usage_date)

    async def snapshot(self, topic_id: str, *, limit: int = 100, cursor: str | None = None) -> Snapshot:
        topic = await self.get_topic(topic_id)
        total_evidence = await self.pool.fetchval("select count(*) from evidence where topic_id=$1", topic_id)
        source_count_rows = await self.pool.fetch("select source, count(*) as count from evidence where topic_id=$1 group by source", topic_id)
        source_counts = {row["source"]: row["count"] for row in source_count_rows}
        if cursor:
            rows = await self.pool.fetch(
                """select * from evidence
                   where topic_id=$1 and (collected_at, id) < (
                     select collected_at, id from evidence where topic_id=$1 and id=$2
                   )
                   order by collected_at desc, id desc limit $3""",
                topic_id, cursor, limit + 1,
            )
        else:
            rows = await self.pool.fetch(
                """select * from evidence where topic_id=$1
                   order by collected_at desc, id desc limit $2""", topic_id, limit + 1,
            )
        has_next_page = len(rows) > limit
        rows = rows[:limit]
        evidence = [_evidence(row) for row in rows]
        ids = [item.id for item in evidence]
        analysis_rows = await self.pool.fetch("select * from analyses where evidence_id = any($1::text[])", ids) if ids else []
        analyses = [_analysis(row) for row in analysis_rows]
        analysis_by_evidence = {item.evidence_id: item for item in analyses}
        evidence_page = [EvidenceItem(**item.model_dump(), analysis=analysis_by_evidence.get(item.id)) for item in evidence]
        sentiment_rows = await self.pool.fetch(
            """select a.label, count(*) as count from analyses a
               join evidence e on e.id=a.evidence_id where e.topic_id=$1 group by a.label""",
            topic_id,
        )
        counts = Counter({row["label"]: row["count"] for row in sentiment_rows})
        analyzed_count = sum(counts.values())
        aspect_rows = await self.pool.fetch(
            """select aspect, count(*) as count from analyses a
               join evidence e on e.id=a.evidence_id
               cross join lateral unnest(a.aspects) as u(aspect)
               where e.topic_id=$1 group by u.aspect order by count(*) desc, u.aspect limit 10""",
            topic_id,
        )
        run_rows = await self.pool.fetch("select * from source_runs where topic_id=$1 order by started_at desc limit 50", topic_id)
        runs = [_run(row) for row in run_rows]
        latest: dict[SourceName, SourceRun] = {}
        for run in runs:
            latest.setdefault(run.source, run)
        summaries = [SourceSummary(source=source, evidence_count=source_counts.get(source, 0), status=latest[source].status if source in latest else SourceStatus.MISCONFIGURED, last_finished_at=latest[source].finished_at if source in latest else None, updated_at=(latest[source].finished_at or latest[source].started_at) if source in latest else None, message=latest[source].message if source in latest else "Belum ada adapter aktif") for source in SourceName]
        return Snapshot(topic=topic, total_evidence=total_evidence, positive_count=counts.get("positif", 0), negative_count=counts.get("negatif", 0), neutral_count=counts.get("netral", 0), pending_count=counts.get("pending", 0) + max(0, total_evidence - analyzed_count), top_aspects=[row["aspect"] for row in aspect_rows], source_summaries=summaries, evidence=evidence_page, analyses=analyses, source_runs=runs, updated_at=max((item.collected_at for item in evidence), default=None), next_cursor=evidence[-1].id if has_next_page and evidence else None)


def _topic(row: Any) -> Topic:
    return Topic(id=row["id"], name=row["name"], keywords=row["keywords"] or [], product_terms=row["product_terms"] or [], exclude_terms=row["exclude_terms"] or [], cities=row["cities"] or [], is_active=row["is_active"], created_at=row["created_at"], updated_at=row["updated_at"])


def _evidence(row: Any) -> Evidence:
    metrics = EvidenceMetrics(views=row["views"], likes=row["likes"], comments=row["comments"], shares=row["shares"], rating=row["rating"], review_count=row["review_count"], price=row["price"], original_price=row["original_price"], sold=row["sold"])
    metadata = row["metadata"] or {}
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    return Evidence(id=row["id"], topic_id=row["topic_id"], source=row["source"], external_id=row["external_id"], provider_run_id=row["provider_run_id"], title=row["title"], text=row["text"], author=row["author"], url=row["url"], published_at=row["published_at"], collected_at=row["collected_at"], relevance_score=row["relevance_score"], metrics=metrics, metadata=metadata)


def _analysis(row: Any) -> Analysis:
    return Analysis(evidence_id=row["evidence_id"], label=row["label"], score=row["score"], confidence=row["confidence"], aspects=row["aspects"] or [], analyzer=row["analyzer"], analyzed_at=row["analyzed_at"])


def _run(row: Any) -> SourceRun:
    return SourceRun(id=row["id"], topic_id=row["topic_id"], source=row["source"], status=row["status"], trigger=row["trigger"], provider_run_id=row["provider_run_id"], raw_count=row["raw_count"], relevant_count=row["relevant_count"], inserted_count=row["inserted_count"], error_code=row["error_code"], message=row["message"], started_at=row["started_at"], finished_at=row["finished_at"])


def _usage(row: Any) -> ProviderUsage:
    return ProviderUsage(provider=row["provider"], source=None if row["source"] == "global" else row["source"], usage_date=row["usage_date"], requests=row["requests"], units=row["units"])
