"""Google Maps source adapter and payload parser for Dashboard Analyzer."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from .apify_client import ApifyError
from .base import CollectionResult, Evidence, EvidenceMetrics, SourceAdapter, Topic

logger = logging.getLogger(__name__)

ACTOR_ID = "compass~crawler-google-places"

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


def _signals(topic: Topic) -> list[str]:
    values = [topic.name, *topic.product_terms, *topic.keywords]
    return list(dict.fromkeys(normalize(value) for value in values if normalize(value)))


def _contains(text: str, signals: list[str]) -> bool:
    """Check whole-phrase matching with Indonesian possessive clitics support."""
    normalized = normalize(text)
    return any(
        re.search(rf"(?<!\w){re.escape(signal)}(?:nya|ku|mu)?(?!\w)", normalized)
        for signal in signals
        if signal
    )


def _review_mentions_product(text: str, topic: Topic) -> bool:
    """Check whether a review text contains topic keywords or product terms."""
    return _contains(text, _signals(topic))


def parse_maps_place_items(
    place: dict[str, Any], topic: Topic, limit: int = 50
) -> list[Evidence]:
    """Parse a Google Maps place item into place and review Evidence items."""
    results: list[Evidence] = []
    place_id = _clean_str(place.get("placeId") or place.get("place_id") or place.get("id"))
    if not place_id:
        return results

    # Legacy relevance: exclude closed places
    business_status = _clean_str(place.get("businessStatus") or place.get("business_status"))
    if (business_status or "").upper() in {"CLOSED_PERMANENTLY", "CLOSED"}:
        return results

    place_name = _clean_str(place.get("title") or place.get("name")) or "Tempat Google Maps"
    place_address = _clean_str(place.get("address") or place.get("formattedAddress") or place.get("street"))
    place_url = _clean_str(place.get("url") or place.get("googleMapsUrl") or place.get("googleUrl"))
    rating = _clean_float(place.get("totalScore") or place.get("rating"))
    review_count = _clean_int(place.get("reviewsCount") or place.get("userRatingCount"))
    primary_type = _clean_str(place.get("categoryName") or place.get("category"))

    # Exclude filter on place name
    if any(_contains(place_name, [normalize(term)]) for term in topic.exclude_terms if term.strip()):
        return results

    # Extract raw reviews first to assess review hits
    raw_reviews = place.get("reviews") or place.get("reviewsData") or []
    if isinstance(raw_reviews, dict):
        raw_reviews = [raw_reviews]
    if not isinstance(raw_reviews, list):
        raw_reviews = []

    # Relevance check: place is relevant if name mentions product OR any review mentions product
    signals = _signals(topic)
    name_hit = _contains(place_name, signals)

    matching_reviews: list[tuple[int, dict[str, Any], str]] = []
    for idx, rev in enumerate(raw_reviews):
        if not isinstance(rev, dict):
            continue
        rev_text = _clean_str(rev.get("text") or rev.get("reviewText") or rev.get("snippet"))
        if rev_text and _review_mentions_product(rev_text, topic):
            matching_reviews.append((idx, rev, rev_text))

    review_hit = len(matching_reviews) > 0
    if not (name_hit or review_hit):
        # Place is irrelevant to topic: reject place and all its reviews completely
        return results

    # 1. Place Summary Evidence (Metrics views must NOT be contaminated with review_count!)
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
        metrics=None,
        metadata={
            "type": "place",
            "place_id": place_id,
            "name": place_name,
            "rating": rating,
            "review_count": review_count,
            "user_rating_count": review_count,
            "address": place_address,
            "primary_type": primary_type,
            "business_status": business_status,
        },
    )
    results.append(place_evidence)

    # 2. Extract matching reviews up to limit
    for idx, rev, rev_text in matching_reviews:
        if len(results) >= limit:
            break

        rev_id = _clean_str(rev.get("reviewId") or rev.get("review_id") or rev.get("id")) or f"{place_id}_rev_{idx}"
        author_name = _clean_str(rev.get("name") or rev.get("authorName") or rev.get("reviewerName")) or "Pengulas Google"
        author_uri = _clean_str(rev.get("reviewerUrl") or rev.get("authorUrl"))
        stars = _clean_int(rev.get("stars") or rev.get("rating"))
        published_raw = rev.get("publishedAtDate") or rev.get("publishedDate") or rev.get("publishAt") or rev.get("date")

        # Preserve review URL if available, fallback to place URL
        rev_url = _clean_str(rev.get("reviewUrl") or rev.get("url")) or place_url

        rev_evidence = Evidence(
            id=f"maps:{rev_id}",
            source="maps",
            topic_id=topic.id,
            external_id=rev_id,
            title=f"{place_name} — Ulasan oleh {author_name}",
            text=rev_text,
            url=rev_url,
            published_at=_parse_datetime(published_raw),
            collected_at=datetime.now(timezone.utc),
            metrics=None,
            metadata={
                "type": "review",
                "place_id": place_id,
                "place_name": place_name,
                "review_id": rev_id,
                "author": author_name,
                "author_name": author_name,
                "author_uri": author_uri,
                "stars": stars,
                "rating": stars,
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


def build_maps_input(
    topic: Topic,
    limit: int | None = None,
    *,
    max_places: int = 3,
    max_reviews: int = 10,
) -> dict[str, Any]:
    """Build input dictionary for compass~crawler-google-places actor matching legacy semantics."""
    city = topic.cities[0] if topic.cities else "Indonesia"
    keyword = topic.keywords[0] if topic.keywords else topic.name
    queries = [f"{keyword} {city}"]
    return {
        "searchStringsArray": queries,
        "locationQuery": city,
        "maxCrawledPlacesPerSearch": max_places,
        "maxReviews": max_reviews,
        "reviewsSort": "newest",
        "reviewsOrigin": "google",
        "language": "id",
        "scrapePlaceDetailPage": True,
        "scrapeReviewsPersonalData": False,
        "skipClosedPlaces": True,
    }


class MapsAdapter:
    """Google Maps adapter implementing SourceAdapter protocol."""

    name = "maps"

    def __init__(self, apify_client: Any | None = None, *, actor_timeout_seconds: int = 120) -> None:
        self.apify_client = apify_client
        # Large actor runs (Maps reviews, social search) often need several
        # minutes; the platform passes APIFY_ACTOR_TIMEOUT_SECONDS here.
        self.actor_timeout_seconds = actor_timeout_seconds

    async def collect(
        self, topic: Topic, limit: int = 50, *, max_places: int = 3
    ) -> CollectionResult:
        if not self.apify_client:
            return CollectionResult(
                source="maps",
                raw_count=0,
                items=[],
                error_code="not_configured",
                message="Apify client belum dikonfigurasi.",
            )

        actor_input = build_maps_input(topic, max_places=max_places)
        try:
            run_result = await self.apify_client.run_actor(
                ACTOR_ID, actor_input, timeout_seconds=self.actor_timeout_seconds
            )
            raw_items = run_result.get("items", [])
            evidence_items = parse_maps_payload(raw_items, topic, limit)
            return CollectionResult(
                source="maps",
                raw_count=len(raw_items),
                items=evidence_items,
                provider_run_id=run_result.get("run_id"),
            )
        except ApifyError as exc:
            logger.error("Maps collection failed (ApifyError): %s", exc.message)
            return CollectionResult(
                source="maps",
                raw_count=0,
                items=[],
                error_code=exc.code,
                message=exc.message,
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
