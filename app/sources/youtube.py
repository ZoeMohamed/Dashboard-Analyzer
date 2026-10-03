"""YouTube source adapter, classification engine, and payload parser for Dashboard Analyzer."""

from __future__ import annotations

import asyncio
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

# Slang normalization from legacy POC
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


def _contains_phrase(text: str, phrase: str) -> bool:
    norm_text = normalize(text)
    norm_phrase = normalize(phrase)
    return bool(norm_phrase) and f" {norm_phrase} " in f" {norm_text} "


# Classification signals from legacy POC
SIGNALS: dict[str, tuple[str, ...]] = {
    "review": ("review", "nyobain", "cobain", "jujur", "mukbang", "kuliner", "jajan", "viral", "rekomendasi", "taste test", "worth it"),
    "resep": ("resep", "cara membuat", "cara bikin", "tutorial", "bikin sendiri", "diy", "homemade"),
    "ide_usaha": ("ide usaha", "peluang usaha", "jualan", "modal", "hpp", "omzet", "franchise", "kemitraan", "gerobak", "untung"),
    "lainnya": (),
}
PRIORITY: tuple[str, ...] = ("ide_usaha", "resep", "review")


def classify_content_type(title: str) -> str:
    """Classify video content type into ide_usaha, resep, review, or lainnya with legacy priority."""
    text = normalize(title)
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


