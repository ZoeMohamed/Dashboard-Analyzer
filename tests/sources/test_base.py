"""Test base data models and contracts for source adapters."""

from datetime import datetime, timezone
import pytest
from app.sources.base import Evidence, EvidenceMetrics, Topic, CollectionResult


def test_evidence_requires_title_or_text() -> None:
    # Valid with title only
    ev1 = Evidence(
        id="tiktok:1",
        source="tiktok",
        topic_id="topik-1",
        external_id="1",
        title="Ada Judul",
    )
    assert ev1.title == "Ada Judul"

    # Valid with text only
    ev2 = Evidence(
        id="tiktok:2",
        source="tiktok",
        topic_id="topik-1",
        external_id="2",
        text="Ada Teks",
    )
    assert ev2.text == "Ada Teks"

    # Invalid without title and without text
    with pytest.raises(ValueError, match="wajib memiliki minimal salah satu"):
        Evidence(
            id="tiktok:3",
            source="tiktok",
            topic_id="topik-1",
            external_id="3",
            title=None,
            text="",
        )


def test_evidence_metrics_nullable() -> None:
    ev = Evidence(
        id="instagram:1",
        source="instagram",
        topic_id="topik-1",
        external_id="1",
        title="Post",
        metrics=None,
    )
    assert ev.metrics is None


def test_collection_result_defaults() -> None:
    res = CollectionResult(source="shopee")
    assert res.raw_count == 0
    assert res.items == []
    assert res.error_code is None
