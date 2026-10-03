"""Test Facebook adapter and payload parsing."""

import json
from pathlib import Path
import pytest

from app.sources.base import Topic
from app.sources.facebook import (
    FacebookAdapter,
    build_facebook_input,
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


import asyncio

def test_facebook_adapter_not_configured(topic: Topic) -> None:
    adapter = FacebookAdapter(apify_client=None)
    result = asyncio.run(adapter.collect(topic))
    assert result.error_code == "not_configured"
