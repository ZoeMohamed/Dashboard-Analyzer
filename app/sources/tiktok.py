"""TikTok source adapter and payload parser for Dashboard Analyzer."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from .apify_client import ApifyError
from .base import CollectionResult, Evidence, EvidenceMetrics, SourceAdapter, Topic

logger = logging.getLogger(__name__)

ACTOR_ID = "clockworks~tiktok-scraper"


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


def parse_tiktok_item(item: dict[str, Any], topic_id: str) -> Evidence | None:
    """Parse a single TikTok item from clockworks~tiktok-scraper payload into Evidence.
    
    Skips items without valid text/caption to prevent fake content.
    """
    external_id = _clean_str(item.get("id") or item.get("videoId"))
    text = _clean_str(item.get("text") or item.get("desc") or item.get("description"))

    # Rule 10: If text is missing or empty, skip item! Do not create fake evidence.
    if not external_id or not text:
        return None

    author_meta = item.get("authorMeta") or item.get("author") or {}
    author_name = None
    author_unique_id = None
    author_url = None
    if isinstance(author_meta, dict):
        author_name = _clean_str(
            author_meta.get("nickName") or author_meta.get("name") or author_meta.get("uniqueId")
        )
        author_unique_id = _clean_str(author_meta.get("uniqueId"))
        author_url = _clean_str(author_meta.get("profileUrl"))

    url = _clean_str(item.get("webVideoUrl") or item.get("videoUrl"))
    if not url and author_unique_id:
        url = f"https://www.tiktok.com/@{author_unique_id}/video/{external_id}"
    if not author_url and author_unique_id:
        author_url = f"https://www.tiktok.com/@{author_unique_id}"

    title = f"TikTok post oleh {author_name}" if author_name else f"TikTok video {external_id}"

    published_raw = item.get("createTimeISO") or item.get("createTime")
    published_at = _parse_datetime(published_raw)

    views = _clean_int(item.get("playCount") or item.get("play_count") or item.get("views"))
    likes = _clean_int(item.get("diggCount") or item.get("likes") or item.get("likeCount"))
    comments = _clean_int(item.get("commentCount") or item.get("comments"))
    shares = _clean_int(item.get("shareCount") or item.get("shares"))

    has_metrics = any(v is not None for v in (views, likes, comments, shares))
    metrics = (
        EvidenceMetrics(views=views, likes=likes, comments=comments, shares=shares)
        if has_metrics
        else None
    )

    metadata: dict[str, Any] = {
        "author_name": author_name,
        "author_unique_id": author_unique_id,
        "author_url": author_url,
        "query": _clean_str(item.get("searchQuery")),
    }

    return Evidence(
        id=f"tiktok:{external_id}",
        source="tiktok",
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


def parse_tiktok_payload(
    items: list[dict[str, Any]],
    topic: Topic,
    limit: int = 50,
    *,
    lookback_days: int | None = None,
    now: datetime | None = None,
) -> list[Evidence]:
    """Parse list of raw TikTok items and return bounded Evidence list with lookback filtering."""
    current = now or datetime.now(timezone.utc)
    cutoff = current - timedelta(days=lookback_days) if lookback_days is not None else None

    seen_ids: set[str] = set()
    results: list[Evidence] = []
    for item in items:
        evidence = parse_tiktok_item(item, topic.id)
        if evidence and evidence.id not in seen_ids:
            if cutoff and evidence.published_at and evidence.published_at < cutoff:
                continue
            seen_ids.add(evidence.id)
            results.append(evidence)
            if len(results) >= limit:
                break
    return results


def build_tiktok_input(topic: Topic, limit: int = 50) -> dict[str, Any]:
    """Build input dictionary for clockworks~tiktok-scraper actor with explicit legacy flags."""
    queries = list(dict.fromkeys([*topic.keywords, *topic.product_terms, topic.name]))
    clean_queries = [q.strip() for q in queries if q and len(q.strip()) >= 2][:3]
    return {
        "searchQueries": clean_queries or [topic.name],
        "searchSection": "/video",
        "resultsPerPage": min(limit, 50),
        "maxFollowersPerProfile": 0,
        "maxFollowingPerProfile": 0,
        "commentsPerPost": 0,
        "topLevelCommentsPerPost": 0,
        "maxRepliesPerComment": 0,
        "scrapeRelatedSearchWords": False,
        "scrapeRelatedVideos": False,
        "scrapeAdditionalAuthorMeta": False,
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
        "shouldDownloadSlideshowImages": False,
        "shouldDownloadAvatars": False,
        "shouldDownloadMusicCovers": False,
        "downloadSubtitlesOptions": "NEVER_DOWNLOAD_SUBTITLES",
        "aiVideoDescription": False,
        "aiVideoSummary": False,
        "proxyCountryCode": "ID",
    }


class TikTokAdapter:
    """TikTok adapter implementing SourceAdapter protocol."""

    name = "tiktok"

    def __init__(self, apify_client: Any | None = None) -> None:
        self.apify_client = apify_client

    async def collect(
        self, topic: Topic, limit: int = 50, *, lookback_days: int = 30
    ) -> CollectionResult:
        if not self.apify_client:
            return CollectionResult(
                source="tiktok",
                raw_count=0,
                items=[],
                error_code="not_configured",
                message="Apify client belum dikonfigurasi.",
            )

        actor_input = build_tiktok_input(topic, limit)
        try:
            run_result = await self.apify_client.run_actor(
                ACTOR_ID, actor_input, timeout_seconds=120
            )
            raw_items = run_result.get("items", [])
            evidence_items = parse_tiktok_payload(
                raw_items, topic, limit, lookback_days=lookback_days
            )
            return CollectionResult(
                source="tiktok",
                raw_count=len(raw_items),
                items=evidence_items,
                provider_run_id=run_result.get("run_id"),
            )
        except ApifyError as exc:
            logger.error("TikTok collection failed (ApifyError): %s", exc.message)
            return CollectionResult(
                source="tiktok",
                raw_count=0,
                items=[],
                error_code=exc.code,
                message=exc.message,
            )
        except Exception as exc:
            logger.error("TikTok collection failed: %s", exc)
            return CollectionResult(
                source="tiktok",
                raw_count=0,
                items=[],
                error_code="provider_error",
                message=str(exc),
            )
