import pytest

from app.config import Settings
from app.contracts import CollectionResult, Evidence, SourceName, TopicCreate, SourceStatus
from app.database.repository import InMemoryRepository
from app.services.pipeline import PipelineService


class FakeProvider:
    source = SourceName.TIKTOK
    provider_name = "apify"

    async def collect(self, topic, *, limit: int) -> CollectionResult:
        return CollectionResult(source=self.source, raw_count=1, usage_units=1, items=[Evidence(source=self.source, topic_id=topic.id, external_id="a", title=topic.name, url="https://example.com/a")])


@pytest.mark.asyncio
async def test_one_source_failure_isolated_and_success_is_idempotent() -> None:
    repository = InMemoryRepository()
    topic = await repository.create_topic(TopicCreate(name="Keripik Pisang"))
    settings = Settings(app_env="test", active_sources=[SourceName.TIKTOK, SourceName.INSTAGRAM])
    service = PipelineService(repository, settings, providers={SourceName.TIKTOK: FakeProvider()})
    runs = await service.refresh(topic.id)
    assert {run.source for run in runs} == {SourceName.TIKTOK, SourceName.INSTAGRAM}
    assert next(run for run in runs if run.source == SourceName.TIKTOK).status == SourceStatus.FRESH
    assert next(run for run in runs if run.source == SourceName.INSTAGRAM).status == SourceStatus.MISCONFIGURED
    await service.run_source(topic.id, SourceName.TIKTOK)
    assert (await repository.snapshot(topic.id)).total_evidence == 1
