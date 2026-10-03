"""Instagram source adapter and payload parser for Dashboard Analyzer."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from .apify_client import ApifyError
from .base import CollectionResult, Evidence, EvidenceMetrics, SourceAdapter, Topic

logger = logging.getLogger(__name__)

ACTOR_ID = "apify~instagram-scraper"


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


def parse_instagram_item(item: dict[str, Any], topic_id: str) -> Evidence | None:
    """Parse a single Instagram item from apify~instagram-scraper payload into Evidence.
    
    Skips items without valid text/caption to prevent fake content.
    """
    external_id = _clean_str(
        item.get("id") or item.get("pk") or item.get("shortCode") or item.get("shortcode")
    )
    text = _clean_str(item.get("caption") or item.get("captionText") or item.get("text"))

    # Rule 10: If text is missing or empty, skip item! Do not create fake evidence.
    if not external_id or not text:
        return None

    owner = item.get("owner") or item.get("ownerMeta") or {}
    owner_username = None
    if isinstance(owner, dict):
        owner_username = _clean_str(
            owner.get("username") or owner.get("ownerUsername") or owner.get("fullName")
        )
    if not owner_username:
        owner_username = _clean_str(item.get("ownerUsername") or item.get("username"))

    shortcode = _clean_str(item.get("shortCode") or item.get("shortcode"))
    url = _clean_str(item.get("url"))
    if not url and shortcode:
        url = f"https://www.instagram.com/p/{shortcode}/"

    author_url = _clean_str(owner.get("profileUrl")) if isinstance(owner, dict) else None
    if not author_url and owner_username:
        author_url = f"https://www.instagram.com/{owner_username}/"

    title = f"Instagram post oleh {owner_username}" if owner_username else f"Instagram post {external_id}"

    published_raw = item.get("timestamp") or item.get("takenAt") or item.get("taken_at_timestamp")
    published_at = _parse_datetime(published_raw)

    views = _clean_int(
        item.get("videoViewCount") or item.get("videoPlayCount") or item.get("plays")
    )
    likes = _clean_int(item.get("likesCount") or item.get("likes"))
    if likes is None and isinstance(item.get("edge_liked_by"), dict):
        likes = _clean_int(item["edge_liked_by"].get("count"))

    comments = _clean_int(item.get("commentsCount") or item.get("comments"))
    if comments is None and isinstance(item.get("edge_media_to_comment"), dict):
        comments = _clean_int(item["edge_media_to_comment"].get("count"))

    shares = _clean_int(item.get("sharesCount") or item.get("shares"))

    has_metrics = any(v is not None for v in (views, likes, comments, shares))
    metrics = (
        EvidenceMetrics(views=views, likes=likes, comments=comments, shares=shares)
        if has_metrics
        else None
    )

    metadata: dict[str, Any] = {
        "shortcode": shortcode,
        "owner_username": owner_username,
        "author_url": author_url,
        "query": _clean_str(item.get("sourceHashtag") or item.get("search")),
    }

    return Evidence(
        id=f"instagram:{external_id}",
        source="instagram",
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


def parse_instagram_payload(
    items: list[dict[str, Any]],
    topic: Topic,
    limit: int = 50,
    *,
    lookback_days: int | None = None,
    now: datetime | None = None,
) -> list[Evidence]:
    """Parse list of raw Instagram items and return bounded Evidence list with lookback filtering."""
    current = now or datetime.now(timezone.utc)
    cutoff = current - timedelta(days=lookback_days) if lookback_days is not None else None

    seen_ids: set[str] = set()
    results: list[Evidence] = []
    for item in items:
        evidence = parse_instagram_item(item, topic.id)
        if evidence and evidence.id not in seen_ids:
            if cutoff and evidence.published_at and evidence.published_at < cutoff:
                continue
            seen_ids.add(evidence.id)
            results.append(evidence)
            if len(results) >= limit:
                break
    return results


def build_instagram_input(topic: Topic, limit: int = 50, lookback_days: int = 30) -> dict[str, Any]:
    """Build input dictionary for apify~instagram-scraper actor with legacy semantics."""
    queries = list(dict.fromkeys([*topic.keywords, *topic.product_terms, topic.name]))
    tags: list[str] = []
    for q in queries:
        clean = "".join(ch for ch in q.casefold() if ch.isalnum())
        if clean:
            tags.append(f"https://www.instagram.com/explore/tags/{clean}/")

    return {
        "resultsType": "posts",
        "directUrls": tags[:3] or [f"https://www.instagram.com/explore/tags/{topic.id}/"],
        "resultsLimit": min(limit, 50),
        "onlyPostsNewerThan": f"{max(1, lookback_days)} days",
        "addParentData": True,
    }


class InstagramAdapter:
    """Instagram adapter implementing SourceAdapter protocol."""

    name = "instagram"

    def __init__(self, apify_client: Any | None = None) -> None:
        self.apify_client = apify_client

    async def collect(
        self, topic: Topic, limit: int = 50, *, lookback_days: int = 30
    ) -> CollectionResult:
        if not self.apify_client:
            return CollectionResult(
                source="instagram",
                raw_count=0,
                items=[],
                error_code="not_configured",
                message="Apify client belum dikonfigurasi.",
            )

        actor_input = build_instagram_input(topic, limit, lookback_days=lookback_days)
        try:
            run_result = await self.apify_client.run_actor(
                ACTOR_ID, actor_input, timeout_seconds=120
            )
            raw_items = run_result.get("items", [])
            evidence_items = parse_instagram_payload(
                raw_items, topic, limit, lookback_days=lookback_days
            )
            return CollectionResult(
                source="instagram",
                raw_count=len(raw_items),
                items=evidence_items,
                provider_run_id=run_result.get("run_id"),
            )
        except ApifyError as exc:
            logger.error("Instagram collection failed (ApifyError): %s", exc.message)
            return CollectionResult(
                source="instagram",
                raw_count=0,
                items=[],
                error_code=exc.code,
                message=exc.message,
            )
        except Exception as exc:
            logger.error("Instagram collection failed: %s", exc)
            return CollectionResult(
                source="instagram",
                raw_count=0,
                items=[],
                error_code="provider_error",
                message=str(exc),
            )
