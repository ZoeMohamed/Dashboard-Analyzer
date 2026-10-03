from datetime import datetime, timedelta, timezone

from app.contracts import Analysis, AnalyzerName, Evidence, EvidenceMetrics, SourceName, TopicCreate
from app.database.repository import InMemoryRepository, evidence_key
from app.services.insights import InsightsService

NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


def _evidence(topic_id: str, source: SourceName, external_id: str, **fields) -> Evidence:
    return Evidence(source=source, topic_id=topic_id, external_id=external_id, url=f"https://example.com/{external_id}", **{"title": "x", **fields})


async def _seed():
    repository = InMemoryRepository()
    topic = await repository.create_topic(TopicCreate(name="Keripik Pisang"))
    tid = topic.id
    social = [
        _evidence(tid, SourceName.TIKTOK, "t1", text="enak", published_at=NOW - timedelta(days=1), metrics=EvidenceMetrics(views=100, likes=10)),
        _evidence(tid, SourceName.TIKTOK, "t2", text="mahal", published_at=NOW - timedelta(days=1), metrics=EvidenceMetrics(views=50)),
        _evidence(tid, SourceName.INSTAGRAM, "i1", text="ok", published_at=NOW - timedelta(days=40)),
    ]
    videos = [
        _evidence(tid, SourceName.YOUTUBE, "v1", published_at=NOW - timedelta(days=10), metadata={"content_type": "resep"}, metrics=EvidenceMetrics(views=1_000), collected_at=NOW - timedelta(hours=30)),
        _evidence(tid, SourceName.YOUTUBE, "v2", published_at=NOW - timedelta(days=45), metadata={"content_type": "review"}, metrics=EvidenceMetrics(views=9_000), collected_at=NOW),
    ]
    later = videos[0].model_copy(update={"metrics": EvidenceMetrics(views=1_600), "collected_at": NOW})
    market = [
        _evidence(tid, SourceName.SHOPEE, "s1", metrics=EvidenceMetrics(price=15_000, rating=4.5, sold=120)),
        _evidence(tid, SourceName.SHOPEE, "s2", metrics=EvidenceMetrics(price=25_000)),
    ]
    maps = [
        _evidence(tid, SourceName.MAPS, "p1", metadata={"type": "place"}, metrics=EvidenceMetrics(rating=4.2, review_count=80)),
        _evidence(tid, SourceName.MAPS, "r1", text="keripiknya enak", metadata={"type": "review"}, published_at=NOW - timedelta(days=2)),
    ]
    await repository.upsert_evidence([*social, *videos, *market, *maps])
    await repository.upsert_evidence([later])
    for item, label, aspects in [(social[0], "positif", ["rasa"]), (social[1], "negatif", ["harga"]), (maps[1], "positif", ["rasa"])]:
        await repository.upsert_analysis(Analysis(evidence_id=evidence_key(tid, item), label=label, score=0.5, confidence=0.6, aspects=aspects, analyzer=AnalyzerName.LOCAL_FALLBACK))
    return repository, tid


async def test_topic_insights_feed_every_chart() -> None:
    repository, topic_id = await _seed()
    insights = await InsightsService(repository).build(topic_id, days=7, now=NOW)

    assert insights.total_evidence == 9
    # Place rows are not opinions, so they are not counted as pending.
    assert insights.sentiment.model_dump() == {"positif": 2, "negatif": 1, "netral": 0, "pending": 5}
    assert len(insights.sentiment_daily) == 7
    yesterday = next(day for day in insights.sentiment_daily if day.day == (NOW - timedelta(days=1)).date())
    assert (yesterday.positif, yesterday.negatif) == (1, 1)
    assert [(item.aspect, item.count, item.positif) for item in insights.aspects] == [("rasa", 2, 2), ("harga", 1, 0)]

    tiktok = next(item for item in insights.sources if item.source == SourceName.TIKTOK)
    assert (tiktok.evidence_count, tiktok.engagement.views, tiktok.engagement.likes, tiktok.engagement.shares) == (2, 150, 10, None)

    youtube = insights.youtube
    assert (youtube.videos_tracked, youtube.new_videos_30d, youtube.new_videos_prev_30d) == (2, 1, 1)
    assert youtube.supply_change_pct == 0.0
    assert youtube.views_gain_24h == 600 and youtube.coverage == 0.5
    assert youtube.attention_index == 160.0  # 1,600 views over 10 days
    assert {item.content_type: item.count for item in youtube.content_mix} == {"resep": 1, "review": 1}
    assert len(youtube.weekly_new_videos) == 12 and sum(week.count for week in youtube.weekly_new_videos) == 2

    assert insights.marketplace.model_dump() == {"products": 2, "priced_products": 2, "price_min": 15_000, "price_max": 25_000, "average_rating": 4.5, "total_sold": 120}
    assert insights.maps.model_dump() == {"places": 1, "average_rating": 4.2, "total_reviews": 80, "product_opinions": 1}


async def test_source_filter_and_missing_metrics_stay_null() -> None:
    repository, topic_id = await _seed()
    insights = await InsightsService(repository).build(topic_id, source=SourceName.INSTAGRAM, days=7, now=NOW)
    assert insights.total_evidence == 1
    assert [item.source for item in insights.sources] == [SourceName.INSTAGRAM]
    assert insights.sources[0].engagement.views is None
    assert insights.youtube is None and insights.marketplace is None and insights.maps is None
