"""Test Google Maps adapter and payload parsing."""

import json
from pathlib import Path
import pytest

from app.sources.base import Topic
from app.sources.maps import (
    MapsAdapter,
    build_maps_input,
    parse_maps_payload,
)


@pytest.fixture
def topic() -> Topic:
    return Topic(
        id="seblak-bandung",
        name="Seblak Bandung",
        keywords=["seblak"],
        product_terms=["seblak"],
        cities=["Bandung"],
    )


@pytest.fixture
def maps_fixture() -> list[dict]:
    path = Path(__file__).parent.parent / "fixtures" / "providers" / "maps.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_parse_maps_fixture(topic: Topic, maps_fixture: list[dict]) -> None:
    items = parse_maps_payload(maps_fixture, topic)

    # 1 place evidence + 2 relevant reviews for place 1, and 1 place evidence for place 2 = 4
    assert len(items) == 4

    place_item = items[0]
    assert place_item.id == "maps:ChIJN1t_tDeuEmsRUsoyG83frY4"
    assert place_item.title == "Seblak Prasmanan Juara"
    assert place_item.metadata["type"] == "place"
    assert place_item.metadata["rating"] == 4.8

    # First relevant review
    rev1 = items[1]
    assert rev1.id == "maps:rev_001"
    assert rev1.metadata["type"] == "review"
    assert rev1.metadata["stars"] == 5
    assert "Seblaknya enak banget" in (rev1.text or "")

    # Second relevant review
    rev2 = items[2]
    assert rev2.id == "maps:rev_002"
    assert "seblak prasmanan memuaskan" in (rev2.text or "")

    # Verify irrelevant review (rev_003: 'Toilet bersih...') is excluded!
    rev_texts = [it.text for it in items]
    assert not any("Toilet bersih" in (t or "") for t in rev_texts)


def test_build_maps_input(topic: Topic) -> None:
    inp = build_maps_input(topic, limit=10)
    assert inp["language"] == "id"
    assert "seblak Bandung" in inp["searchStringsArray"]


import asyncio

def test_maps_adapter_not_configured(topic: Topic) -> None:
    adapter = MapsAdapter(apify_client=None)
    result = asyncio.run(adapter.collect(topic))
    assert result.error_code == "not_configured"
