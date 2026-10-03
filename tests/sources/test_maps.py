"""Test Google Maps adapter and payload parsing."""

import asyncio
import json
from pathlib import Path
import pytest

from app.sources.apify_client import ApifyError
from app.sources.base import Topic
from app.sources.maps import (
    MapsAdapter,
    build_maps_input,
    parse_maps_payload,
    parse_maps_place_items,
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

    # 1 place evidence + 2 relevant reviews for place 1.
    # Place 2 ('Toko Buku Berkah') has no relevance to seblak (neither name nor review hit) -> rejected!
    assert len(items) == 3
    assert not any(it.title == "Toko Buku Berkah" for it in items)

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


def test_maps_irrelevant_place_is_rejected(topic: Topic) -> None:
    """Section 16: Place with no name hit and no review hit must produce 0 items."""
    irrelevant_place = {
        "placeId": "place_padang",
        "title": "Warung Nasi Padang",
        "address": "Jl. Sudirman No. 10",
        "reviews": [
            {"reviewId": "rev_padang_1", "text": "Toilet bersih dan rapi"},
            {"reviewId": "rev_padang_2", "text": "Pelayanan cepat dan ramah"},
        ],
    }
    items = parse_maps_place_items(irrelevant_place, topic)
    assert items == []


def test_build_maps_input(topic: Topic) -> None:
    inp = build_maps_input(topic, limit=10)
    assert inp["language"] == "id"
    assert inp["locationQuery"] == "Bandung"
    assert inp["reviewsSort"] == "newest"
    assert inp["reviewsOrigin"] == "google"
    assert inp["scrapePlaceDetailPage"] is True
    assert inp["skipClosedPlaces"] is True
    assert inp["scrapeReviewsPersonalData"] is False
    assert inp["maxCrawledPlacesPerSearch"] == 3
    assert "seblak Bandung" in inp["searchStringsArray"]


def test_maps_adapter_not_configured(topic: Topic) -> None:
    adapter = MapsAdapter(apify_client=None)
    result = asyncio.run(adapter.collect(topic))
    assert result.error_code == "not_configured"


# ==================== GROUP C: MAPS REGRESSION TESTS ====================

def test_maps_no_views_contamination(topic: Topic, maps_fixture: list[dict]) -> None:
    """Rule 8: Review count must NOT be stored as views metrics. Stored in metadata."""
    items = parse_maps_payload(maps_fixture, topic)
    place_item = items[0]

    # Metrics views must be None (no fake metrics!)
    if place_item.metrics is not None:
        assert place_item.metrics.views is None

    # review_count preserved in metadata
    assert place_item.metadata["review_count"] == 350
    assert place_item.metadata["rating"] == 4.8


def test_maps_review_url_preferred(topic: Topic) -> None:
    """Rule 8: If review has reviewUrl, use it over place URL."""
    place_data = {
        "placeId": "place_url_test",
        "title": "Kedai Seblak Juara",
        "url": "https://maps.google.com/place_url",
        "reviews": [
            {
                "reviewId": "rev_specific_url",
                "text": "Seblaknya pedas mantap",
                "reviewUrl": "https://maps.google.com/review_specific_url",
            }
        ],
    }
    items = parse_maps_place_items(place_data, topic)
    assert len(items) == 2
    rev_item = items[1]
    assert rev_item.url == "https://maps.google.com/review_specific_url"


def test_maps_author_and_stars_preserved(topic: Topic) -> None:
    """Rule 8: Preserve author name, author url, and stars."""
    place_data = {
        "placeId": "place_author_test",
        "title": "Warung Seblak",
        "reviews": [
            {
                "reviewId": "rev_author_test",
                "text": "Seblak komplit porsi banyak",
                "stars": 4,
                "name": "Budi Santoso",
                "reviewerUrl": "https://maps.google.com/reviewer/budi",
            }
        ],
    }
    items = parse_maps_place_items(place_data, topic)
    assert len(items) == 2
    rev = items[1]
    assert rev.metadata["author_name"] == "Budi Santoso"
    assert rev.metadata["author_uri"] == "https://maps.google.com/reviewer/budi"
    assert rev.metadata["stars"] == 4


def test_maps_closed_place_excluded(topic: Topic) -> None:
    """Rule 8: Closed places must be excluded."""
    closed_place = {
        "placeId": "place_closed",
        "title": "Seblak Enak",
        "businessStatus": "CLOSED_PERMANENTLY",
        "reviews": [{"reviewId": "r1", "text": "Seblak enak banget"}],
    }
    items = parse_maps_place_items(closed_place, topic)
    assert len(items) == 0

    closed_place_2 = {
        "placeId": "place_closed_2",
        "title": "Seblak Enak 2",
        "businessStatus": "CLOSED",
        "reviews": [{"reviewId": "r2", "text": "Seblak enak banget"}],
    }
    assert len(parse_maps_place_items(closed_place_2, topic)) == 0


def test_maps_clitic_phrase_matching(topic: Topic) -> None:
    """Rule 8: Match Indonesian clitics 'seblaknya', 'seblakku'."""
    place = {
        "placeId": "p_clitic",
        "title": "Kedai Makanan",
        "reviews": [
            {"reviewId": "r_clitic_1", "text": "Rasa seblaknya juara"},
            {"reviewId": "r_clitic_2", "text": "Porsi seblakku melimpah"},
        ],
    }
    items = parse_maps_place_items(place, topic)
    # 1 place summary + 2 reviews
    assert len(items) == 3


def test_maps_adapter_preserves_error_code(topic: Topic) -> None:
    """Rule 2: Adapter must preserve original Apify error code."""
    class MockApifyClient:
        async def run_actor(self, *args, **kwargs):
            raise ApifyError("budget_exhausted", "Token limit reached")

    adapter = MapsAdapter(apify_client=MockApifyClient())
    result = asyncio.run(adapter.collect(topic))
    assert result.error_code == "budget_exhausted"
    assert "Token limit reached" in (result.message or "")
