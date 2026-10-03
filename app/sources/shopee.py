"""Shopee marketplace source adapter and payload parser for Dashboard Analyzer."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from .base import CollectionResult, Evidence, EvidenceMetrics, SourceAdapter, Topic

logger = logging.getLogger(__name__)

ACTOR_ID = "xtracto~shopee-scraper"


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

    # Clean non-digit characters except separator
    raw = re.sub(r"[^\d.,]", "", raw)
    if not raw:
        return None

    if has_unit:
        # e.g. "1.2" or "1,2" -> 1.2
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


def _product_is_relevant(title: str, topic: Topic) -> bool:
    """Check if title contains topic keywords/product terms and is not excluded."""
    t = title.casefold()
    for excl in topic.exclude_terms:
        if excl.strip() and excl.casefold() in t:
            return False

    signals = [topic.name, *topic.keywords, *topic.product_terms]
    return any(signal.casefold() in t for signal in signals if signal.strip())


def parse_shopee_item(item: dict[str, Any], topic: Topic) -> Evidence | None:
    """Parse a single Shopee marketplace item into Evidence."""
    external_id = _clean_str(item.get("itemId") or item.get("id") or item.get("item_id"))
    title = _clean_str(item.get("title") or item.get("name"))
    if not external_id or not title:
        return None

    # Check relevance
    if not _product_is_relevant(title, topic):
        return None

    shop_name = _clean_str(item.get("shopName") or item.get("shop_name") or item.get("shop_location"))
    url = _clean_str(item.get("url") or item.get("item_url"))
    price = parse_price(item.get("price") or item.get("rawPrice"))
    rating = _clean_float(item.get("rating") or item.get("item_rating"))
    rating_count = _clean_int(item.get("ratingCount") or item.get("rating_count"))
    sold_count = parse_sold_count(item.get("sold") or item.get("historical_sold") or item.get("sold_count"))

    price_str = f"Rp {int(price):,}".replace(",", ".") if price is not None else "Harga tidak tertera"
    shop_str = f" di {shop_name}" if shop_name else ""
    text = f"{title}{shop_str}. Harga: {price_str}."

    has_metrics = sold_count is not None
    metrics = EvidenceMetrics(views=sold_count) if has_metrics else None

    metadata: dict[str, Any] = {
        "shop_name": shop_name,
        "price": price,
        "rating": rating,
        "rating_count": rating_count,
        "sold_count": sold_count,
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
        metrics=metrics,
        metadata=metadata,
    )


def parse_shopee_payload(
    items: list[dict[str, Any]], topic: Topic, limit: int = 50
) -> list[Evidence]:
    """Parse list of raw Shopee items and return bounded Evidence list."""
    seen_ids: set[str] = set()
    results: list[Evidence] = []
    for item in items:
        evidence = parse_shopee_item(item, topic)
        if evidence and evidence.id not in seen_ids:
            seen_ids.add(evidence.id)
            results.append(evidence)
            if len(results) >= limit:
                break
    return results


def build_shopee_input(topic: Topic, limit: int = 50) -> dict[str, Any]:
    """Build input dictionary for xtracto~shopee-scraper actor."""
    query = topic.keywords[0] if topic.keywords else topic.name
    return {
        "keyword": query,
        "limit": min(limit, 50),
        "country": "ID",
        "sortBy": "relevancy",
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
            evidence_items = parse_shopee_payload(raw_items, topic, limit)
            return CollectionResult(
                source="shopee",
                raw_count=len(raw_items),
                items=evidence_items,
                provider_run_id=run_result.get("run_id"),
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
