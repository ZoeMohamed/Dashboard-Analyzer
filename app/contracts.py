from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator


class SourceName(str, Enum):
    SUMMARY = "summary"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    MAPS = "maps"
    SHOPEE = "shopee"
    YOUTUBE = "youtube"


class SourceStatus(str, Enum):
    DISABLED = "disabled"
    MISCONFIGURED = "misconfigured"
    QUEUED = "queued"
    RUNNING = "running"
    FRESH = "fresh"
    EMPTY = "empty"
    STALE = "stale"
    BUDGET_EXHAUSTED = "budget_exhausted"
    ERROR = "error"


class SentimentLabel(str, Enum):
    POSITIF = "positif"
    NEGATIF = "negatif"
    NETRAL = "netral"
    PENDING = "pending"


class TopicCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    keywords: list[str] = Field(default_factory=list, max_length=5)
    product_terms: list[str] = Field(default_factory=list, max_length=8)
    exclude_terms: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)


class Topic(BaseModel):
    id: str
    name: str
    keywords: list[str] = Field(default_factory=list)
    product_terms: list[str] = Field(default_factory=list)
    exclude_terms: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EvidenceMetrics(BaseModel):
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None


class Evidence(BaseModel):
    id: str
    source: str
    topic_id: str
    external_id: str
    title: str | None = None
    text: str | None = None
    url: str | None = None
    published_at: datetime | None = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    relevance_score: float = Field(default=1.0, ge=0.0, le=1.0)
    metrics: EvidenceMetrics | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_content_presence(self) -> Evidence:
        if not (self.title and self.title.strip()) and not (self.text and self.text.strip()):
            raise ValueError("Evidence harus memiliki setidaknya 'title' atau 'text'.")
        return self


class Analysis(BaseModel):
    evidence_id: str
    label: SentimentLabel
    score: float = Field(default=0.0, ge=-1.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    aspects: list[str] = Field(default_factory=list)
    analyzer: str = "lexicon"
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SourceRun(BaseModel):
    id: str
    source: str
    topic_id: str
    status: SourceStatus = SourceStatus.FRESH
    trigger: Literal["manual", "scheduled", "system"] = "manual"
    provider_run_id: str | None = None
    raw_count: int = 0
    relevant_count: int = 0
    inserted_count: int = 0
    error_code: str | None = None
    message: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None


class SourceSummary(BaseModel):
    source: str
    evidence_count: int = 0
    status: SourceStatus = SourceStatus.FRESH
    updated_at: datetime | None = None
    message: str | None = None


class Snapshot(BaseModel):
    topic: Topic
    total_evidence: int = 0
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    pending_count: int = 0
    top_aspects: list[str] = Field(default_factory=list)
    source_summaries: list[SourceSummary] = Field(default_factory=list)
    updated_at: datetime | None = None


class TopicListResponse(BaseModel):
    topics: list[Topic]


class RefreshResponse(BaseModel):
    run_id: str
    status: SourceStatus
