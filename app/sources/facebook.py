"""Facebook source adapter and payload parser for Dashboard Analyzer."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from .apify_client import ApifyError
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
    """Parse a single Facebook public post item into Evidence.
    
    Skips items without valid text/content to prevent fake evidence.
    """
    external_id = _clean_str(
        item.get("postId") or item.get("post_id") or item.get("id") or item.get("legacyId")
    )
    text = _clean_str(item.get("text") or item.get("postText") or item.get("message") or item.get("description"))

    # Rule 10: If text is missing or empty, skip item! Do not create fake evidence.
    if not external_id or not text:
        return None

    author = (
        item.get("user")
        or item.get("author")
        or item.get("owner")
        or item.get("page")
        or item.get("pageName")
        or {}
    )
    page_name = item.get("pageName")
    page_label = page_name.get("name") if isinstance(page_name, dict) else page_name
    author_name = _clean_str(
        item.get("authorName")
        or item.get("userName")
        or page_label
        or (author.get("name") if isinstance(author, dict) else None)
        or (author.get("username") if isinstance(author, dict) else None)
    )

    url = _clean_str(item.get("url") or item.get("postUrl") or item.get("post_url"))
    author_url = (
        _clean_str(item.get("authorUrl") or author.get("url") or author.get("profileUrl"))
        if isinstance(author, dict)
        else None
    )
    if not author_url and isinstance(author, dict) and author.get("id"):
        author_url = f"https://www.facebook.com/{author.get('id')}"

    title = f"Facebook post oleh {author_name}" if author_name else f"Facebook post {external_id}"

    published_raw = (
        item.get("publishedAt")
        or item.get("published_at")
        or item.get("time")
        or item.get("date")
        or item.get("timestamp")
    )
    published_at = _parse_datetime(published_raw)

    views = _clean_int(item.get("views") or item.get("videoViews") or item.get("viewCount"))
    likes = _clean_int(item.get("likes") or item.get("likesCount") or item.get("reactions") or item.get("reactionCount"))
    comments = _clean_int(item.get("comments") or item.get("commentsCount") or item.get("commentCount"))
    shares = _clean_int(item.get("shares") or item.get("sharesCount") or item.get("shareCount"))

    has_metrics = any(v is not None for v in (views, likes, comments, shares))
    metrics = (
        EvidenceMetrics(views=views, likes=likes, comments=comments, shares=shares)
        if has_metrics
        else None
    )

    metadata: dict[str, Any] = {
        "author_name": author_name,
        "author_url": author_url,
        "query": _clean_str(item.get("searchQuery") or item.get("query") or item.get("category")),
    }

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
    items: list[dict[str, Any]],
    topic: Topic,
    limit: int = 50,
    *,
    lookback_days: int | None = None,
    now: datetime | None = None,
) -> list[Evidence]:
    """Parse list of raw Facebook items and return bounded Evidence list with lookback filtering."""
    current = now or datetime.now(timezone.utc)
    cutoff = current - timedelta(days=lookback_days) if lookback_days is not None else None

    seen_ids: set[str] = set()
    results: list[Evidence] = []
    for item in items:
        evidence = parse_facebook_item(item, topic.id)
        if evidence and evidence.id not in seen_ids:
            if cutoff and evidence.published_at and evidence.published_at < cutoff:
                continue
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

    def __init__(self, apify_client: Any | None = None, *, actor_timeout_seconds: int = 120) -> None:
        self.apify_client = apify_client
        # Large actor runs (Maps reviews, social search) often need several
        # minutes; the platform passes APIFY_ACTOR_TIMEOUT_SECONDS here.
        self.actor_timeout_seconds = actor_timeout_seconds

    async def collect(
        self, topic: Topic, limit: int = 50, *, lookback_days: int = 30
    ) -> CollectionResult:
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
                ACTOR_ID, actor_input, timeout_seconds=self.actor_timeout_seconds
            )
            raw_items = run_result.get("items", [])
            evidence_items = parse_facebook_payload(
                raw_items, topic, limit, lookback_days=lookback_days
            )
            return CollectionResult(
                source="facebook",
                raw_count=len(raw_items),
                items=evidence_items,
                provider_run_id=run_result.get("run_id"),
            )
        except ApifyError as exc:
            logger.error("Facebook collection failed (ApifyError): %s", exc.message)
            return CollectionResult(
                source="facebook",
                raw_count=0,
                items=[],
                error_code=exc.code,
                message=exc.message,
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