def parse_count(value: Any) -> int | None:
    """Parse localized Indonesian counts like '12 rb', '1,2 jt', '3 juta', '1 miliar'."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return max(0, int(value))
    text = str(value).lower().replace(".", "").replace(",", ".")
    match = re.search(r"([\d.]+)\s*(miliar|juta|jt|ribu|rb|k|m)?", text)
    if not match:
        digits = "".join(ch for ch in str(value) if ch.isdigit())
        return int(digits) if digits else None
    try:
        number = float(match.group(1))
    except ValueError:
        return None
    scale = {
        "rb": 1_000,
        "ribu": 1_000,
        "k": 1_000,
        "jt": 1_000_000,
        "juta": 1_000_000,
        "m": 1_000_000,
        "miliar": 1_000_000_000,
    }.get(match.group(2), 1)
    return max(0, int(number * scale))


def relative_datetime(value: Any, *, now: datetime | None = None) -> datetime:
    """Parse relative datetime strings like '2 minggu lalu', '3 bln', '2 thn' or ISO date strings."""
    reference = now or datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    raw_str = str(value or "").strip()
    if not raw_str:
        return reference

    # Check relative date match
    match = re.search(
        r"(\d+)\s+(detik|dtk|second|seconds|menit|mnt|minute|minutes|jam|hour|hours|"
        r"hari|day|days|minggu|mgg|week|weeks|bulan|bln|month|months|tahun|thn|year|years)",
        raw_str.casefold(),
    )
    if match:
        amount = int(match.group(1))
        seconds = {
            "detik": 1, "dtk": 1, "second": 1, "seconds": 1,
            "menit": 60, "mnt": 60, "minute": 60, "minutes": 60,
            "jam": 3600, "hour": 3600, "hours": 3600,
            "hari": 86400, "day": 86400, "days": 86400,
            "minggu": 604800, "mgg": 604800, "week": 604800, "weeks": 604800,
            "bulan": 2592000, "bln": 2592000, "month": 2592000, "months": 2592000,
            "tahun": 31536000, "thn": 31536000, "year": 31536000, "years": 31536000,
        }[match.group(2)]
        return reference - timedelta(seconds=amount * seconds)

    # Check ISO format
    try:
        iso_clean = raw_str.replace("Z", "+00:00").replace("z", "+00:00")
        dt = datetime.fromisoformat(iso_clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return reference



def build_query(topic: Topic, *, extra_excludes: tuple[str, ...] | list[str] = ()) -> str:
    """Build YouTube query with terms and excluded keywords matching legacy semantics."""
    terms = [f'"{keyword}"' if " " in keyword else keyword for keyword in topic.keywords]
    if not terms and topic.name:
        terms = [f'"{topic.name}"' if " " in topic.name else topic.name]
    excluded_terms = list(dict.fromkeys([*topic.exclude_terms, *extra_excludes]))
    excluded = [f'-"{term}"' if " " in term else f"-{term}" for term in excluded_terms if term.strip()]
    return "|".join(terms) + (" " + " ".join(excluded) if excluded else "")


def is_relevant(
    item: dict[str, Any],
    topic: Topic,
    *,
    extra_excludes: tuple[str, ...] | list[str] = (),
) -> bool:
    """Check if item matches topic, has UMKM intent, and is not excluded."""
    if item.get("live_broadcast_content") == "upcoming":
        return False

    snippet = item.get("snippet") if isinstance(item.get("snippet"), dict) else item
    title = str(snippet.get("title") or "")
    description = str(snippet.get("description") or snippet.get("desc") or "")[:600]
    channel_title = str(
        snippet.get("channelTitle") or snippet.get("channel_title") or snippet.get("author") or ""
    )
    combined = f"{title} {description} {channel_title}"

    # 1. Exclude filter
    excludes = list(dict.fromkeys([*topic.exclude_terms, *YOUTUBE_EXCLUDE_TERMS, *extra_excludes]))
    if any(_contains_phrase(combined, excl) for excl in excludes):
        return False

    # 2. Product signal
    signals = list(dict.fromkeys([*topic.keywords, *topic.product_terms, topic.name]))
    has_product = any(_contains_phrase(combined, sig) for sig in signals if sig.strip())
    if not has_product:
        return False

    # 3. UMKM / business intent signal
    has_intent = any(_contains_phrase(combined, term) for term in UMKM_INTENT_TERMS)
    return has_intent


def parse_youtube_item(item: dict[str, Any], topic: Topic) -> Evidence | None:
    """Parse a single YouTube video item into Evidence with relevance check and metadata."""
    raw_id = item.get("id")
    if isinstance(raw_id, dict):
        external_id = _clean_str(raw_id.get("videoId"))
    else:
        external_id = _clean_str(raw_id or item.get("videoId") or item.get("video_id"))

    if not external_id:
        return None

    snippet = item.get("snippet") if isinstance(item.get("snippet"), dict) else item
    title = _clean_str(snippet.get("title"))
    if not title:
        return None

    # Check relevance using full legacy semantics (exclude + product + UMKM intent)
    if not is_relevant(item, topic):
        return None

    channel_title = _clean_str(
        snippet.get("channelTitle") or snippet.get("author") or snippet.get("channel") or snippet.get("channel_title")
    )
    description = _clean_str(snippet.get("description") or snippet.get("desc"))
    text = description or (f"Video oleh {channel_title}: {title}" if channel_title else title)
    url = _clean_str(item.get("url")) or f"https://www.youtube.com/watch?v={external_id}"

    published_raw = snippet.get("publishedAt") or snippet.get("publishTime") or snippet.get("published_at")
    published_at = relative_datetime(published_raw)

    stats = item.get("statistics") if isinstance(item.get("statistics"), dict) else item
    views = parse_count(stats.get("viewCount") or stats.get("views"))
    likes = _clean_int(stats.get("likeCount") or stats.get("likes"))
    comments = _clean_int(stats.get("commentCount") or stats.get("comments"))

    has_metrics = any(v is not None for v in (views, likes, comments))
    metrics = (
        EvidenceMetrics(views=views, likes=likes, comments=comments)
        if has_metrics
        else None
    )

    # Compute views per day with accurate published date
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
    """Parse list of raw YouTube items and return bounded, sorted Evidence list."""
    seen_ids: set[str] = set()
    results: list[Evidence] = []
    for item in items:
        evidence = parse_youtube_item(item, topic)
        if evidence and evidence.id not in seen_ids:
            seen_ids.add(evidence.id)
            results.append(evidence)

    # Sort using legacy semantics: published_at desc, then views desc
    results.sort(
        key=lambda ev: (
            ev.published_at or datetime.min.replace(tzinfo=timezone.utc),
            (ev.metrics.views if ev.metrics and ev.metrics.views else 0),
        ),
        reverse=True,
    )
    return results[:limit]


class YouTubeClient:
    """Official YouTube Data API v3 client with legacy TrendDiscovery search passes."""

    mode = "api"

    def __init__(self, api_key: str, *, client: httpx.AsyncClient | None = None) -> None:
        self.api_key = api_key
        self._client = client or httpx.AsyncClient(timeout=15.0)
        self._owns_client = client is None

    async def search(
        self,
        topic: Topic,
        limit: int = 50,
        *,
        lookback_days: int = 30,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        current = now or datetime.now(timezone.utc)
        cutoff = current - timedelta(days=lookback_days)
        query = build_query(topic)

        # 1. Search by date (with bounded pagination)
        ids: list[str] = []
        page_token: str | None = None
        for _ in range(2):
            params: dict[str, Any] = {
                "part": "snippet",
                "q": query,
                "type": "video",
                "order": "date",
                "publishedAfter": cutoff.isoformat().replace("+00:00", "Z"),
                "regionCode": "ID",
                "relevanceLanguage": "id",
                "maxResults": min(limit, 50),
                "key": self.api_key,
            }
            if page_token:
                params["pageToken"] = page_token
            resp = await self._client.get(f"{API_ROOT}/search", params=params)
            if resp.status_code != 200:
                break
            data = resp.json()
            ids.extend([
                item["id"]["videoId"]
                for item in data.get("items", [])
                if item.get("id", {}).get("videoId")
            ])
            page_token = data.get("nextPageToken")
            if not page_token:
                break

        # 2. Search by popularity (viewCount)
        pop_params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "order": "viewCount",
            "publishedAfter": cutoff.isoformat().replace("+00:00", "Z"),
            "regionCode": "ID",
            "relevanceLanguage": "id",
            "maxResults": min(limit, 50),
            "key": self.api_key,
        }
        pop_resp = await self._client.get(f"{API_ROOT}/search", params=pop_params)
        if pop_resp.status_code == 200:
            ids.extend([
                item["id"]["videoId"]
                for item in pop_resp.json().get("items", [])
                if item.get("id", {}).get("videoId")
            ])

        unique_ids = list(dict.fromkeys(ids))
        if not unique_ids:
            return []

        # 3. Batch fetch video details
        details: list[dict[str, Any]] = []
        for start in range(0, len(unique_ids), 50):
            batch = unique_ids[start:start + 50]
            vid_resp = await self._client.get(
                f"{API_ROOT}/videos",
                params={
                    "part": "snippet,statistics",
                    "id": ",".join(batch),
                    "key": self.api_key,
                },
            )
            if vid_resp.status_code == 200:
                details.extend(vid_resp.json().get("items", []))

        return details

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()


class PublicYouTubeClient:
    """Best-effort public search used when no YouTube API key is provided."""

    mode = "public"

    def __init__(self, *, timeout: float = 15.0, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None
        self._cache: dict[str, dict[str, Any]] = {}
        self._refreshed_at: dict[str, datetime] = {}

    @staticmethod
    def _initial_data(html: str, markers: tuple[str, ...]) -> dict[str, Any]:
        decoder = json.JSONDecoder()
        for marker in markers:
            index = html.find(marker)
            if index >= 0:
                parsed, _ = decoder.raw_decode(html[index + len(marker):].lstrip())
                if isinstance(parsed, dict):
                    return parsed
        raise ValueError("Data awal YouTube tidak ditemukan")

    async def search(
        self,
        topic: Topic,
        limit: int = 50,
        *,
        lookback_days: int = 30,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        current = now or datetime.now(timezone.utc)
        query = build_query(topic)
        headers = {"User-Agent": USER_AGENT, "Accept-Language": "id-ID,id;q=0.9"}

        items: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        # Perform discovery pass by date (CAI%3D) and viewCount (CAMSAhAB)
        for sort_filter in ("CAI%3D", "CAMSAhAB"):
            url = f"{WEB_ROOT}/results?search_query={quote_plus(query)}&hl=id&gl=ID&sp={sort_filter}"
            try:
                resp = await self._client.get(url, headers=headers)
                if resp.status_code != 200:
                    continue
                data = self._initial_data(
                    resp.text,
                    ("var ytInitialData = ", "window['ytInitialData'] = ", "ytInitialData = "),
                )
                for node in self._walk(data):
                    vr = node.get("videoRenderer")
                    if not isinstance(vr, dict) or not vr.get("videoId"):
                        continue
                    video_id = str(vr["videoId"])
                    if video_id in seen_ids:
                        continue
                    seen_ids.add(video_id)

                    v_title = "".join(r.get("text", "") for r in vr.get("title", {}).get("runs", [])) or vr.get("title", {}).get("simpleText", "")
                    c_title = "".join(r.get("text", "") for r in vr.get("ownerText", {}).get("runs", [])) or vr.get("ownerText", {}).get("simpleText", "")
                    desc = "".join(r.get("text", "") for r in vr.get("detailedMetadataSnippets", [{}])[0].get("snippetText", {}).get("runs", [])) if vr.get("detailedMetadataSnippets") else ""
                    views_text = vr.get("viewCountText", {}).get("simpleText") or "".join(r.get("text", "") for r in vr.get("viewCountText", {}).get("runs", []))
                    published_text = vr.get("publishedTimeText", {}).get("simpleText") or "".join(r.get("text", "") for r in vr.get("publishedTimeText", {}).get("runs", []))

                    parsed_date = relative_datetime(published_text, now=current)
                    parsed_views = parse_count(views_text)

                    item_dict = {
                        "id": video_id,
                        "snippet": {
                            "title": v_title,
                            "channelTitle": c_title,
                            "description": desc,
                            "publishedAt": parsed_date.isoformat(),
                        },
                        "statistics": {
                            "viewCount": parsed_views,
                        },
                    }
                    self._cache[video_id] = item_dict
                    self._refreshed_at[video_id] = current
                    items.append(item_dict)
                    if len(items) >= limit:
                        break
            except Exception as exc:
                logger.warning("Public YouTube scraper filter %s failed: %s", sort_filter, exc)

            if len(items) >= limit:
                break

        return items

    @staticmethod
    def _walk(node: Any):
        if isinstance(node, dict):
            yield node
            for child in node.values():
                yield from PublicYouTubeClient._walk(child)
        elif isinstance(node, list):
            for child in node:
                yield from PublicYouTubeClient._walk(child)

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()


class YouTubeAdapter:
    """YouTube adapter implementing SourceAdapter protocol."""

    name = "youtube"

    def __init__(self, client: Any | None = None, *, auto_fallback: bool = True) -> None:
        self.client = client
        if self.client is None and auto_fallback:
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
