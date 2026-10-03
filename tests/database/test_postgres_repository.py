"""PostgresRepository against a real database.

Runs only when TEST_DATABASE_URL is set. The test works inside a temporary
schema that it creates and drops, so existing tables are never touched.
"""

import os
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from app.contracts import Analysis, AnalyzerName, Evidence, EvidenceMetrics, SourceName, SourceRun, SourceStatus, TopicCreate, utc_now
from app.database.repository import PostgresRepository, evidence_key

DSN = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="TEST_DATABASE_URL tidak diset")
MIGRATION = Path(__file__).parents[2] / "migrations" / "0001_initial.sql"


@pytest.fixture
async def repository():
    asyncpg = pytest.importorskip("asyncpg")
    schema = f"test_{uuid4().hex[:12]}"
    admin = await asyncpg.connect(DSN)
    await admin.execute(f"create schema {schema}")
    pool = await asyncpg.create_pool(DSN, min_size=1, max_size=3, server_settings={"search_path": schema})
    try:
        await pool.execute(MIGRATION.read_text())
        yield PostgresRepository(pool)
    finally:
        await pool.close()
        await admin.execute(f"drop schema {schema} cascade")
        await admin.close()


async def test_postgres_round_trip(repository: PostgresRepository) -> None:
    topic = await repository.create_topic(TopicCreate(name="Keripik Pisang", cities=["Bandung"]))
    duplicate = await repository.create_topic(TopicCreate(name="Keripik Pisang"))
    assert (topic.id, duplicate.id) == ("keripik-pisang", "keripik-pisang-2")
    assert await repository.count_active_topics() == 2

    now = utc_now()
    video = Evidence(source=SourceName.YOUTUBE, topic_id=topic.id, external_id="v1", title="Resep keripik pisang", url="https://youtube.com/watch?v=v1", metrics=EvidenceMetrics(views=100), collected_at=now - timedelta(hours=30), metadata={"content_type": "resep"})
    post = Evidence(source=SourceName.TIKTOK, topic_id=topic.id, external_id="t1", text="keripik pisang enak", url="https://tiktok.com/t1")
    assert await repository.upsert_evidence([video, post]) == 2
    assert await repository.upsert_evidence([video.model_copy(update={"metrics": EvidenceMetrics(views=250), "collected_at": now})]) == 0

    video_id = evidence_key(topic.id, video)
    assert [views for _, views in (await repository.metric_history([video_id]))[video_id]] == [100, 250]

    post_id = evidence_key(topic.id, post)
    assert await repository.missing_analysis_ids([video_id, post_id]) == {video_id, post_id}
    await repository.upsert_analysis(Analysis(evidence_id=post_id, label="positif", score=1, confidence=0.6, aspects=["rasa"], analyzer=AnalyzerName.LOCAL_FALLBACK))
    assert await repository.missing_analysis_ids([video_id, post_id]) == {video_id}

    snapshot = await repository.snapshot(topic.id, source=SourceName.TIKTOK)
    assert snapshot.total_evidence == 1 and snapshot.evidence[0].analysis.label == "positif"
    assert snapshot.sentiment.positif == 1 and snapshot.top_aspects == ["rasa"]
    assert {item.source: item.evidence_count for item in snapshot.sources}[SourceName.YOUTUBE] == 1

    page = await repository.snapshot(topic.id, limit=1)
    assert page.next_cursor and (await repository.snapshot(topic.id, limit=1, cursor=page.next_cursor)).evidence

    listed = await repository.list_topic_evidence(topic.id, source=SourceName.YOUTUBE)
    assert listed[0].metrics.views == 250 and listed[0].metadata == {"content_type": "resep"}

    await repository.upsert_run(SourceRun(id="r1", topic_id=topic.id, source=SourceName.YOUTUBE, status=SourceStatus.FRESH, started_at=now - timedelta(hours=1)))
    await repository.upsert_run(SourceRun(id="r2", topic_id=topic.id, source=SourceName.YOUTUBE, status=SourceStatus.ERROR, started_at=now))
    assert (await repository.latest_run(topic.id, SourceName.YOUTUBE)).id == "r2"

    assert await repository.reserve_usage("gemini", None, now.date(), 3, 2) is None  # first row of the day
    first = await repository.reserve_usage("apify", SourceName.TIKTOK, now.date(), 1, 2)
    second = await repository.reserve_usage("apify", SourceName.TIKTOK, now.date(), 1, 2)
    assert (first.units, second.units) == (1, 2)
    assert await repository.reserve_usage("apify", SourceName.TIKTOK, now.date(), 1, 2) is None

    await repository.delete_topic(duplicate.id)
    assert [item.id for item in await repository.list_topics()] == [topic.id]
