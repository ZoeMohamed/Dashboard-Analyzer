"""Test TikTok adapter and payload parsing."""

import json
from pathlib import Path
import pytest

from app.sources.base import Topic
from app.sources.tiktok import (
    TikTokAdapter,
    build_tiktok_input,
    parse_tiktok_payload,
)


@pytest.fixture
def topic() -> Topic:
    return Topic(
        id="seblak-bandung",
        name="Seblak Bandung",
        keywords=["seblak prasmanan", "seblak pedas"],
        product_terms=["seblak", "ceker"],
        cities=["Bandung"],
    )


@pytest.fixture
def tiktok_fixture() -> list[dict]:
    path = Path(__file__).parent.parent / "fixtures" / "providers" / "tiktok.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_parse_tiktok_fixture(topic: Topic, tiktok_fixture: list[dict]) -> None:
    items = parse_tiktok_payload(tiktok_fixture, topic)
    assert len(items) == 2

    first = items[0]
    assert first.id == "tiktok:7198273645123456789"
    assert first.source == "tiktok"
    assert first.topic_id == "seblak-bandung"
    assert "seblak prasmanan viral" in (first.text or "")
    assert first.metrics is not None
    assert first.metrics.views == 45000
    assert first.metrics.likes == 3200
    assert first.metrics.comments == 180
    assert first.metrics.shares == 95

    second = items[1]
    assert second.id == "tiktok:7198273645999999999"
    assert second.metrics is not None
    assert second.metrics.views == 12000
    assert second.metrics.likes == 850
    assert second.metrics.comments is None  # Missing in fixture, remains None


def test_build_tiktok_input(topic: Topic) -> None:
    inp = build_tiktok_input(topic, limit=30)
    assert inp["resultsPerPage"] == 30
    assert "seblak prasmanan" in inp["searchQueries"]
    assert inp["commentsPerPost"] == 0
    assert inp["shouldDownloadVideos"] is False


import asyncio

def test_tiktok_adapter_not_configured(topic: Topic) -> None:
    adapter = TikTokAdapter(apify_client=None)
    result = asyncio.run(adapter.collect(topic))
    assert result.error_code == "not_configured"
    assert result.items == []
