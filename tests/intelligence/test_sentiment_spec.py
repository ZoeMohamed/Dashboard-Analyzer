"""Required Indonesian sentiment cases from docs/SYSTEM.md section 6."""

import pytest

from app.intelligence.relevance import is_relevant_evidence
from app.intelligence.sentiment import LexiconAnalyzer
from app.contracts import TopicCreate


async def _analyze(text: str):
    return (await LexiconAnalyzer().analyze([("c1", text)]))[0]


@pytest.mark.parametrize(("text", "label"), [
    ("enak banget", "positif"),
    ("tidak enak", "negatif"),
    ("nggak mengecewakan", "positif"),
    ("siapa sih yang nggak suka ini", "positif"),
    ("akhirnya produk ini hadir", "positif"),
    ("Promo hari ini! Cappuccino cincau diskon 20% untuk semua menu", "netral"),
    ("Launching produk hari ini", "netral"),
    ("😍😍😍", "netral"),
    ("terlalu manis dan cincaunya keras", "negatif"),
    ("Terlalu enak, pengen beli lagi", "positif"),
])
async def test_required_cases(text: str, label: str) -> None:
    assert (await _analyze(text)).sentiment == label


async def test_delivery_complaint_does_not_flip_taste_opinion() -> None:
    result = await _analyze("Rasanya enak banget, cuma pengirimannya lama")
    assert result.sentiment == "positif"
    assert "rasa" in result.topics and "pengiriman" in result.topics


async def test_mixed_taste_and_price_reports_both_aspects() -> None:
    result = await _analyze("Rasanya enak, tapi terlalu mahal")
    assert result.sentiment == "netral"
    assert result.topics[:2] == ["harga", "rasa"]


@pytest.mark.parametrize(("text", "relevant"), [
    ("Cappuccino cincau ini enak", True),  # full keyword
    ("cincau di atas cappuccino", True),  # two product terms
    ("Es cincau segar", False),  # one generic product term only
    ("Upin Ipin minum cappuccino cincau", False),  # exclude term wins
])
def test_relevance_gate(text: str, relevant: bool) -> None:
    topic = TopicCreate(name="Cappuccino Cincau", exclude_terms=["upin ipin"])
    assert is_relevant_evidence(text, topic) is relevant
