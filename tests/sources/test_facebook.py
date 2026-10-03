"""Test Facebook adapter and payload parsing."""

import asyncio
import json
from pathlib import Path
import pytest

from app.sources.apify_client import ApifyError
from app.sources.base import Topic
from app.sources.facebook import (
    FacebookAdapter,
    build_facebook_input,
    parse_facebook_item,
    parse_facebook_payload,
)


@pytest.fixture
def topic() -> Topic:
    return Topic(
        id="seblak-bandung",
        name="Seblak Bandung",
        keywords=["seblak bandung"],
        product_terms=["seblak"],
        cities=["Bandung"],
    )


@pytest.fixture
def facebook_fixture() -> list[dict]:
    path = Path(__file__).parent.parent / "fixtures" / "providers" / "facebook.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_parse_facebook_fixture(topic: Topic, facebook_fixture: list[dict]) -> None:
    items = parse_facebook_payload(facebook_fixture, topic)
    assert len(items) == 2

    first = items[0]
    assert first.id == "facebook:fb_post_1001"
    assert first.source == "facebook"
    assert "Rekomendasi warung seblak" in (first.text or "")
    assert first.metrics is not None
    assert first.metrics.likes == 210
    assert first.metrics.comments == 45
    assert first.metrics.shares == 18

    second = items[1]
    assert second.id == "facebook:fb_post_1002"
    assert second.metrics is not None
    assert second.metrics.likes == 88
    assert second.metrics.comments is None


def test_build_facebook_input(topic: Topic) -> None:
    inp = build_facebook_input(topic, limit=20)
    assert inp["resultsLimit"] == 20
    assert inp["searchType"] == "posts"
    assert inp["locations"] == ["Bandung"]


def test_facebook_adapter_not_configured(topic: Topic) -> None:
    adapter = FacebookAdapter(apify_client=None)
    result = asyncio.run(adapter.collect(topic))
    assert result.error_code == "not_configured"


# ==================== GROUP E: FACEBOOK REGRESSION TESTS ====================

def test_facebook_missing_text_skipped(topic: Topic) -> None:
    """Rule 10: Posts without text must be skipped. No fake title from author/page."""
    item_no_text = {
        "id": "fb_no_text",
        "authorName": "Komunitas Kuliner",
        "text": "",
    }
    assert parse_facebook_item(item_no_text, topic.id) is None

    item_none_text = {
        "id": "fb_none_text",
        "authorName": "Komunitas Kuliner",
        "text": None,
    }
    assert parse_facebook_item(item_none_text, topic.id) is None


def test_facebook_id_aliases(topic: Topic) -> None:
    """Rule 10: Support postId, post_id, id, and legacyId aliases."""
    for key in ("postId", "post_id", "id", "legacyId"):
        item = {
            key: f"fb_key_{key}",
            "text": "Info seblak enak di Bandung",
        }
        ev = parse_facebook_item(item, topic.id)
        assert ev is not None
        assert ev.external_id == f"fb_key_{key}"


def test_facebook_missing_metrics(topic: Topic) -> None:
    """Rule 10: Missing metrics should remain None."""
    item = {
        "postId": "fb_meta_1",
        "text": "Resep seblak ceker pedas",
    }
    ev = parse_facebook_item(item, topic.id)
    assert ev is not None
    assert ev.metrics is None


def test_facebook_adapter_preserves_error_code(topic: Topic) -> None:
    """Rule 2: FacebookAdapter must preserve original Apify error code."""
    class MockApifyClient:
        async def run_actor(self, *args, **kwargs):
            raise ApifyError("invalid_payload", "Input invalid")

    adapter = FacebookAdapter(apify_client=MockApifyClient())
    result = asyncio.run(adapter.collect(topic))
    assert result.error_code == "invalid_payload"
    assert "Input invalid" in (result.message or "")
