from datetime import datetime, timezone

import pytest

from app.contracts import Evidence, SourceName, TopicCreate


def test_topic_derives_terms_and_deduplicates_keywords() -> None:
    topic = TopicCreate(name="  Cappuccino   Cincau ", keywords=["cincau", "Cincau", " cappuccino "])
    assert topic.name == "Cappuccino Cincau"
    assert topic.keywords == ["cincau", "cappuccino"]
    assert topic.product_terms == ["cappuccino", "cincau"]


def test_evidence_requires_http_url_and_content() -> None:
    with pytest.raises(ValueError):
        Evidence(source=SourceName.TIKTOK, topic_id="kopi", external_id="1", url="not-a-url")

    evidence = Evidence(source=SourceName.TIKTOK, topic_id="kopi", external_id="1", text="Enak", url="https://example.com/1", published_at=datetime(2026, 1, 1))
    assert evidence.id == "tiktok:1"
    assert evidence.published_at.tzinfo == timezone.utc
