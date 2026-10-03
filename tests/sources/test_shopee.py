"""Test Shopee marketplace adapter and payload parsing."""

import asyncio
import json
from pathlib import Path
import pytest

from app.sources.apify_client import ApifyError
from app.sources.base import Topic
from app.sources.shopee import (
    ShopeeAdapter,
    build_shopee_input,
    parse_price,
    parse_shopee_item,
    parse_shopee_payload,
    parse_sold_count,
    query_for,
)


@pytest.fixture
def topic() -> Topic:
    return Topic(
        id="seblak-bandung",
        name="Seblak Bandung",
        keywords=["seblak"],
        product_terms=["seblak", "kerupuk"],
        exclude_terms=["baju", "kaos"],
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
    # Must match the xtracto~shopee-scraper input schema exactly; the actor
    # rejects unknown fields and uppercase country codes with HTTP 400.
    assert inp == {
        "mode": "keyword",
        "keyword": "seblak",
        "country": "id",
        "sort": "relevancy",
        "maxProducts": 20,
        "fetchDetail": False,
        "delay": 0.5,
    }


def test_shopee_adapter_not_configured(topic: Topic) -> None:
    adapter = ShopeeAdapter(apify_client=None)
    result = asyncio.run(adapter.collect(topic))
    assert result.error_code == "not_configured"


# ==================== GROUP D: SHOPEE REGRESSION TESTS ====================

def test_shopee_id_aliases(topic: Topic) -> None:
    """Rule 9: Support all legacy ID aliases (id, itemId, item_id, productId, product_id) and fallback."""
    aliases = [
        {"id": "id_101", "name": "Seblak Pedas 1"},
        {"itemId": "itemId_102", "productName": "Seblak Pedas 2"},
        {"item_id": "item_id_103", "title": "Seblak Pedas 3"},
        {"productId": "productId_104", "itemName": "Seblak Pedas 4"},
        {"product_id": "product_id_105", "product_name": "Seblak Pedas 5"},
    ]
    for item in aliases:
        ev = parse_shopee_item(item, topic)
        assert ev is not None
        assert ev.external_id in {"id_101", "itemId_102", "item_id_103", "productId_104", "product_id_105"}

    # Fallback hash if no ID alias is present
    fallback_item = {
        "title": "Seblak Instan Bandung Mantap",
        "url": "https://shopee.co.id/seblak-fallback-test",
    }
    ev_fallback = parse_shopee_item(fallback_item, topic)
    assert ev_fallback is not None
    assert len(ev_fallback.external_id) == 24


def test_shopee_multi_field_relevance(topic: Topic) -> None:
    """Rule 9: Relevance must check title, description, and category."""
    # 1. Product signal in description only
    item_desc = {
        "id": "rel_desc",
        "title": "Makanan Instan Khas Sunda",
        "description": "Seblak basah dengan topping lengkap",
    }
    assert parse_shopee_item(item_desc, topic) is not None

    # 2. Product signal in category only
    item_cat = {
        "id": "rel_cat",
        "title": "Makanan Tradisional Jawa Barat",
        "category": "Makanan / Cemilan / Seblak",
    }
    assert parse_shopee_item(item_cat, topic) is not None

    # 3. Excluded term in description -> rejected
    item_excl = {
        "id": "rel_excl",
        "title": "Seblak Enak",
        "description": "Free kaos dan baju untuk pembelian 10 pcs",
    }
    assert parse_shopee_item(item_excl, topic) is None


def test_shopee_preserves_original_price_and_stock(topic: Topic) -> None:
    """Rule 9: Preserve original_price, stock, image_url, and shop_name."""
    item = {
        "itemId": "full_meta_item",
        "title": "Seblak Pedas Komplit",
        "price": "15000",
        "originalPrice": "25000",
        "stock": 50,
        "shopName": "Dapur Seblak",
        "imageUrl": "https://shopee.co.id/img.jpg",
        "sold": "100",
        "rating": 4.8,
        "ratingCount": 40,
    }
    ev = parse_shopee_item(item, topic)
    assert ev is not None
    assert ev.metadata["price"] == 15000.0
    assert ev.metadata["original_price"] == 25000.0
    assert ev.metadata["stock"] == 50
    assert ev.metadata["shop_name"] == "Dapur Seblak"
    assert ev.metadata["image_url"] == "https://shopee.co.id/img.jpg"
    assert ev.metadata["sold_count"] == 100
    assert ev.metadata["rating"] == 4.8
    assert ev.metadata["rating_count"] == 40


def test_shopee_missing_optional_fields(topic: Topic) -> None:
    """Rule 9: Missing optional fields must not crash parser."""
    minimal_item = {
        "title": "Seblak Minimalis",
    }
    ev = parse_shopee_item(minimal_item, topic)
    assert ev is not None
    assert ev.metadata["price"] is None
    assert ev.metadata["original_price"] is None
    assert ev.metadata["stock"] is None
    assert ev.metadata["rating"] is None


def test_shopee_adapter_preserves_error_code(topic: Topic) -> None:
    """Rule 2: ShopeeAdapter must preserve original Apify error code."""
    class MockApifyClient:
        async def run_actor(self, *args, **kwargs):
            raise ApifyError("provider_permission", "Token access denied")

    adapter = ShopeeAdapter(apify_client=MockApifyClient())
    result = asyncio.run(adapter.collect(topic))
    assert result.error_code == "provider_permission"
    assert "Token access denied" in (result.message or "")


def test_shopee_titles_are_html_unescaped(topic: Topic) -> None:
    [item] = parse_shopee_payload([{"itemid": "1", "title": "Seblak Kering (ASIN &amp; GURIH)", "url": "https://shopee.co.id/x"}], topic)
    assert item.title == "Seblak Kering (ASIN & GURIH)"
