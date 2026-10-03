"""Relevance gate and sentiment analysis between source collection and storage."""

from __future__ import annotations

import logging
from typing import Any

from app.analyzer.rate_limiter import AsyncRateLimiter
from app.config import Settings
from app.contracts import Analysis, AnalyzerName, Evidence, SentimentLabel
from app.intelligence.relevance import is_relevant_evidence
from app.intelligence.sentiment import LexiconAnalyzer
from app.services.usage import UsageService

logger = logging.getLogger(__name__)

# Lexicon counts are not calibrated probabilities, so the local fallback reports
# a deliberately low confidence; the UI shows the analyzer name next to it.
LOCAL_CONFIDENCE = {SentimentLabel.POSITIF: 0.6, SentimentLabel.NEGATIF: 0.6, SentimentLabel.NETRAL: 0.3}
GEMINI_CONFIDENCE = 0.8


def _is_place_record(item: Evidence) -> bool:
    # Maps place rows describe a business, not an opinion. The adapter already
    # decided relevance from the place name and its reviews.
    return item.source == "maps" and item.metadata.get("type") == "place"


class IntelligenceService:
    def __init__(self, settings: Settings, usage: UsageService, *, gemini: Any | None = None, fallback: Any | None = None) -> None:
        self.settings = settings
        self.usage = usage
        self.gemini = gemini
        self.fallback = fallback or LexiconAnalyzer()
        self.limiter = AsyncRateLimiter(settings.gemini_rpm)

    @classmethod
    def from_settings(cls, settings: Settings, usage: UsageService) -> "IntelligenceService":
        gemini = None
        if settings.gemini_api_key_values:
            try:
                from app.intelligence.gemini import GeminiAnalyzer

                gemini = GeminiAnalyzer(settings, model=settings.gemini_model)
            except (ImportError, RuntimeError, ValueError):
                logger.warning("Gemini tidak tersedia; analisis memakai leksikon lokal")
        return cls(settings, usage, gemini=gemini)

    def filter_relevant(self, topic: Any, items: list[Evidence]) -> list[Evidence]:
        return [
            item for item in items
            if _is_place_record(item) or is_relevant_evidence(f"{item.title or ''} {item.text or ''}", topic)
        ]

    async def analyze(self, items: list[Evidence]) -> list[Analysis]:
        pairs = [(item.id, item.text or item.title or "") for item in items if item.id and not _is_place_record(item)]
        results: dict[str, tuple[Any, AnalyzerName]] = {}
        if self.gemini is not None:
            size = self.settings.gemini_batch_size
            for start in range(0, len(pairs), size):
                batch = pairs[start:start + size]
                try:
                    await self.usage.reserve("gemini", None, len(batch))
                    await self.limiter.acquire()
                    for result in await self.gemini.analyze(batch):
                        results[result.id] = (result, AnalyzerName.GEMINI)
                except Exception as exc:  # budget, quota, and schema failures all fall back locally
                    logger.warning("Gemini gagal, memakai leksikon lokal: %s", type(exc).__name__)
                    break
        missing = [pair for pair in pairs if pair[0] not in results]
        for result in await self.fallback.analyze(missing):
            results[result.id] = (result, AnalyzerName.LOCAL_FALLBACK)
        analyses: list[Analysis] = []
        for evidence_id, (result, analyzer) in results.items():
            label = SentimentLabel(result.sentiment)
            confidence = GEMINI_CONFIDENCE if analyzer == AnalyzerName.GEMINI else LOCAL_CONFIDENCE[label]
            analyses.append(Analysis(evidence_id=evidence_id, label=label, score=max(-1.0, min(1.0, float(result.score))), confidence=confidence, aspects=list(result.topics), analyzer=analyzer))
        return analyses
