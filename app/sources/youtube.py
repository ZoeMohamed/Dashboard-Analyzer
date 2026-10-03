"""YouTube source adapter, classification engine, and payload parser for Dashboard Analyzer."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from urllib.parse import quote_plus

import httpx

from .base import CollectionResult, Evidence, EvidenceMetrics, SourceAdapter, Topic

logger = logging.getLogger(__name__)

API_ROOT = "https://www.googleapis.com/youtube/v3"
WEB_ROOT = "https://www.youtube.com"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# 27 exclude terms from legacy POC
YOUTUBE_EXCLUDE_TERMS: tuple[str, ...] = (
    "upin ipin", "kartun", "animasi", "animation", "episode", "full episode",
    "serial", "sinetron", "dongeng", "cerita anak", "nursery", "kids", "kidz",
    "balita", "lagu", "lagu anak", "music video", "official trailer", "trailer", "gaming",
    "gameplay", "meme", "hiburan", "komedi", "parodi", "sketsa", "film anak",
    "tayangan anak",
)

# 50+ UMKM intent terms from legacy POC
UMKM_INTENT_TERMS: tuple[str, ...] = (
    "review", "resep", "resepnya", "cara membuat", "cara bikin", "tutorial", "jualan",
    "jualannya", "terjual", "laku", "pedagang", "dagang", "bisnis", "usaha", "umkm", "warung",
    "kedai", "kuliner", "jajanan", "makanan", "minuman", "harga", "harganya", "menu", "order",
    "pesan", "homemade", "rumahan", "buatan", "modal", "omzet", "produk", "brand", "lokal",
    "crispy", "keju", "sambal", "bumbu", "bumbunya", "porsi", "rasa", "kemasan", "produksi",
    "produsen", "outlet", "toko", "cabang", "pelanggan", "catering", "katering", "supplier",
    "grosir", "franchise", "kemitraan", "unboxing", "testi", "testimoni", "pasar", "tembus",
    "ekspor", "mancanegara", "murah", "affordable", "battle", "seduh", "makan", "enak", "serba",
    "rekomendasi", "mukbang", "jajan", "beli", "viral", "ramai", "rame",
)

# Classification dictionaries from legacy POC
SIGNALS: dict[str, tuple[str, ...]] = {
    "review": ("review", "nyobain", "cobain", "jujur", "mukbang", "kuliner", "jajan", "viral", "rekomendasi", "taste test", "worth it"),
    "resep": ("resep", "cara membuat", "cara bikin", "tutorial", "bikin sendiri", "diy", "homemade"),
    "ide_usaha": ("ide usaha", "peluang usaha", "jualan", "modal", "hpp", "omzet", "franchise", "kemitraan", "gerobak", "untung"),
    "lainnya": (),
}
PRIORITY: tuple[str, ...] = ("ide_usaha", "resep", "review")


def classify_content_type(title: str) -> str:
    """Classify video content type into review, resep, ide_usaha, or lainnya."""
    text = title.casefold()
    scores = {
        kind: sum(1 for signal in SIGNALS[kind] if signal in text)
        for kind in PRIORITY
    }
    best = max(scores.values(), default=0)
    if best == 0:
        return "lainnya"
    return next(kind for kind in PRIORITY if scores[kind] == best)


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
    """Check if title contains excluded entertainment/cartoons or user exclude_terms."""
    t = title.casefold()
    all_excludes = set(list(YOUTUBE_EXCLUDE_TERMS) + [e.casefold().strip() for e in topic.exclude_terms if e.strip()])
    return any(excl in t for excl in all_excludes)


def parse_youtube_item(item: dict[str, Any], topic: Topic) -> Evidence | None:
    """Parse a single YouTube video item into Evidence with content_type & views_per_day."""
    raw_id = item.get("id")
    if isinstance(raw_id, dict):
        external_id = _clean_str(raw_id.get("videoId"))
    else:
        external_id = _clean_str(raw_id or item.get("videoId") or item.get("video_id"))

    if not external_id:
        return None

    snippet = item.get("snippet") or item
    title = _clean_str(snippet.get("title"))
    if not title:
        return None

    # Filter out excluded entertainment content
    if _is_excluded(title, topic):
        return None

    channel_title = _clean_str(
        snippet.get("channelTitle") or snippet.get("author") or snippet.get("channel") or snippet.get("channel_title")
    )
    description = _clean_str(snippet.get("description") or snippet.get("desc"))
    text = description or (f"Video oleh {channel_title}: {title}" if channel_title else title)
    url = _clean_str(item.get("url")) or f"https://www.youtube.com/watch?v={external_id}"

    published_raw = snippet.get("publishedAt") or snippet.get("publishTime") or snippet.get("published_at")
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

    # Compute views per day
    views_per_day: float | None = None
    if views is not None:
        age_days = max(1.0, (datetime.now(timezone.utc) - published_at).total_seconds() / 86400.0)
        views_per_day = round(views / age_days, 1)

    # Full Content Type Classification from legacy POC
    content_type = classify_content_type(title)

    metadata: dict[str, Any] = {
        "channel_title": channel_title,
        "views_per_day": views_per_day,
        "content_type": content_type,
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


class YouTubeClient:
    """Official YouTube Data API v3 client."""

    def __init__(self, api_key: str, *, client: httpx.AsyncClient | None = None) -> None:
        self.api_key = api_key
        self._client = client or httpx.AsyncClient(timeout=15.0)

    async def search(self, topic: Topic, limit: int = 50) -> list[dict[str, Any]]:
        query = topic.keywords[0] if topic.keywords else topic.name
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "regionCode": "ID",
            "relevanceLanguage": "id",
            "maxResults": min(limit, 50),
            "key": self.api_key,
        }
        resp = await self._client.get(f"{API_ROOT}/search", params=params)
        if resp.status_code != 200:
            return []
        data = resp.json()
        ids = [item["id"]["videoId"] for item in data.get("items", []) if item.get("id", {}).get("videoId")]
        if not ids:
            return []

        # Fetch video statistics
        vid_resp = await self._client.get(
            f"{API_ROOT}/videos",
            params={"part": "snippet,statistics", "id": ",".join(ids[:50]), "key": self.api_key},
        )
        if vid_resp.status_code == 200:
            return vid_resp.json().get("items", [])
        return data.get("items", [])


class PublicYouTubeClient:
    """Public fallback scraper that parses YouTube HTML without an API key."""

    def __init__(self, *, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(timeout=15.0)

    async def search(self, topic: Topic, limit: int = 50) -> list[dict[str, Any]]:
        query = topic.keywords[0] if topic.keywords else topic.name
        url = f"{WEB_ROOT}/results?search_query={quote_plus(query)}&hl=id&gl=ID"
        headers = {"User-Agent": USER_AGENT, "Accept-Language": "id-ID,id;q=0.9"}
        try:
            resp = await self._client.get(url, headers=headers)
            if resp.status_code != 200:
                return []
            html = resp.text
            # Extract initial data JSON
            marker = "var ytInitialData = "
            idx = html.find(marker)
            if idx == -1:
                return []
            end = html.find(";</script>", idx)
            raw_json = html[idx + len(marker):end]
            data = json.loads(raw_json)
            # Find video renderers
            items: list[dict[str, Any]] = []
            for item in self._walk(data):
                vr = item.get("videoRenderer")
                if isinstance(vr, dict) and vr.get("videoId"):
                    v_title = "".join(r.get("text", "") for r in vr.get("title", {}).get("runs", []))
                    c_title = "".join(r.get("text", "") for r in vr.get("ownerText", {}).get("runs", []))
                    desc = "".join(r.get("text", "") for r in vr.get("detailedMetadataSnippets", [{}])[0].get("snippetText", {}).get("runs", [])) if vr.get("detailedMetadataSnippets") else ""
                    views_text = vr.get("viewCountText", {}).get("simpleText", "")
                    items.append({
                        "id": vr["videoId"],
                        "snippet": {
                            "title": v_title,
                            "channelTitle": c_title,
                            "description": desc,
                            "publishedAt": datetime.now(timezone.utc).isoformat(),
                        },
                        "statistics": {
                            "viewCount": "".join(ch for ch in views_text if ch.isdigit()) or None
                        }
                    })
                    if len(items) >= limit:
                        break
            return items
        except Exception as exc:
            logger.warning("Public YouTube scraper failed: %s", exc)
            return []

    @staticmethod
    def _walk(node: Any):
        if isinstance(node, dict):
            yield node
            for child in node.values():
                yield from PublicYouTubeClient._walk(child)
        elif isinstance(node, list):
            for child in node:
                yield from PublicYouTubeClient._walk(child)


class YouTubeAdapter:
    """YouTube adapter implementing SourceAdapter protocol."""

    name = "youtube"

    def __init__(self, client: Any | None = None, *, auto_fallback: bool = True) -> None:
        self.client = client
        if self.client is None and auto_fallback:
            # Auto fallback to API if key exists, otherwise public client
            yt_key = os.getenv("YOUTUBE_API_KEY")
            if yt_key:
                self.client = YouTubeClient(yt_key)
            else:
                self.client = PublicYouTubeClient()

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
