"""Mesin analisis sentimen leksikon Bahasa Indonesia dan ekstraksi aspek inovasi UMKM."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
import re
from typing import Iterable

from app.contracts import Analysis, SentimentLabel
from app.intelligence.normalize import normalize, tokenize

LEXICON_DIR = Path(__file__).parent / "lexicon"

NEGATIONS: frozenset[str] = frozenset({
    "tidak", "bukan", "kurang", "belum", "tak", "jangan",
})

ASPECTS: tuple[str, ...] = (
    "harga", "rasa", "kemasan", "pengiriman", "pelayanan", "kualitas",
    "ukuran", "jahitan", "warna", "bahan", "promo", "porsi",
)


@lru_cache(maxsize=1)
def load_stopwords() -> frozenset[str]:
    """Muat kata tugas/stopwords dari berkas lexicon/stopwords.txt."""
    path = LEXICON_DIR / "stopwords.txt"
    if not path.exists():
        return frozenset()
    with path.open(encoding="utf-8") as handle:
        return frozenset(
            line.strip().lower()
            for line in handle
            if line.strip() and not line.lstrip().startswith("#")
        )


@lru_cache(maxsize=2)
def _load_words(filename: str) -> frozenset[str]:
    path = LEXICON_DIR / filename
    if not path.exists():
        return frozenset()
    with path.open(encoding="utf-8") as handle:
        return frozenset(
            line.strip().lower()
            for line in handle
            if line.strip() and not line.lstrip().startswith("#")
        )


def is_negated(tokens: list[str], index: int) -> bool:
    """Periksa apakah ada kata negasi dalam 2 token sebelumnya."""
    window = tokens[max(0, index - 2):index]
    return any(token in NEGATIONS for token in window)


def aspect_present(aspect: str, tokens: list[str]) -> bool:
    """Deteksi kemunculan aspek termasuk akhiran kepemilikan (-nya, -an, -ku, -mu)."""
    suffixes = ("nya", "ku", "mu", "an")
    aspect_forms = {aspect, *(f"{aspect}{s}" for s in suffixes)}
    return any(token in aspect_forms for token in tokens)


def extract_aspects(text: str, max_aspects: int = 3) -> list[str]:
    """Ekstrak maksimal 3 aspek produk yang disebut dalam teks."""
    tokens = tokenize(text)
    detected = [aspect for aspect in ASPECTS if aspect_present(aspect, tokens)]
    return detected[:max_aspects]


def top_keywords(
    texts: Iterable[str],
    exclude: Iterable[str] | None = None,
    n: int = 10,
    ngram: int = 1,
) -> list[tuple[str, int]]:
    """Hitung unigram/bigram terbanyak tanpa stopwords untuk indikator visual (Fitur Wajib 2)."""
    if ngram not in (1, 2):
        raise ValueError("ngram harus bernilai 1 atau 2")
    if n <= 0:
        return []

    stopwords = load_stopwords()
    excluded_tokens = set()
    if exclude:
        for phrase in ([exclude] if isinstance(exclude, str) else exclude):
            excluded_tokens.update(tokenize(str(phrase)))

    blocked = stopwords | excluded_tokens
    counts: Counter[str] = Counter()

    for text in texts:
        tokens = [
            token for token in tokenize(text)
            if len(token) >= 3 and token not in blocked
        ]
        if ngram == 1:
            counts.update(tokens)
        else:
            bigrams = [f"{w1} {w2}" for w1, w2 in zip(tokens, tokens[1:])]
            counts.update(bigrams)

    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:n]


class LexiconAnalyzer:
    """Analyzer sentimen berbasis aturan leksikon lokal Bahasa Indonesia."""

    name = "lexicon"

    def __init__(self) -> None:
        self.positive_words = _load_words("positive.txt")
        self.negative_words = _load_words("negative.txt")

    def analyze_text(self, text: str, evidence_id: str = "") -> Analysis:
        """Klasifikasikan sentimen sebuah teks."""
        tokens = tokenize(text)
        normalized = " ".join(tokens)

        # 1. Koreksi kalimat retoris: "siapa sih yang nggak suka..." -> POSITIF
        if re.search(r"\bsiapa(?:\s+sih)?\s+yang\s+(?:tidak|nggak|ga|gak)\s+suka\b", normalized):
            aspects = extract_aspects(text)
            return Analysis(
                evidence_id=evidence_id,
                label=SentimentLabel.POSITIF,
                score=1.0,
                confidence=0.95,
                aspects=aspects,
                analyzer=self.name,
                analyzed_at=datetime.now(timezone.utc),
            )

        # 2. Koreksi konteks peluncuran/kehadiran produk: "akhirnya ... hadir/bisa kamu nikmati" -> POSITIF
        if (
            re.search(r"\bakhirnya\b", normalized)
            and re.search(r"\b(?:rasa pertamanya|menunjukkan|bisa kamu nikmati|hadir|meluncur)\b", normalized)
            and not re.search(r"\b(?:tidak enak|terlalu manis|terlalu pahit|kecewa|zonk)\b", normalized)
        ):
            aspects = extract_aspects(text)
            return Analysis(
                evidence_id=evidence_id,
                label=SentimentLabel.POSITIF,
                score=0.8,
                confidence=0.90,
                aspects=aspects,
                analyzer=self.name,
                analyzed_at=datetime.now(timezone.utc),
            )

        # 3. Hitung polaritas token dengan negation window
        pos_count = 0
        neg_count = 0

        for idx, token in enumerate(tokens):
            polarity = 0
            if token in self.positive_words:
                polarity = 1
            elif token in self.negative_words:
                polarity = -1

            # Khusus review makanan UMKM: "terlalu manis / terlalu asin / terlalu pedas" merupakan keluhan
            if idx > 0 and tokens[idx - 1] == "terlalu" and token in {"manis", "asin", "pedas", "asam", "pahit", "lembek", "cair", "kering"}:
                polarity = -1

            if polarity != 0:
                if is_negated(tokens, idx):
                    polarity *= -1  # Balik polaritas ("tidak enak" -> -1, "tidak mengecewakan" -> +1)

                if polarity > 0:
                    pos_count += 1
                elif polarity < 0:
                    neg_count += 1

        total_sentiment_words = pos_count + neg_count
        if total_sentiment_words == 0:
            score = 0.0
            label = SentimentLabel.NETRAL
            confidence = 0.70
        else:
            score = (pos_count - neg_count) / max(1, total_sentiment_words)
            if score > 0.2:
                label = SentimentLabel.POSITIF
            elif score < -0.2:
                label = SentimentLabel.NEGATIF
            else:
                label = SentimentLabel.NETRAL
            confidence = min(0.95, 0.70 + (total_sentiment_words * 0.05))

        aspects = extract_aspects(text)

        return Analysis(
            evidence_id=evidence_id,
            label=label,
            score=round(score, 3),
            confidence=round(confidence, 2),
            aspects=aspects,
            analyzer=self.name,
            analyzed_at=datetime.now(timezone.utc),
        )

    def analyze_batch(self, items: list[tuple[str, str]]) -> list[Analysis]:
        """Klasifikasi kumpulan teks (evidence_id, text)."""
        return [self.analyze_text(text, evidence_id=item_id) for item_id, text in items]
