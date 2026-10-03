"""Google Maps source adapter and payload parser for Dashboard Analyzer."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .base import CollectionResult, Evidence, EvidenceMetrics, SourceAdapter, Topic

logger = logging.getLogger(__name__)

ACTOR_ID = "compass~crawler-google-places"


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


def _parse_datetime(val: Any, fallback: datetime | None = None) -> datetime:
    if isinstance(val, datetime):
        dt = val
    elif isinstance(val, (int, float)):
        ts = val / 1000 if val > 1e11 else val
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    elif isinstance(val, str) and val.strip():
        try:
            dt = datetime.fromisoformat(val.strip().replace("Z", "+00:00"))
        except ValueError:
            try:
                dt = datetime.strptime(val.strip()[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                dt = fallback or datetime.now(timezone.utc)
    else:
        dt = fallback or datetime.now(timezone.utc)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _review_mentions_product(text: str, topic: Topic) -> bool:
    """Check whether a review text contains topic keywords or product terms."""
    haystack = text.casefold()
    signals = [topic.name, *topic.keywords, *topic.product_terms]
    return any(signal.casefold() in haystack for signal in signals if signal.strip())


def parse_maps_place_items(
    place: dict[str, Any], topic: Topic, limit: int = 50
) -> list[Evidence]:
    """Parse a Google Maps place item into place and review Evidence items."""
    results: list[Evidence] = []
    place_id = _clean_str(place.get("placeId") or place.get("id"))
    if not place_id:
        return results

    place_name = _clean_str(place.get("title") or place.get("name")) or "Tempat Google Maps"
    place_address = _clean_str(place.get("address") or place.get("formattedAddress"))
    place_url = _clean_str(place.get("url") or place.get("googleUrl"))
    rating = _clean_float(place.get("totalScore") or place.get("rating"))
    review_count = _clean_int(place.get("reviewsCount") or place.get("userRatingCount"))

    # 1. Place Summary Evidence
    place_evidence = Evidence(
        id=f"maps:{place_id}",
        source="maps",
        topic_id=topic.id,
        external_id=place_id,
        title=place_name,
        text=place_address or f"Tempat terdaftar di Google Maps: {place_name}",
        url=place_url,
        published_at=datetime.now(timezone.utc),
        collected_at=datetime.now(timezone.utc),
        metrics=EvidenceMetrics(views=review_count),
        metadata={
            "type": "place",
            "rating": rating,
            "review_count": review_count,
            "address": place_address,
        },
    )
    results.append(place_evidence)

    # 2. Extract specific reviews that mention the product
    raw_reviews = place.get("reviews") or []
    if isinstance(raw_reviews, list):
        for idx, rev in enumerate(raw_reviews):
            if len(results) >= limit:
                break
            if not isinstance(rev, dict):
                continue

            rev_text = _clean_str(rev.get("text") or rev.get("reviewText"))
            if not rev_text:
                continue

            # In accordance with docs/SYSTEM.md: only include reviews that mention the product
            if not _review_mentions_product(rev_text, topic):
                continue

            rev_id = _clean_str(rev.get("reviewId") or rev.get("id")) or f"{place_id}_rev_{idx}"
            author_name = _clean_str(rev.get("name") or rev.get("authorName")) or "Pengulas Google"
            stars = _clean_int(rev.get("stars") or rev.get("rating"))
            published_raw = rev.get("publishedAtDate") or rev.get("publishAt") or rev.get("date")

            rev_evidence = Evidence(
                id=f"maps:{rev_id}",
                source="maps",
                topic_id=topic.id,
                external_id=rev_id,
                title=f"{place_name} — Ulasan oleh {author_name}",
                text=rev_text,
                url=place_url,
                published_at=_parse_datetime(published_raw),
                collected_at=datetime.now(timezone.utc),
                metadata={
                    "type": "review",
                    "place_id": place_id,
                    "place_name": place_name,
                    "author": author_name,
                    "stars": stars,
                },
            )
            results.append(rev_evidence)

    return results


def parse_maps_payload(
    places: list[dict[str, Any]], topic: Topic, limit: int = 50
) -> list[Evidence]:
    """Parse list of raw Google Maps places and return bounded Evidence list."""
    seen_ids: set[str] = set()
    results: list[Evidence] = []
    for place in places:
        items = parse_maps_place_items(place, topic, limit)
        for evidence in items:
            if evidence.id not in seen_ids:
                seen_ids.add(evidence.id)
                results.append(evidence)
                if len(results) >= limit:
                    return results
    return results


def build_maps_input(topic: Topic, limit: int = 50) -> dict[str, Any]:
    """Build input dictionary for compass~crawler-google-places actor."""
    city = topic.cities[0] if topic.cities else "Indonesia"
    queries = [f"{q} {city}" for q in topic.keywords] if topic.keywords else [f"{topic.name} {city}"]
    return {
        "searchStringsArray": queries[:2],
        "locationQuery": city,
        "maxCrawledPlacesPerSearch": min(limit, 20),
        "maxReviews": 10,
        "reviewsSort": "newest",
        "reviewsOrigin": "google",
        "language": "id",
        "scrapeReviewerName": True,
    }


class MapsAdapter:
    """Google Maps adapter implementing SourceAdapter protocol."""

    name = "maps"

    def __init__(self, apify_client: Any | None = None) -> None:
        self.apify_client = apify_client

    async def collect(self, topic: Topic, limit: int = 50) -> CollectionResult:
        if not self.apify_client:
            return CollectionResult(
                source="maps",
                raw_count=0,
                items=[],
                error_code="not_configured",
                message="Apify client belum dikonfigurasi.",
            )

        actor_input = build_maps_input(topic, limit)
        try:
            run_result = await self.apify_client.run_actor(
                ACTOR_ID, actor_input, timeout_seconds=120
            )
            raw_items = run_result.get("items", [])
            evidence_items = parse_maps_payload(raw_items, topic, limit)
            return CollectionResult(
                source="maps",
                raw_count=len(raw_items),
                items=evidence_items,
                provider_run_id=run_result.get("run_id"),
            )
        except Exception as exc:
            logger.error("Maps collection failed: %s", exc)
            return CollectionResult(
                source="maps",
                raw_count=0,
                items=[],
                error_code="provider_error",
                message=str(exc),
            )
