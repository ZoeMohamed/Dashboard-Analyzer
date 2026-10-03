"""Bridge the source adapters (app/sources) to the shared pipeline contract.

Adapters report provider failures as ``CollectionResult.error_code`` and use
their own lightweight models. The pipeline expects ``app.contracts`` models and
domain exceptions, so this module is the only place the two meet.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import ValidationError

from app.config import Settings
from app.contracts import CollectionResult, Evidence, EvidenceMetrics, SourceName
from app.errors import (
    BudgetExhaustedError,
    DomainError,
    InvalidProviderPayloadError,
    NotConfiguredError,
    ProviderError,
    ProviderPermissionError,
    ProviderTimeoutError,
)
from app.sources.apify_client import ApifyClient
from app.sources.facebook import FacebookAdapter
from app.sources.instagram import InstagramAdapter
from app.sources.maps import MapsAdapter
from app.sources.shopee import ShopeeAdapter
from app.sources.tiktok import TikTokAdapter
from app.sources.youtube import PublicYouTubeClient, YouTubeAdapter, YouTubeClient

logger = logging.getLogger(__name__)

APIFY_ADAPTERS: dict[SourceName, type] = {
    SourceName.TIKTOK: TikTokAdapter,
    SourceName.INSTAGRAM: InstagramAdapter,
    SourceName.FACEBOOK: FacebookAdapter,
    SourceName.MAPS: MapsAdapter,
    SourceName.SHOPEE: ShopeeAdapter,
}

ERRORS: dict[str, type[DomainError]] = {
    "not_configured": NotConfiguredError,
    "provider_timeout": ProviderTimeoutError,
    "provider_permission": ProviderPermissionError,
    "budget_exhausted": BudgetExhaustedError,
    "invalid_payload": InvalidProviderPayloadError,
}


def _count(value: Any) -> int | None:
    try:
        return max(0, int(float(value))) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _rating(value: Any) -> float | None:
    try:
        rating = float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None
    return rating if rating is not None and 0 <= rating <= 5 else None


def _clip(value: Any, limit: int) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text[:limit] or None


def to_evidence(item: Any, source: SourceName) -> Evidence | None:
    """Map one adapter evidence item to the shared contract, or skip it.

    Items without an http(s) link are skipped: every stored evidence must lead
    back to its original page. Metrics that the adapter keeps in metadata
    (rating, price, sold) are lifted into typed fields; missing values stay null.
    """

    url = (item.url or "").strip()
    if not url.startswith(("https://", "http://")) or len(url) > 2_000:
        return None
    metadata = json.loads(json.dumps(item.metadata or {}, default=str))
    metrics = item.metrics
    try:
        return Evidence(
            source=source,
            topic_id=item.topic_id,
            external_id=str(item.external_id)[:500],
            title=_clip(item.title, 500),
            text=_clip(item.text, 10_000),
            author=_clip(metadata.get("author_name") or metadata.get("author") or metadata.get("shop_name"), 300),
            url=url,
            published_at=item.published_at,
            collected_at=item.collected_at,
            relevance_score=item.relevance_score if item.relevance_score is None or 0 <= item.relevance_score <= 1 else None,
            metrics=EvidenceMetrics(
                views=_count(metrics.views if metrics else None),
                likes=_count(metrics.likes if metrics else None),
                comments=_count(metrics.comments if metrics else None),
                shares=_count(metrics.shares if metrics else None),
                rating=_rating(metadata.get("rating")),
                review_count=_count(metadata.get("review_count") or metadata.get("rating_count")),
                price=_count(metadata.get("price")),
                original_price=_count(metadata.get("original_price")),
                sold=_count(metadata.get("sold_count")),
            ),
            metadata=metadata,
        )
    except ValidationError:
        logger.warning("Evidence %s dari %s dilewati karena tidak sesuai kontrak", item.external_id, source)
        return None


class SourceAdapterProvider:
    """Expose an app.sources adapter as a pipeline SourceProvider."""

    def __init__(self, adapter: Any, source: SourceName, provider_name: str) -> None:
        self.adapter = adapter
        self.source = source
        self.provider_name = provider_name

    async def collect(self, topic: Any, *, limit: int) -> CollectionResult:
        result = await self.adapter.collect(topic, limit=limit)
        items = [evidence for evidence in (to_evidence(item, self.source) for item in result.items) if evidence is not None]
        if result.error_code and not items:
            raise ERRORS.get(result.error_code, ProviderError)(result.message or "Provider gagal")
        return CollectionResult(source=self.source, items=items, raw_count=max(result.raw_count, len(items)), provider_run_id=result.provider_run_id)


def build_providers(settings: Settings) -> tuple[dict[SourceName, SourceAdapterProvider], list[Any]]:
    """Construct configured providers and the clients that must be closed on shutdown.

    Apify sources without a token are simply not registered, so the pipeline
    reports them as ``misconfigured`` instead of failing.
    """

    active = set(settings.active_sources)
    providers: dict[SourceName, SourceAdapterProvider] = {}
    clients: list[Any] = []
    tokens = [token.get_secret_value() for token in settings.apify_credentials]
    if tokens and active.intersection(APIFY_ADAPTERS):
        apify = ApifyClient(tokens, max_attempts=settings.apify_key_max_attempts, cooldown_seconds=settings.apify_key_cooldown_seconds)
        clients.append(apify)
        for source, adapter in APIFY_ADAPTERS.items():
            if source in active:
                providers[source] = SourceAdapterProvider(adapter(apify, actor_timeout_seconds=settings.apify_actor_timeout_seconds), source, "apify")
    if SourceName.YOUTUBE in active:
        youtube = YouTubeClient(settings.youtube_api_key.get_secret_value()) if settings.youtube_api_key else PublicYouTubeClient()
        clients.append(youtube)
        providers[SourceName.YOUTUBE] = SourceAdapterProvider(YouTubeAdapter(youtube, auto_fallback=False), SourceName.YOUTUBE, "youtube")
    return providers, clients
