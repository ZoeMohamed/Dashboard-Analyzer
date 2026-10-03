"""Test YouTube adapter and payload parsing."""

import json
from pathlib import Path
import pytest

from app.sources.base import Topic
from app.sources.youtube import (
    YouTubeAdapter,
    parse_youtube_payload,
)


@pytest.fixture
def topic() -> Topic:
    return Topic(
        id="seblak-bandung",
        name="Seblak Bandung",
        keywords=["seblak"],
        product_terms=["seblak"],
        exclude_terms=["kartun", "animasi"],
        cities=["Bandung"],
    )


@pytest.fixture
def youtube_fixture() -> list[dict]:
    path = Path(__file__).parent.parent / "fixtures" / "providers" / "youtube.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_parse_youtube_fixture(topic: Topic, youtube_fixture: list[dict]) -> None:
    items = parse_youtube_payload(youtube_fixture, topic)

    # Item 3 is 'Kartun Animasi Anak' which must be filtered out!
    assert len(items) == 2

    first = items[0]
    assert first.id == "youtube:abc123XYZ"
    assert first.source == "youtube"
    assert "RESEP SEBLAK" in (first.title or "")
    assert first.metrics is not None
    assert first.metrics.views == 125000
    assert first.metrics.likes == 4300
    assert first.metrics.comments == 210
    assert first.metadata.get("views_per_day") is not None

    second = items[1]
    assert second.id == "youtube:def456UVW"
    assert "Review Seblak" in (second.title or "")
    assert second.metrics is not None
    assert second.metrics.views == 45000
    assert second.metrics.comments is None  # Missing in statistics, stays None


import asyncio

def test_youtube_adapter_not_configured(topic: Topic) -> None:
    adapter = YouTubeAdapter(client=None)
    result = asyncio.run(adapter.collect(topic))
    assert result.error_code == "not_configured"
