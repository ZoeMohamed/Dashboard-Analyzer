"""Facebook source adapter and payload parser for Dashboard Analyzer."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .base import CollectionResult, Evidence, EvidenceMetrics, SourceAdapter, Topic

logger = logging.getLogger(__name__)

ACTOR_ID = "apify~facebook-search-scraper"


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
            dt = fallback or datetime.now(timezone.utc)
    else:
        dt = fallback or datetime.now(timezone.utc)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_facebook_item(item: dict[str, Any], topic_id: str) -> Evidence | None:
    """Parse a single Facebook public post item into Evidence."""
    external_id = _clean_str(item.get("id") or item.get("postId"))
    if not external_id:
        return None

    author_name = _clean_str(
        item.get("authorName")
        or item.get("pageName")
        or (item.get("user") or {}).get("name")
        or (item.get("author") or {}).get("name")
    )

    text = _clean_str(item.get("text") or item.get("message") or item.get("postText"))
    url = _clean_str(item.get("url") or item.get("postUrl"))

    title = author_name or (f"Facebook Post {external_id}")
    if not text and not title:
        return None

    published_raw = item.get("time") or item.get("date") or item.get("timestamp")
    published_at = _parse_datetime(published_raw)

    views = _clean_int(item.get("views") or item.get("viewCount"))
    likes = _clean_int(item.get("likes") or item.get("likesCount") or item.get("reactions"))
    comments = _clean_int(item.get("comments") or item.get("commentsCount"))
    shares = _clean_int(item.get("shares") or item.get("sharesCount"))

    has_metrics = any(v is not None for v in (views, likes, comments, shares))
    metrics = (
        EvidenceMetrics(views=views, likes=likes, comments=comments, shares=shares)
        if has_metrics
        else None
    )

    metadata: dict[str, Any] = {}
    if author_name:
        metadata["author_name"] = author_name

    return Evidence(
        id=f"facebook:{external_id}",
        source="facebook",
        topic_id=topic_id,
        external_id=external_id,
        title=title,
        text=text,
        url=url,
        published_at=published_at,
        collected_at=datetime.now(timezone.utc),
        metrics=metrics,
        metadata=metadata,
    )


def parse_facebook_payload(
    items: list[dict[str, Any]], topic: Topic, limit: int = 50
) -> list[Evidence]:
    """Parse list of raw Facebook items and return bounded Evidence list."""
    seen_ids: set[str] = set()
    results: list[Evidence] = []
    for item in items:
        evidence = parse_facebook_item(item, topic.id)
        if evidence and evidence.id not in seen_ids:
            seen_ids.add(evidence.id)
            results.append(evidence)
            if len(results) >= limit:
                break
    return results


def build_facebook_input(topic: Topic, limit: int = 50) -> dict[str, Any]:
    """Build input dictionary for apify~facebook-search-scraper actor."""
    queries = list(dict.fromkeys([*topic.keywords, *topic.product_terms, topic.name]))
    clean_queries = [q.strip() for q in queries if q and len(q.strip()) >= 2][:3]
    return {
        "categories": clean_queries or [topic.name],
        "locations": topic.cities[:1] if topic.cities else [],
        "searchType": "posts",
        "resultsLimit": min(limit, 50),
    }


class FacebookAdapter:
    """Facebook adapter implementing SourceAdapter protocol."""

    name = "facebook"

    def __init__(self, apify_client: Any | None = None) -> None:
        self.apify_client = apify_client

    async def collect(self, topic: Topic, limit: int = 50) -> CollectionResult:
        if not self.apify_client:
            return CollectionResult(
                source="facebook",
                raw_count=0,
                items=[],
                error_code="not_configured",
                message="Apify client belum dikonfigurasi.",
            )

        actor_input = build_facebook_input(topic, limit)
        try:
            run_result = await self.apify_client.run_actor(
                ACTOR_ID, actor_input, timeout_seconds=120
            )
            raw_items = run_result.get("items", [])
            evidence_items = parse_facebook_payload(raw_items, topic, limit)
            return CollectionResult(
                source="facebook",
                raw_count=len(raw_items),
                items=evidence_items,
                provider_run_id=run_result.get("run_id"),
            )
        except Exception as exc:
            logger.error("Facebook collection failed: %s", exc)
            return CollectionResult(
                source="facebook",
                raw_count=0,
                items=[],
                error_code="provider_error",
                message=str(exc),
            )
