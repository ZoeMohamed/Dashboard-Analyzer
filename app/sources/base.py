"""Base interfaces, data models, and protocols for Dashboard Analyzer source adapters."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Protocol
from pydantic import BaseModel, Field, model_validator

SourceName = Literal[
    "tiktok",
    "instagram",
    "facebook",
    "maps",
    "shopee",
    "youtube",
]

SourceStatus = Literal[
    "disabled",
    "misconfigured",
    "queued",
    "running",
    "fresh",
    "empty",
    "stale",
    "budget_exhausted",
    "error",
]

SourceErrorCode = Literal[
    "not_configured",
    "provider_timeout",
    "provider_permission",
    "invalid_payload",
    "budget_exhausted",
    "provider_error",
]


class EvidenceMetrics(BaseModel):
    """Engagement and quantitative metrics for a piece of evidence."""

    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None


class Topic(BaseModel):
    """UMKM product topic definition."""

    id: str
    name: str
    keywords: list[str] = Field(default_factory=list)
    product_terms: list[str] = Field(default_factory=list)
    exclude_terms: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class Evidence(BaseModel):
    """Normalized evidence item collected from a public source."""

    id: str
    source: SourceName
    topic_id: str
    external_id: str
    title: str | None = None
    text: str | None = None
    url: str | None = None
    published_at: datetime | None = None
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    relevance_score: float | None = None
    metrics: EvidenceMetrics | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_content_presence(self) -> Evidence:
        has_title = bool(self.title and self.title.strip())
        has_text = bool(self.text and self.text.strip())
        if not (has_title or has_text):
            raise ValueError(
                "Evidence wajib memiliki minimal salah satu dari 'title' atau 'text'."
            )
        return self


class CollectionResult(BaseModel):
    """Batch collection result returned by any SourceAdapter."""

    source: SourceName
    raw_count: int = 0
    items: list[Evidence] = Field(default_factory=list)
    provider_run_id: str | None = None
    error_code: str | None = None
    message: str | None = None


class SourceAdapter(Protocol):
    """Protocol that every provider adapter must implement."""

    name: SourceName

    async def collect(self, topic: Topic, limit: int = 50) -> CollectionResult:
        """Collect public evidence for the given topic up to limit items."""
        ...
