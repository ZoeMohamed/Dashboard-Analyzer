"""Shopee marketplace source adapter and payload parser for Dashboard Analyzer."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any

from .apify_client import ApifyError
from .base import CollectionResult, Evidence, EvidenceMetrics, SourceAdapter, Topic

logger = logging.getLogger(__name__)

ACTOR_ID = "xtracto~shopee-scraper"

SLANG: dict[str, str] = {
    "gk": "tidak",
    "ga": "tidak",
    "gak": "tidak",
    "nggak": "tidak",
    "ngga": "tidak",
    "enggak": "tidak",
    "tdk": "tidak",
    "yg": "yang",
    "bgt": "banget",
    "tp": "tapi",
    "krn": "karena",
    "udh": "sudah",
    "udah": "sudah",
    "sdh": "sudah",
    "blm": "belum",
    "bgs": "bagus",
    "dgn": "dengan",
    "jg": "juga",
    "aja": "saja",
    "emg": "memang",
    "hrg": "harga",
    "ongkir": "ongkos kirim",
}

_URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_MENTION_RE = re.compile(r"(?<!\w)@[\w.]+", re.UNICODE)
_REPEATED_RE = re.compile(r"([^\W\d_])\1{2,}", re.IGNORECASE | re.UNICODE)
_NON_LETTER_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def normalize(text: str) -> str:
    """Clean text and expand slang without stemming."""
    cleaned = _URL_RE.sub(" ", str(text or "").lower())
    cleaned = _MENTION_RE.sub(" ", cleaned).replace("#", "")
    cleaned = _REPEATED_RE.sub(r"\1", cleaned)
    words = _NON_LETTER_RE.findall(cleaned)
    return " ".join(SLANG.get(word, word) for word in words)


def _clean_str(val: Any) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def _clean_int(val: Any) -> int | None:
    if val is None or val == "":
        return None
    try:
        return max(0, int(float(val)))
    except (ValueError, TypeError):
        return None


def _clean_float(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _first(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def parse_price(val: Any) -> float | None:
    """Parse Indonesian price string into float without inventing numbers."""
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return max(0.0, float(val))

    raw = str(val).casefold().replace("rp", "").replace("idr", "").strip()
    multiplier = 1.0
    has_unit = False
    if raw.endswith("jt") or raw.endswith("juta"):
        multiplier = 1_000_000.0
        raw = raw.replace("juta", "").replace("jt", "").strip()
        has_unit = True
    elif raw.endswith("rb") or raw.endswith("ribu") or raw.endswith("k"):
        multiplier = 1_000.0
        raw = raw.replace("ribu", "").replace("rb", "").replace("k", "").strip()
        has_unit = True
    elif raw.endswith("m"):
        multiplier = 1_000_000.0
        raw = raw[:-1].strip()
        has_unit = True

    # Clean non-digit characters except separator
    raw = re.sub(r"[^\d.,]", "", raw)
    if not raw:
        return None

    if has_unit:
        raw = raw.replace(",", ".")
        try:
            return max(0.0, float(raw) * multiplier)
        except ValueError:
            return None

    # Full price without unit (e.g. "18.500" or "18,500.00")
    if "." in raw and "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "." in raw:
        parts = raw.split(".")
        if len(parts[-1]) == 3:
            raw = raw.replace(".", "")
        else:
            raw = raw.replace(".", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")

    try:
        return max(0.0, float(raw) * multiplier)
    except ValueError:
        return None


def parse_sold_count(val: Any) -> int | None:
    """Parse sold count string like '1.2rb', '10rb+', '850'."""
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return max(0, int(val))

    raw = str(val).casefold().replace("+", "").replace("terjual", "").strip()
    multiplier = 1
    has_multiplier = False
    if "rb" in raw or "k" in raw:
        multiplier = 1_000
        raw = raw.replace("rb", "").replace("k", "").strip()
        has_multiplier = True
    elif "jt" in raw:
        multiplier = 1_000_000
        raw = raw.replace("jt", "").strip()
        has_multiplier = True

    raw = re.sub(r"[^\d.,]", "", raw)
    if not raw:
        return None

    if has_multiplier:
        raw = raw.replace(",", ".")
        try:
            return max(0, int(float(raw) * multiplier))
        except (ValueError, TypeError):
            return None

    # Normal count without multiplier e.g. "1.250" or "850"
    raw = raw.replace(".", "").replace(",", "")
    try:
        return max(0, int(raw))
    except (ValueError, TypeError):
        return None


def _product_is_relevant(haystack: str, topic: Topic) -> bool:
    """Check if title/desc/category contains topic keywords/product terms and is not excluded."""
    norm_haystack = normalize(haystack)
    for excl in topic.exclude_terms:
        norm_excl = normalize(excl)
        if norm_excl and norm_excl in norm_haystack:
            return False

    signals = [normalize(s) for s in [topic.name, *topic.keywords, *topic.product_terms] if normalize(s)]
    return any(signal in norm_haystack for signal in signals)


def parse_shopee_item(item: dict[str, Any], topic: Topic, *, query: str = "") -> Evidence | None:
    """Parse a single Shopee marketplace item into Evidence with legacy ID aliases and metadata."""
    title = _clean_str(_first(item, "title", "name", "productName", "product_name", "itemName"))
    if not title:
        return None

    description = _clean_str(_first(item, "description", "desc", "productDescription"))
    category = _clean_str(_first(item, "category", "categoryName"))
    url = _clean_str(_first(item, "url", "productUrl", "product_url", "itemUrl", "link"))

    # Multi-field relevance check: title, description, and category
    haystack = " ".join(part for part in (title, description or "", category or "") if part)
    if not _product_is_relevant(haystack, topic):
        return None

    # Support all legacy ID aliases with fallback identity
    raw_id = _clean_str(_first(item, "id", "itemId", "item_id", "productId", "product_id"))
    if raw_id:
        external_id = raw_id
    else:
        external_id = hashlib.sha1((url or title).encode("utf-8")).hexdigest()[:24]

    shop = _first(item, "shopName", "shop_name", "sellerName", "shop", "seller", "shop_location")
    shop_name = _clean_str(shop.get("name") if isinstance(shop, dict) else shop)
    price = parse_price(_first(item, "price", "priceMin", "price_min", "rawPrice"))
    original_price = parse_price(_first(item, "originalPrice", "original_price", "priceMax", "price_max"))
    rating = _clean_float(_first(item, "rating", "ratingStar", "rating_star", "item_rating"))
    rating_count = _clean_int(_first(item, "ratingCount", "rating_count", "reviewCount", "review_count"))
    sold_count = parse_sold_count(_first(item, "sold", "soldCount", "sold_count", "historicalSold", "historical_sold"))
    stock = _clean_int(_first(item, "stock", "stockCount"))
    image_url = _clean_str(_first(item, "image", "imageUrl", "image_url", "thumbnail"))

    price_str = f"Rp {int(price):,}".replace(",", ".") if price is not None else "Harga tidak tertera"
    shop_str = f" di {shop_name}" if shop_name else ""
    text = f"{title}{shop_str}. Harga: {price_str}."

    metadata: dict[str, Any] = {
        "shop_name": shop_name,
        "price": price,
        "original_price": original_price,
        "rating": rating,
        "rating_count": rating_count,
        "sold_count": sold_count,
        "stock": stock,
        "image_url": image_url,
        "category": category,
        "description": description,
        "query": query,
    }

    return Evidence(
        id=f"shopee:{external_id}",
        source="shopee",
        topic_id=topic.id,
        external_id=external_id,
        title=title,
        text=text,
        url=url,
        published_at=datetime.now(timezone.utc),
        collected_at=datetime.now(timezone.utc),
        metrics=None,
        metadata=metadata,
    )


def parse_shopee_payload(
    items: list[dict[str, Any]], topic: Topic, limit: int = 50, *, query: str = ""
) -> list[Evidence]:
    """Parse list of raw Shopee items and return bounded Evidence list."""
    seen_ids: set[str] = set()
    results: list[Evidence] = []
    for item in items:
        evidence = parse_shopee_item(item, topic, query=query)
        if evidence and evidence.id not in seen_ids:
            seen_ids.add(evidence.id)
            results.append(evidence)
            if len(results) >= limit:
                break
    return results


def query_for(topic: Topic) -> str:
    """Determine query keyword using topic name, keywords, and product terms matching legacy."""
    values = [*topic.keywords, *topic.product_terms, topic.name]
    return next(
        (" ".join(str(val).split()).strip() for val in values if len(str(val).strip()) >= 2),
        topic.name,
    )


def build_shopee_input(topic: Topic, limit: int = 50) -> dict[str, Any]:
    """Build input dictionary for xtracto~shopee-scraper actor matching legacy semantics."""
    query = query_for(topic)
    return {
        "keyword": query,
        "limit": min(limit, 50),
        "country": "ID",
        "sortBy": "relevancy",
        "mode": "keyword",
        "fetchDetail": False,
        "delay": 0.5,
    }


class ShopeeAdapter:
    """Shopee adapter implementing SourceAdapter protocol."""

    name = "shopee"

    def __init__(self, apify_client: Any | None = None) -> None:
        self.apify_client = apify_client

    async def collect(self, topic: Topic, limit: int = 50) -> CollectionResult:
        if not self.apify_client:
            return CollectionResult(
                source="shopee",
                raw_count=0,
                items=[],
                error_code="not_configured",
                message="Apify client belum dikonfigurasi.",
            )

        actor_input = build_shopee_input(topic, limit)
        try:
            run_result = await self.apify_client.run_actor(
                ACTOR_ID, actor_input, timeout_seconds=120
            )
            raw_items = run_result.get("items", [])
            evidence_items = parse_shopee_payload(
                raw_items, topic, limit, query=actor_input.get("keyword", "")
            )
            return CollectionResult(
                source="shopee",
                raw_count=len(raw_items),
                items=evidence_items,
                provider_run_id=run_result.get("run_id"),
            )
        except ApifyError as exc:
            logger.error("Shopee collection failed (ApifyError): %s", exc.message)
            return CollectionResult(
                source="shopee",
                raw_count=0,
                items=[],
                error_code=exc.code,
                message=exc.message,
            )
        except Exception as exc:
            logger.error("Shopee collection failed: %s", exc)
            return CollectionResult(
                source="shopee",
                raw_count=0,
                items=[],
                error_code="provider_error",
                message=str(exc),
            )
