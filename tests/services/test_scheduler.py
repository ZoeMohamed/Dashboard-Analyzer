from datetime import timedelta

from app.config import Settings
from app.contracts import CollectionResult, RunTrigger, SourceName, SourceRun, SourceStatus, TopicCreate, utc_now
from app.database.repository import InMemoryRepository
from app.services.pipeline import PipelineService
from app.services.scheduler import RefreshScheduler


class CountingProvider:
    source = SourceName.YOUTUBE
    provider_name = "youtube"

    def __init__(self) -> None:
        self.calls = 0

    async def collect(self, topic, *, limit: int) -> CollectionResult:
        self.calls += 1
        return CollectionResult(source=self.source)


async def test_scheduler_refreshes_only_stale_configured_sources_within_cap() -> None:
    repository = InMemoryRepository()
    fresh = await repository.create_topic(TopicCreate(name="Seblak"))
    stale = await repository.create_topic(TopicCreate(name="Bakso"))
    never = await repository.create_topic(TopicCreate(name="Cilok"))
    settings = Settings(_env_file=None, app_env="test", source_ttl_minutes=60, scheduler_max_runs_per_tick=5, active_sources=[SourceName.YOUTUBE, SourceName.TIKTOK])
    provider = CountingProvider()
    pipeline = PipelineService(repository, settings, providers={SourceName.YOUTUBE: provider})
    now = utc_now()
    await repository.upsert_run(SourceRun(id="r1", topic_id=fresh.id, source=SourceName.YOUTUBE, status=SourceStatus.FRESH, started_at=now - timedelta(minutes=5)))
    # A recent failure also waits for the TTL instead of retrying every tick.
    await repository.upsert_run(SourceRun(id="r2", topic_id=stale.id, source=SourceName.YOUTUBE, status=SourceStatus.ERROR, started_at=now - timedelta(minutes=90)))

    scheduler = RefreshScheduler(pipeline, settings)
    due = await scheduler.due_sources(now)
    # TikTok has no provider (not configured) and is never scheduled.
    assert sorted(due) == sorted([(stale.id, SourceName.YOUTUBE), (never.id, SourceName.YOUTUBE)])

    assert await scheduler.tick(now) == 2
    assert provider.calls == 2
    latest = await repository.latest_run(stale.id, SourceName.YOUTUBE)
    assert latest.trigger == RunTrigger.SCHEDULED and latest.status == SourceStatus.EMPTY
    assert await scheduler.due_sources(now) == []


async def test_scheduler_respects_max_runs_per_tick() -> None:
    repository = InMemoryRepository()
    for name in ("Satu", "Dua", "Tiga"):
        await repository.create_topic(TopicCreate(name=name))
    settings = Settings(_env_file=None, app_env="test", scheduler_max_runs_per_tick=2, active_sources=[SourceName.YOUTUBE])
    pipeline = PipelineService(repository, settings, providers={SourceName.YOUTUBE: CountingProvider()})
    assert len(await RefreshScheduler(pipeline, settings).due_sources()) == 2
