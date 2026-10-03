"""YouTube source adapter and payload parser for Dashboard Analyzer."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .base import CollectionResult, Evidence, EvidenceMetrics, SourceAdapter, Topic

logger = logging.getLogger(__name__)


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


def _is_excluded(title: str, topic: Topic) -> bool:
    """Check if title contains excluded terms like cartoons, children shows, gaming."""
    t = title.casefold()
    default_excludes = ["kartun", "animasi", "trailer", "gameplay"]
    all_excludes = set(default_excludes + [e.casefold().strip() for e in topic.exclude_terms if e.strip()])
    return any(excl in t for excl in all_excludes)


def parse_youtube_item(item: dict[str, Any], topic: Topic) -> Evidence | None:
    """Parse a single YouTube video item (API or raw object) into Evidence."""
    # Handle id string or dict {"videoId": "..."}
    raw_id = item.get("id")
    if isinstance(raw_id, dict):
        external_id = _clean_str(raw_id.get("videoId"))
    else:
        external_id = _clean_str(raw_id or item.get("videoId"))

    if not external_id:
        return None

    snippet = item.get("snippet") or item
    title = _clean_str(snippet.get("title"))
    if not title:
        return None

    # Filter out excluded entertainment content as required by docs/SYSTEM.md
    if _is_excluded(title, topic):
        return None

    channel_title = _clean_str(snippet.get("channelTitle") or snippet.get("author") or snippet.get("channel"))
    description = _clean_str(snippet.get("description") or snippet.get("desc"))
    text = description or (f"Video oleh {channel_title}: {title}" if channel_title else title)
    url = _clean_str(item.get("url")) or f"https://www.youtube.com/watch?v={external_id}"

    published_raw = snippet.get("publishedAt") or snippet.get("publishTime")
    published_at = _parse_datetime(published_raw)

    stats = item.get("statistics") or item
    views = _clean_int(stats.get("viewCount") or stats.get("views"))
    likes = _clean_int(stats.get("likeCount") or stats.get("likes"))
    comments = _clean_int(stats.get("commentCount") or stats.get("comments"))

    has_metrics = any(v is not None for v in (views, likes, comments))
    metrics = (
        EvidenceMetrics(views=views, likes=likes, comments=comments)
        if has_metrics
        else None
    )

    # Compute views per day if published_at is available
    views_per_day: float | None = None
    if views is not None:
        age_days = max(1.0, (datetime.now(timezone.utc) - published_at).total_seconds() / 86400.0)
        views_per_day = round(views / age_days, 1)

    metadata: dict[str, Any] = {
        "channel_title": channel_title,
        "views_per_day": views_per_day,
    }

    return Evidence(
        id=f"youtube:{external_id}",
        source="youtube",
        topic_id=topic.id,
        external_id=external_id,
        title=title,
        text=text,
        url=url,
        published_at=published_at,
        collected_at=datetime.now(timezone.utc),
        metrics=metrics,
        metadata=metadata,
    )


def parse_youtube_payload(
    items: list[dict[str, Any]], topic: Topic, limit: int = 50
) -> list[Evidence]:
    """Parse list of raw YouTube items and return bounded Evidence list."""
    seen_ids: set[str] = set()
    results: list[Evidence] = []
    for item in items:
        evidence = parse_youtube_item(item, topic)
        if evidence and evidence.id not in seen_ids:
            seen_ids.add(evidence.id)
            results.append(evidence)
            if len(results) >= limit:
                break
    return results


class YouTubeAdapter:
    """YouTube adapter implementing SourceAdapter protocol."""

    name = "youtube"

    def __init__(self, client: Any | None = None) -> None:
        self.client = client

    async def collect(self, topic: Topic, limit: int = 50) -> CollectionResult:
        if not self.client:
            return CollectionResult(
                source="youtube",
                raw_count=0,
                items=[],
                error_code="not_configured",
                message="YouTube client belum dikonfigurasi.",
            )

        try:
            raw_items = await self.client.search(topic, limit=min(limit, 50))
            evidence_items = parse_youtube_payload(raw_items, topic, limit)
            return CollectionResult(
                source="youtube",
                raw_count=len(raw_items),
                items=evidence_items,
            )
        except Exception as exc:
            logger.error("YouTube collection failed: %s", exc)
            return CollectionResult(
                source="youtube",
                raw_count=0,
                items=[],
                error_code="provider_error",
                message=str(exc),
            )
