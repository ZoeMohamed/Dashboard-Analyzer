"""Test Shopee marketplace adapter and payload parsing."""

import json
from pathlib import Path
import pytest

from app.sources.base import Topic
from app.sources.shopee import (
    ShopeeAdapter,
    build_shopee_input,
    parse_price,
    parse_shopee_payload,
    parse_sold_count,
)


@pytest.fixture
def topic() -> Topic:
    return Topic(
        id="seblak-bandung",
        name="Seblak Bandung",
        keywords=["seblak"],
        product_terms=["seblak", "kerupuk"],
        cities=["Bandung"],
    )


@pytest.fixture
def shopee_fixture() -> list[dict]:
    path = Path(__file__).parent.parent / "fixtures" / "providers" / "shopee.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_parse_price_and_sold_count() -> None:
    assert parse_price("Rp 18.500") == 18500.0
    assert parse_price("15k") == 15000.0
    assert parse_price("1.2jt") == 1200000.0
    assert parse_price(None) is None
    assert parse_price("") is None

    assert parse_sold_count("10rb+") == 10000
    assert parse_sold_count("1.2rb terjual") == 1200
    assert parse_sold_count("850") == 850
    assert parse_sold_count(None) is None


def test_parse_shopee_fixture(topic: Topic, shopee_fixture: list[dict]) -> None:
    items = parse_shopee_payload(shopee_fixture, topic)

    # Item 3 is 'Casing HP Motif Bunga' which is irrelevant and must be filtered out
    assert len(items) == 2

    first = items[0]
    assert first.id == "shopee:1928374650"
    assert first.source == "shopee"
    assert first.metadata["price"] == 18500.0
    assert first.metadata["sold_count"] == 10000
    assert first.metadata["rating"] == 4.9

    second = items[1]
    assert second.id == "shopee:1928374651"
    assert second.metadata["price"] == 12000.0
    assert second.metadata["sold_count"] == 850


def test_build_shopee_input(topic: Topic) -> None:
    inp = build_shopee_input(topic, limit=20)
    assert inp["country"] == "ID"
    assert inp["keyword"] == "seblak"
    assert inp["limit"] == 20


import asyncio

def test_shopee_adapter_not_configured(topic: Topic) -> None:
    adapter = ShopeeAdapter(apify_client=None)
    result = asyncio.run(adapter.collect(topic))
    assert result.error_code == "not_configured"
