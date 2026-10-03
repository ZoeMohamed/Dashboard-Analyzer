"""Test TikTok adapter and payload parsing."""

import asyncio
import json
from pathlib import Path
import pytest

from app.sources.apify_client import ApifyError
from app.sources.base import Topic
from app.sources.tiktok import (
    TikTokAdapter,
    build_tiktok_input,
    parse_tiktok_item,
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


def test_tiktok_adapter_not_configured(topic: Topic) -> None:
    adapter = TikTokAdapter(apify_client=None)
    result = asyncio.run(adapter.collect(topic))
    assert result.error_code == "not_configured"
    assert result.items == []


# ==================== GROUP E: TIKTOK REGRESSION TESTS ====================

def test_tiktok_missing_text_skipped(topic: Topic) -> None:
    """Rule 10: Items with missing or empty text MUST be skipped. No fake titles from author."""
    item_no_text = {
        "id": "tt_no_text",
        "authorMeta": {"name": "Influencer Hebat", "uniqueId": "influencer123"},
        "text": "",
    }
    assert parse_tiktok_item(item_no_text, topic.id) is None

    item_none_text = {
        "id": "tt_none_text",
        "authorMeta": {"name": "Influencer Hebat", "uniqueId": "influencer123"},
        "text": None,
    }
    assert parse_tiktok_item(item_none_text, topic.id) is None


def test_tiktok_missing_author(topic: Topic) -> None:
    """Rule 10: Missing author should not cause error when text is valid."""
    item = {
        "id": "tt_no_author",
        "text": "Seblak prasmanan murah meriah",
    }
    ev = parse_tiktok_item(item, topic.id)
    assert ev is not None
    assert ev.external_id == "tt_no_author"
    assert ev.metadata["author_name"] is None


def test_tiktok_missing_metrics(topic: Topic) -> None:
    """Rule 10: Missing metrics should remain None, no fabricated 0s."""
    item = {
        "id": "tt_no_metrics",
        "text": "Seblak enak banget",
    }
    ev = parse_tiktok_item(item, topic.id)
    assert ev is not None
    assert ev.metrics is None


def test_tiktok_missing_timestamp(topic: Topic) -> None:
    """Rule 10: Missing timestamp handled without crashing."""
    item = {
        "id": "tt_no_time",
        "text": "Seblak enak banget",
    }
    ev = parse_tiktok_item(item, topic.id)
    assert ev is not None
    assert ev.published_at is not None


def test_tiktok_stable_external_id_and_url(topic: Topic) -> None:
    """Rule 10: Stable external ID and normalized video URL."""
    item = {
        "videoId": "888877776666",
        "text": "Resep seblak ceker",
        "authorMeta": {"uniqueId": "chefindo"},
    }
    ev = parse_tiktok_item(item, topic.id)
    assert ev is not None
    assert ev.external_id == "888877776666"
    assert ev.id == "tiktok:888877776666"
    assert ev.url == "https://www.tiktok.com/@chefindo/video/888877776666"


def test_tiktok_adapter_preserves_error_code(topic: Topic) -> None:
    """Rule 2: TikTokAdapter must preserve original Apify error code."""
    class MockApifyClient:
        async def run_actor(self, *args, **kwargs):
            raise ApifyError("provider_timeout", "Actor timed out")

    adapter = TikTokAdapter(apify_client=MockApifyClient())
    result = asyncio.run(adapter.collect(topic))
    assert result.error_code == "provider_timeout"
    assert "Actor timed out" in (result.message or "")
