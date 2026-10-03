"""Sources -> pipeline -> intelligence -> repository, without network."""

import asyncio

import pytest
from pydantic import SecretStr

from app.config import Settings
from app.contracts import AnalyzerName, CollectionResult, Evidence, SourceName, SourceStatus, TopicCreate
from app.database.repository import InMemoryRepository
from app.services.analysis import IntelligenceService
from app.services.pipeline import PipelineService
from app.services.providers import SourceAdapterProvider, build_providers
from app.services.usage import UsageService
from app.sources.base import CollectionResult as SourceResult
from app.sources.base import Evidence as SourceEvidence
from app.sources.base import EvidenceMetrics as SourceMetrics


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, app_env="test", **overrides)


def _source_item(topic_id: str, external_id: str, text: str, *, url: str | None = "https://example.com/p", **extra) -> SourceEvidence:
    return SourceEvidence(id=f"tiktok:{external_id}", source="tiktok", topic_id=topic_id, external_id=external_id, text=text, url=url, **extra)


class FakeAdapter:
    def __init__(self, result_factory) -> None:
        self.result_factory = result_factory
        self.calls = 0

    async def collect(self, topic, limit: int = 50) -> SourceResult:
        self.calls += 1
        await asyncio.sleep(0.01)
        return self.result_factory(topic)


async def _service(adapter, **settings_overrides):
    repository = InMemoryRepository()
    topic = await repository.create_topic(TopicCreate(name="Cappuccino Cincau", exclude_terms=["upin ipin"]))
    settings = _settings(active_sources=[SourceName.TIKTOK], **settings_overrides)
    usage = UsageService(repository, settings)
    service = PipelineService(
        repository, settings, usage=usage,
        providers={SourceName.TIKTOK: SourceAdapterProvider(adapter, SourceName.TIKTOK, "apify")},
        intelligence=IntelligenceService(settings, usage),
    )
    return repository, topic, service


@pytest.mark.asyncio
async def test_bridge_maps_metrics_and_skips_items_without_link() -> None:
    adapter = FakeAdapter(lambda topic: SourceResult(source="tiktok", raw_count=2, items=[
        _source_item(topic.id, "a", "cappuccino cincau enak", metrics=SourceMetrics(views=10, likes=2), metadata={"author_name": "budi", "rating": 4.5, "price": "15000"}),
        _source_item(topic.id, "b", "cappuccino cincau", url=None),
    ]))
    result = await SourceAdapterProvider(adapter, SourceName.TIKTOK, "apify").collect(
        await InMemoryRepository().create_topic(TopicCreate(name="Cappuccino Cincau")), limit=50
    )
    assert isinstance(result, CollectionResult)
    assert [item.external_id for item in result.items] == ["a"]
    item = result.items[0]
    assert (item.metrics.views, item.metrics.likes, item.metrics.rating, item.metrics.price) == (10, 2, 4.5, 15000)
    assert item.metrics.shares is None
    assert item.author == "budi"


@pytest.mark.asyncio
@pytest.mark.parametrize(("code", "status"), [
    ("not_configured", SourceStatus.MISCONFIGURED),
    ("provider_timeout", SourceStatus.ERROR),
    ("budget_exhausted", SourceStatus.BUDGET_EXHAUSTED),
    ("provider_error", SourceStatus.ERROR),
])
async def test_adapter_error_codes_become_run_statuses(code: str, status: SourceStatus) -> None:
    adapter = FakeAdapter(lambda topic: SourceResult(source="tiktok", error_code=code, message="gagal"))
    _, topic, service = await _service(adapter)
    run = await service.run_source(topic.id, SourceName.TIKTOK)
    assert run.status == status
    assert run.error_code == code


@pytest.mark.asyncio
async def test_relevance_gate_and_analysis_share_the_stored_evidence_id() -> None:
    adapter = FakeAdapter(lambda topic: SourceResult(source="tiktok", raw_count=4, items=[
        _source_item(topic.id, "1", "Cappuccino cincau ini enak banget"),
        _source_item(topic.id, "2", "Es cincau segar"),  # one product term only
        _source_item(topic.id, "3", "Upin Ipin minum cappuccino cincau"),  # excluded
        _source_item(topic.id, "4", "cincau di atas cappuccino, tidak enak"),  # two product terms
    ]))
    repository, topic, service = await _service(adapter)
    run = await service.run_source(topic.id, SourceName.TIKTOK)
    snapshot = await repository.snapshot(topic.id)
    assert run.status == SourceStatus.FRESH
    assert (run.raw_count, run.relevant_count, run.inserted_count) == (4, 2, 2)
    by_external = {item.external_id: item for item in snapshot.evidence}
    assert set(by_external) == {"1", "4"}
    assert all(item.analysis and item.analysis.evidence_id == item.id for item in snapshot.evidence)
    assert by_external["1"].analysis.label == "positif"
    assert by_external["4"].analysis.label == "negatif"
    assert by_external["1"].analysis.analyzer == AnalyzerName.LOCAL_FALLBACK
    assert snapshot.sentiment.positif == 1 and snapshot.sentiment.negatif == 1 and snapshot.sentiment.pending == 0


@pytest.mark.asyncio
async def test_concurrent_refresh_calls_provider_once() -> None:
    adapter = FakeAdapter(lambda topic: SourceResult(source="tiktok", raw_count=1, items=[_source_item(topic.id, "1", "cappuccino cincau")]))
    repository, topic, service = await _service(adapter)
    first, second = await asyncio.gather(service.refresh(topic.id), service.refresh(topic.id))
    assert adapter.calls == 1
    usage = await repository.get_usage("apify", SourceName.TIKTOK, service.usage._today())
    assert usage.units == 1
    assert {first[0].status, second[0].status} == {SourceStatus.FRESH, SourceStatus.RUNNING}


@pytest.mark.asyncio
async def test_paid_results_are_kept_when_cost_exceeds_remaining_budget() -> None:
    class CostlyProvider:
        source = SourceName.TIKTOK
        provider_name = "apify"

        async def collect(self, topic, *, limit: int) -> CollectionResult:
            return CollectionResult(source=self.source, raw_count=1, usage_units=5, items=[Evidence(source=self.source, topic_id=topic.id, external_id="a", text="cappuccino cincau", url="https://example.com/a")])

    repository = InMemoryRepository()
    topic = await repository.create_topic(TopicCreate(name="Cappuccino Cincau"))
    service = PipelineService(repository, _settings(active_sources=[SourceName.TIKTOK], apify_daily_run_limit=3), providers={SourceName.TIKTOK: CostlyProvider()})
    run = await service.run_source(topic.id, SourceName.TIKTOK)
    assert run.status == SourceStatus.FRESH
    assert (await repository.snapshot(topic.id)).total_evidence == 1
    second = await service.run_source(topic.id, SourceName.TIKTOK)
    assert second.status == SourceStatus.BUDGET_EXHAUSTED


@pytest.mark.asyncio
async def test_build_providers_registers_apify_sources_only_with_tokens() -> None:
    providers, clients = build_providers(_settings())
    assert set(providers) == {SourceName.YOUTUBE}
    providers, more = build_providers(_settings(apify_tokens=[SecretStr("token-a")]))
    assert set(providers) == set(SourceName)
    assert all(provider.provider_name == "apify" for source, provider in providers.items() if source != SourceName.YOUTUBE)
    for client in [*clients, *more]:
        await client.close()
