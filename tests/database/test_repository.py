import pytest

from app.contracts import Evidence, SourceName, TopicCreate
from app.database.repository import InMemoryRepository


@pytest.mark.asyncio
async def test_upsert_is_idempotent_and_topics_do_not_leak() -> None:
    repository = InMemoryRepository()
    first = await repository.create_topic(TopicCreate(name="Kopi Susu"))
    second = await repository.create_topic(TopicCreate(name="Seblak"))
    item = Evidence(source=SourceName.TIKTOK, topic_id=first.id, external_id="post-1", title="Kopi susu", url="https://example.com/post-1")
    assert await repository.upsert_evidence([item]) == 1
    assert await repository.upsert_evidence([item]) == 0
    assert (await repository.snapshot(first.id)).total_evidence == 1
    assert (await repository.snapshot(second.id)).total_evidence == 0

    same_external_other_topic = item.model_copy(update={"topic_id": second.id})
    assert await repository.upsert_evidence([same_external_other_topic]) == 1
    assert (await repository.snapshot(first.id)).total_evidence == 1
    assert (await repository.snapshot(second.id)).total_evidence == 1


@pytest.mark.asyncio
async def test_snapshot_is_bounded() -> None:
    repository = InMemoryRepository()
    topic = await repository.create_topic(TopicCreate(name="Ayam Bakar"))
    for index in range(3):
        await repository.upsert_evidence([Evidence(source=SourceName.YOUTUBE, topic_id=topic.id, external_id=str(index), title=f"Video {index}", url=f"https://example.com/{index}")])
    snapshot = await repository.snapshot(topic.id, limit=2)
    assert len(snapshot.evidence) == 2
    assert snapshot.next_cursor
    next_page = await repository.snapshot(topic.id, limit=2, cursor=snapshot.next_cursor)
    assert len(next_page.evidence) == 1
    assert {item.id for item in snapshot.evidence}.isdisjoint(item.id for item in next_page.evidence)
