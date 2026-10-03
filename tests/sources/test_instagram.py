"""Test Instagram adapter and payload parsing."""

import json
from pathlib import Path
import pytest

from app.sources.base import Topic
from app.sources.instagram import (
    InstagramAdapter,
    build_instagram_input,
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


import asyncio

def test_instagram_adapter_not_configured(topic: Topic) -> None:
    adapter = InstagramAdapter(apify_client=None)
    result = asyncio.run(adapter.collect(topic))
    assert result.error_code == "not_configured"
