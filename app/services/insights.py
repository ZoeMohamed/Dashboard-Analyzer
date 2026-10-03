"""Chart-ready aggregates computed from stored evidence and analyses.

Every number is derived from persisted evidence; a metric no provider reported
stays null instead of becoming zero.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from statistics import median

from app.contracts import (
    AspectCount,
    ContentMixItem,
    DailySentiment,
    EngagementTotals,
    EvidenceItem,
    Insights,
    MapsInsights,
    MarketplaceInsights,
    SentimentCounts,
    SourceInsight,
    SourceName,
    VideoInsight,
    WeeklyCount,
    YouTubeInsights,
    utc_now,
)

LABELS = ("positif", "negatif", "netral")
WEEKS = 12


def _is_place(item: EvidenceItem) -> bool:
    return item.source == SourceName.MAPS and item.metadata.get("type") == "place"


def _label(item: EvidenceItem) -> str:
    return str(item.analysis.label) if item.analysis else "pending"


def _day(item: EvidenceItem) -> date:
    return (item.published_at or item.collected_at).date()


def _sum(values: list[int | None]) -> int | None:
    present = [value for value in values if value is not None]
    return sum(present) if present else None


def _sentiment(items: list[EvidenceItem]) -> SentimentCounts:
    counts = Counter(_label(item) for item in items)
    return SentimentCounts(positif=counts["positif"], negatif=counts["negatif"], netral=counts["netral"], pending=counts["pending"])


def _views_per_day(item: EvidenceItem, now: datetime) -> float | None:
    if item.metrics.views is not None and item.published_at is not None:
        age_days = max(1.0, (now - item.published_at).total_seconds() / 86_400)
        return round(item.metrics.views / age_days, 1)
    value = item.metadata.get("views_per_day")
    return float(value) if isinstance(value, (int, float)) else None


def _gain_24h(history: list[tuple[datetime, int | None]]) -> int | None:
    points = [(captured, views) for captured, views in history if views is not None]
    if len(points) < 2:
        return None
    latest_at, latest_views = points[-1]
    baseline = [views for captured, views in points if captured <= latest_at - timedelta(hours=24)]
    return max(0, latest_views - baseline[-1]) if baseline else None


class InsightsService:
    def __init__(self, repository: object, *, evidence_limit: int = 2_000) -> None:
        self.repository = repository
        self.evidence_limit = evidence_limit

    async def build(self, topic_id: str, *, source: SourceName | None = None, days: int = 30, now: datetime | None = None) -> Insights:
        await self.repository.get_topic(topic_id)
        now = now or utc_now()
        items = await self.repository.list_topic_evidence(topic_id, source=source, limit=self.evidence_limit)
        # Maps place rows describe a business, not an opinion, so they never
        # count as pending sentiment.
        opinions = [item for item in items if not _is_place(item)]
        sources = [SourceName(source)] if source else list(SourceName)
        return Insights(
            topic_id=topic_id,
            source=source,
            window_days=days,
            total_evidence=len(items),
            sentiment=_sentiment(opinions),
            sentiment_daily=self._daily(opinions, days, now),
            aspects=self._aspects(opinions),
            sources=[self._source(name, items) for name in sources],
            youtube=await self._youtube([item for item in items if item.source == SourceName.YOUTUBE], now),
            marketplace=self._marketplace([item for item in items if item.source == SourceName.SHOPEE]),
            maps=self._maps([item for item in items if item.source == SourceName.MAPS]),
        )

    @staticmethod
    def _daily(items: list[EvidenceItem], days: int, now: datetime) -> list[DailySentiment]:
        first = now.date() - timedelta(days=days - 1)
        counts: dict[date, Counter[str]] = {first + timedelta(days=offset): Counter() for offset in range(days)}
        for item in items:
            label = _label(item)
            if label in LABELS and _day(item) in counts:
                counts[_day(item)][label] += 1
        return [DailySentiment(day=day, **{label: counter[label] for label in LABELS}) for day, counter in counts.items()]

    @staticmethod
    def _aspects(items: list[EvidenceItem]) -> list[AspectCount]:
        totals: Counter[str] = Counter()
        by_label: dict[str, Counter[str]] = {}
        for item in items:
            if item.analysis is None:
                continue
            for aspect in item.analysis.aspects:
                totals[aspect] += 1
                by_label.setdefault(aspect, Counter())[str(item.analysis.label)] += 1
        return [
            AspectCount(aspect=aspect, count=count, **{label: by_label[aspect][label] for label in LABELS})
            for aspect, count in totals.most_common(10)
        ]

    @staticmethod
    def _source(source: SourceName, items: list[EvidenceItem]) -> SourceInsight:
        selected = [item for item in items if item.source == source]
        return SourceInsight(
            source=source,
            evidence_count=len(selected),
            sentiment=_sentiment([item for item in selected if not _is_place(item)]),
            engagement=EngagementTotals(
                views=_sum([item.metrics.views for item in selected]),
                likes=_sum([item.metrics.likes for item in selected]),
                comments=_sum([item.metrics.comments for item in selected]),
                shares=_sum([item.metrics.shares for item in selected]),
            ),
        )

    async def _youtube(self, videos: list[EvidenceItem], now: datetime) -> YouTubeInsights | None:
        if not videos:
            return None
        published = [(item, item.published_at) for item in videos if item.published_at is not None]
        new_30 = sum(1 for _, at in published if at >= now - timedelta(days=30))
        prev_30 = sum(1 for _, at in published if now - timedelta(days=60) <= at < now - timedelta(days=30))
        this_week = now.date() - timedelta(days=now.weekday())
        weeks = [this_week - timedelta(weeks=offset) for offset in range(WEEKS - 1, -1, -1)]
        weekly = Counter(at.date() - timedelta(days=at.weekday()) for _, at in published)
        mix = Counter(str(item.metadata.get("content_type") or "lainnya") for item in videos)
        history = await self.repository.metric_history(item.id for item in videos)
        gains = {item.id: _gain_24h(history.get(item.id, [])) for item in videos}
        recent_rates = [rate for item, at in published if at >= now - timedelta(days=30) and (rate := _views_per_day(item, now)) is not None]
        rows = [
            VideoInsight(
                evidence_id=item.id, title=item.title, url=item.url, content_type=item.metadata.get("content_type"),
                published_at=item.published_at, views=item.metrics.views, views_per_day=_views_per_day(item, now), gain_24h=gains[item.id],
            )
            for item in videos
        ]
        rows.sort(key=lambda row: (row.views_per_day is not None, row.views_per_day or 0), reverse=True)
        measured = [gain for gain in gains.values() if gain is not None]
        return YouTubeInsights(
            videos_tracked=len(videos),
            new_videos_30d=new_30,
            new_videos_prev_30d=prev_30,
            supply_change_pct=round((new_30 - prev_30) / prev_30 * 100, 1) if prev_30 else None,
            weekly_new_videos=[WeeklyCount(week_start=week, count=weekly[week]) for week in weeks],
            content_mix=[ContentMixItem(content_type=kind, count=count, share=round(count / len(videos), 3)) for kind, count in mix.most_common()],
            attention_index=round(median(recent_rates), 1) if recent_rates else None,
            views_gain_24h=sum(measured) if measured else None,
            coverage=round(len(measured) / len(videos), 3),
            top_videos=rows[:10],
        )

    @staticmethod
    def _marketplace(products: list[EvidenceItem]) -> MarketplaceInsights | None:
        if not products:
            return None
        prices = [item.metrics.price for item in products if item.metrics.price is not None]
        ratings = [item.metrics.rating for item in products if item.metrics.rating is not None]
        return MarketplaceInsights(
            products=len(products),
            priced_products=len(prices),
            price_min=min(prices) if prices else None,
            price_max=max(prices) if prices else None,
            average_rating=round(sum(ratings) / len(ratings), 2) if ratings else None,
            total_sold=_sum([item.metrics.sold for item in products]),
        )

    @staticmethod
    def _maps(items: list[EvidenceItem]) -> MapsInsights | None:
        if not items:
            return None
        places = [item for item in items if _is_place(item)]
        ratings = [item.metrics.rating for item in places if item.metrics.rating is not None]
        return MapsInsights(
            places=len(places),
            average_rating=round(sum(ratings) / len(ratings), 2) if ratings else None,
            total_reviews=_sum([item.metrics.review_count for item in places]),
            product_opinions=len(items) - len(places),
        )
