import pytest
from app.contracts import SentimentLabel
from app.intelligence.gemini import GeminiAnalyzer, parse_response


def test_gemini_parse_valid_response():
    raw_json = """
    [
        {"i": "c1", "s": "positif", "sc": 0.85, "tp": ["rasa", "kemasan"]},
        {"i": "c2", "s": "negatif", "sc": -0.70, "tp": ["harga"]}
    ]
    """
    short_to_original = {"c1": "ev-101", "c2": "ev-102"}
    results = parse_response(raw_json, short_to_original)

    assert len(results) == 2
    assert results[0].evidence_id == "ev-101"
    assert results[0].label == SentimentLabel.POSITIF
    assert results[0].score == 0.85
    assert results[0].aspects == ["rasa", "kemasan"]

    assert results[1].evidence_id == "ev-102"
    assert results[1].label == SentimentLabel.NEGATIF
    assert results[1].score == -0.70
    assert results[1].aspects == ["harga"]


def test_gemini_parse_markdown_wrapped_json():
    raw_markdown = """```json
    [
        {"i": "c1", "s": "netral", "sc": 0.05, "tp": ["promo"]}
    ]
    ```"""
    short_to_original = {"c1": "ev-201"}
    results = parse_response(raw_markdown, short_to_original)
    assert len(results) == 1
    assert results[0].evidence_id == "ev-201"
    assert results[0].label == SentimentLabel.NETRAL


def test_gemini_ignores_unregistered_id():
    raw_json = '[{"i": "c999", "s": "positif", "sc": 0.9, "tp": []}]'
    short_to_original = {"c1": "ev-101"}
    results = parse_response(raw_json, short_to_original)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_gemini_fallback_when_offline():
    # Tanpa api_keys, analyzer otomatis menggunakan fallback LexiconAnalyzer
    analyzer = GeminiAnalyzer(api_keys=[])
    items = [
        ("ev-1", "rasa cincaunya enak banget dan segar"),
        ("ev-2", "tidak enak terlalu manis"),
    ]
    results = await analyzer.analyze(items)
    assert len(results) == 2
    assert results[0].label == SentimentLabel.POSITIF
    assert results[1].label == SentimentLabel.NEGATIF
