"""Test Instagram adapter and payload parsing."""

import asyncio
import json
from pathlib import Path
import pytest

from app.sources.apify_client import ApifyError
from app.sources.base import Topic
from app.sources.instagram import (
    InstagramAdapter,
    build_instagram_input,
    parse_instagram_item,
    parse_instagram_payload,
)


@pytest.fixture
def topic() -> Topic:
    return Topic(
        id="seblak-bandung",
        name="Seblak Bandung",
        keywords=["seblak prasmanan"],
        product_terms=["seblak"],
        cities=["Bandung"],
    )


@pytest.fixture
def instagram_fixture() -> list[dict]:
    path = Path(__file__).parent.parent / "fixtures" / "providers" / "instagram.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_parse_instagram_fixture(topic: Topic, instagram_fixture: list[dict]) -> None:
    items = parse_instagram_payload(instagram_fixture, topic)
    assert len(items) == 2

    first = items[0]
    assert first.id == "instagram:3198273645123456789"
    assert first.source == "instagram"
    assert "Pencinta seblak wajib mampir" in (first.text or "")
    assert first.url == "https://www.instagram.com/p/Cx12345ABCD/"
    assert first.metrics is not None
    assert first.metrics.views == 15000
    assert first.metrics.likes == 1250
    assert first.metrics.comments == 42

    second = items[1]
    assert second.id == "instagram:3198273645999999999"
    assert second.metrics is not None
    assert second.metrics.likes == 320
    assert second.metrics.views is None


def test_build_instagram_input(topic: Topic) -> None:
    inp = build_instagram_input(topic, limit=25)
    assert inp["resultsLimit"] == 25
    assert len(inp["directUrls"]) > 0
    assert "instagram.com/explore/tags/" in inp["directUrls"][0]
    assert inp["onlyPostsNewerThan"] == "30 days"
    assert inp["addParentData"] is True


def test_instagram_adapter_not_configured(topic: Topic) -> None:
    adapter = InstagramAdapter(apify_client=None)
    result = asyncio.run(adapter.collect(topic))
    assert result.error_code == "not_configured"


# ==================== GROUP E: INSTAGRAM REGRESSION TESTS ====================

def test_instagram_missing_text_skipped(topic: Topic) -> None:
    """Rule 10: Posts without text must be skipped. No fake title from owner username."""
    item_no_text = {
        "id": "ig_no_text",
        "owner": {"username": "kulinerbandung"},
        "caption": "",
    }
    assert parse_instagram_item(item_no_text, topic.id) is None

    item_none_text = {
        "id": "ig_none_text",
        "owner": {"username": "kulinerbandung"},
        "caption": None,
    }
    assert parse_instagram_item(item_none_text, topic.id) is None


def test_instagram_missing_owner(topic: Topic) -> None:
    """Rule 10: Valid caption with missing owner is parsed cleanly."""
    item = {
        "id": "ig_no_owner",
        "text": "Seblak prasmanan terlezat di Bandung",
    }
    ev = parse_instagram_item(item, topic.id)
    assert ev is not None
    assert ev.metadata["owner_username"] is None


def test_instagram_edge_likes_and_comments(topic: Topic) -> None:
    """Rule 10: Correctly extracts nested edge_liked_by and edge_media_to_comment."""
    item = {
        "id": "ig_nested_metrics",
        "caption": "Seblak bakar pertama di Bandung",
        "edge_liked_by": {"count": 789},
        "edge_media_to_comment": {"count": 34},
    }
    ev = parse_instagram_item(item, topic.id)
    assert ev is not None
    assert ev.metrics is not None
    assert ev.metrics.likes == 789
    assert ev.metrics.comments == 34


def test_instagram_shortcode_url_fallback(topic: Topic) -> None:
    """Rule 10: Shortcode constructs canonical Instagram URL."""
    item = {
        "id": "ig_sc_123",
        "shortcode": "Cxyz9876",
        "caption": "Seblak pedas mantap",
    }
    ev = parse_instagram_item(item, topic.id)
    assert ev is not None
    assert ev.url == "https://www.instagram.com/p/Cxyz9876/"


def test_instagram_adapter_preserves_error_code(topic: Topic) -> None:
    """Rule 2: InstagramAdapter must preserve original Apify error code."""
    class MockApifyClient:
        async def run_actor(self, *args, **kwargs):
            raise ApifyError("provider_permission", "Token invalid")

    adapter = InstagramAdapter(apify_client=MockApifyClient())
    result = asyncio.run(adapter.collect(topic))
    assert result.error_code == "provider_permission"
    assert "Token invalid" in (result.message or "")
