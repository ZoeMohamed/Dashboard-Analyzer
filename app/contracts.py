"""Shared contracts for sources, intelligence, persistence, API, and UI."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class SourceName(StrEnum):
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    MAPS = "maps"
    SHOPEE = "shopee"
    YOUTUBE = "youtube"


class SourceStatus(StrEnum):
    DISABLED = "disabled"
    MISCONFIGURED = "misconfigured"
    QUEUED = "queued"
    RUNNING = "running"
    FRESH = "fresh"
    EMPTY = "empty"
    STALE = "stale"
    BUDGET_EXHAUSTED = "budget_exhausted"
    ERROR = "error"


class RunTrigger(StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    STARTUP = "startup"


class SentimentLabel(StrEnum):
    POSITIF = "positif"
    NEGATIF = "negatif"
    NETRAL = "netral"
    PENDING = "pending"


class AnalyzerName(StrEnum):
    GEMINI = "gemini"
    LOCAL_FALLBACK = "local_fallback"
    PENDING = "pending"


class ErrorCode(StrEnum):
    NOT_CONFIGURED = "not_configured"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_PERMISSION = "provider_permission"
    INVALID_PAYLOAD = "invalid_payload"
    DATABASE_TIMEOUT = "database_timeout"
    BUDGET_EXHAUSTED = "budget_exhausted"
    ALREADY_RUNNING = "already_running"
    PROVIDER_ERROR = "provider_error"


class StreamEventName(StrEnum):
    SOURCE_STATUS = "source_status"
    PROGRESS = "progress"
    EVIDENCE_NEW = "evidence_new"
    ANALYSIS_UPDATED = "analysis_updated"
    ERROR = "error"
    PING = "ping"


def _normalized_terms(values: list[str], *, maximum: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = " ".join(raw.strip().split())
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return result[:maximum]


class TopicCreate(ContractModel):
    name: str = Field(min_length=2, max_length=100)
    keywords: list[str] = Field(default_factory=list, max_length=5)
    product_terms: list[str] = Field(default_factory=list, max_length=8)
    exclude_terms: list[str] = Field(default_factory=list, max_length=20)
    cities: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return " ".join(value.strip().split())

    @field_validator("keywords")
    @classmethod
    def normalize_keywords(cls, value: list[str]) -> list[str]:
        return _normalized_terms(value, maximum=5)

    @field_validator("product_terms", "cities")
    @classmethod
    def normalize_short_lists(cls, value: list[str]) -> list[str]:
        return _normalized_terms(value, maximum=8)

    @field_validator("exclude_terms")
    @classmethod
    def normalize_excludes(cls, value: list[str]) -> list[str]:
        return _normalized_terms(value, maximum=20)

    @model_validator(mode="after")
    def provide_search_terms(self) -> "TopicCreate":
        if not self.keywords:
            self.keywords = [self.name.casefold()]
        if not self.product_terms:
            self.product_terms = self.name.casefold().split()[:8]
        return self


class Topic(TopicCreate):
    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)
    is_active: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class EvidenceMetrics(ContractModel):
    views: int | None = Field(default=None, ge=0)
    likes: int | None = Field(default=None, ge=0)
    comments: int | None = Field(default=None, ge=0)
    shares: int | None = Field(default=None, ge=0)
    rating: float | None = Field(default=None, ge=0, le=5)
    review_count: int | None = Field(default=None, ge=0)
    price: int | None = Field(default=None, ge=0)
    original_price: int | None = Field(default=None, ge=0)
    sold: int | None = Field(default=None, ge=0)


class Evidence(ContractModel):
    id: str | None = None
    source: SourceName
    topic_id: str = Field(min_length=1, max_length=120)
    external_id: str = Field(min_length=1, max_length=500)
    provider_run_id: str | None = Field(default=None, max_length=500)
    title: str | None = Field(default=None, max_length=500)
    text: str | None = Field(default=None, max_length=10_000)
    author: str | None = Field(default=None, max_length=300)
    url: str = Field(min_length=8, max_length=2_000)
    published_at: datetime | None = None
    collected_at: datetime = Field(default_factory=utc_now)
    relevance_score: float | None = Field(default=None, ge=0, le=1)
    metrics: EvidenceMetrics = Field(default_factory=EvidenceMetrics)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("url")
    @classmethod
    def allow_http_urls_only(cls, value: str) -> str:
        if not value.startswith(("https://", "http://")):
            raise ValueError("url evidence harus menggunakan http atau https")
        return value

    @model_validator(mode="after")
    def normalize_identity_and_content(self) -> "Evidence":
        if not (self.title and self.title.strip()) and not (self.text and self.text.strip()):
            raise ValueError("evidence membutuhkan title atau text")
        if self.published_at and self.published_at.tzinfo is None:
            self.published_at = self.published_at.replace(tzinfo=timezone.utc)
        if self.collected_at.tzinfo is None:
            self.collected_at = self.collected_at.replace(tzinfo=timezone.utc)
        if self.id is None:
            self.id = f"{self.source}:{self.external_id}"
        return self


class Analysis(ContractModel):
    evidence_id: str = Field(min_length=1)
    label: SentimentLabel
    score: float = Field(ge=-1, le=1)
    confidence: float = Field(ge=0, le=1)
    aspects: list[str] = Field(default_factory=list, max_length=12)
    analyzer: AnalyzerName
    analyzed_at: datetime = Field(default_factory=utc_now)

    @field_validator("aspects")
    @classmethod
    def normalize_aspects(cls, value: list[str]) -> list[str]:
        return _normalized_terms(value, maximum=12)


class EvidenceItem(Evidence):
    """Evidence enriched with its active analysis for snapshot consumers."""

    analysis: Analysis | None = None


class SourceRun(ContractModel):
    id: str | None = None
    source: SourceName
    topic_id: str = Field(min_length=1, max_length=120)
    status: SourceStatus
    trigger: RunTrigger = RunTrigger.MANUAL
    provider_run_id: str | None = Field(default=None, max_length=500)
    raw_count: int = Field(default=0, ge=0)
    relevant_count: int = Field(default=0, ge=0)
    inserted_count: int = Field(default=0, ge=0)
    error_code: ErrorCode | None = None
    message: str | None = Field(default=None, max_length=500)
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None


class CollectionResult(ContractModel):
    source: SourceName
    items: list[Evidence] = Field(default_factory=list)
    raw_count: int = Field(default=0, ge=0)
    provider_run_id: str | None = None
    usage_units: int = Field(default=1, ge=0)


class IntelligenceResult(ContractModel):
    accepted: bool
    relevance_score: float = Field(ge=0, le=1)
    reason: str = Field(max_length=300)
    analysis: Analysis | None = None


class SourceSummary(ContractModel):
    source: SourceName
    evidence_count: int = Field(default=0, ge=0)
    status: SourceStatus
    last_finished_at: datetime | None = None
    updated_at: datetime | None = None
    message: str | None = None


class SentimentCounts(ContractModel):
    positif: int = Field(default=0, ge=0)
    negatif: int = Field(default=0, ge=0)
    netral: int = Field(default=0, ge=0)
    pending: int = Field(default=0, ge=0)


class Snapshot(ContractModel):
    topic: Topic
    sentiment: SentimentCounts = Field(default_factory=SentimentCounts)
    sources: list[SourceSummary] = Field(default_factory=list)
    total_evidence: int = Field(default=0, ge=0)
    positive_count: int = Field(default=0, ge=0)
    negative_count: int = Field(default=0, ge=0)
    neutral_count: int = Field(default=0, ge=0)
    pending_count: int = Field(default=0, ge=0)
    top_aspects: list[str] = Field(default_factory=list)
    source_summaries: list[SourceSummary] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    analyses: list[Analysis] = Field(default_factory=list)
    source_runs: list[SourceRun] = Field(default_factory=list)
    updated_at: datetime | None = None
    generated_at: datetime = Field(default_factory=utc_now)
    next_cursor: str | None = None

    @model_validator(mode="after")
    def synchronize_frontend_and_legacy_fields(self) -> "Snapshot":
        if not self.sources:
            self.sources = self.source_summaries
        if not self.source_summaries:
            self.source_summaries = self.sources
        legacy_counts = (self.positive_count, self.negative_count, self.neutral_count, self.pending_count)
        if any(legacy_counts):
            self.sentiment = SentimentCounts(
                positif=self.positive_count,
                negatif=self.negative_count,
                netral=self.neutral_count,
                pending=self.pending_count,
            )
        else:
            self.positive_count = self.sentiment.positif
            self.negative_count = self.sentiment.negatif
            self.neutral_count = self.sentiment.netral
            self.pending_count = self.sentiment.pending
        return self


class ProviderUsage(ContractModel):
    provider: str
    source: SourceName | None = None
    usage_date: date
    requests: int = Field(default=0, ge=0)
    units: int = Field(default=0, ge=0)


class StreamEvent(ContractModel):
    event: StreamEventName
    type: StreamEventName | None = None
    topic_id: str
    source: SourceName | None = None
    status: SourceStatus | None = None
    run_id: str | None = None
    progress: float | None = Field(default=None, ge=0, le=1)
    message: str | None = None
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def expose_frontend_event_type(self) -> "StreamEvent":
        if self.type is None:
            self.type = self.event
        return self


class TopicListResponse(ContractModel):
    topics: list[Topic]


class RefreshRequest(ContractModel):
    sources: list[SourceName] | None = None


class RefreshResponse(ContractModel):
    run_id: str
    status: SourceStatus
