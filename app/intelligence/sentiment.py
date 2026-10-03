"""Analyzer fallback berbasis leksikon lokal."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re

from app.nlp.preprocess import tokenize

from .base import BaseAnalyzer, SentimentResult

# normalize() maps Indonesian slang such as "nggak", "gak", and "ga" to
# "tidak". Keep the complete set here for callers that provide pre-tokenized
# text and for future slang additions.
NEGATIONS = frozenset({"tidak", "bukan", "kurang", "belum", "tak", "jangan"})
TOPICS = (
    "harga", "rasa", "kemasan", "pengiriman", "pelayanan", "kualitas",
    "ukuran", "jahitan", "warna", "bahan", "promo",
)
NLP_DIR = Path(__file__).parents[1] / "nlp"

# "terlalu X" is a complaint about excess ("terlalu manis", "terlalu mahal"),
# except with words that are only ever praise ("terlalu enak" = very tasty).
EXCESS_MARKERS = frozenset({"terlalu", "kelewat", "kebanyakan"})
ALWAYS_GOOD = frozenset({"enak", "lezat", "nikmat", "mantap", "mantul", "bagus", "keren", "worth"})
# Clauses are split on punctuation and on these conjunctions so that one
# aspect's complaint does not cancel another aspect's praise.
CLAUSE_BREAKS = frozenset({
    "dan", "serta", "tapi", "tetapi", "namun", "cuma", "hanya", "sayang", "sayangnya",
    "walaupun", "meskipun", "padahal", "sedangkan",
})
DELIVERY_TERMS = frozenset({
    "pengiriman", "pengirimannya", "kirim", "dikirim", "kiriman", "kurir", "kurirnya",
    "ongkos", "paket", "paketnya", "ekspedisi", "delivery", "pengantaran", "diantar",
})
ASPECT_HINTS = {
    "mahal": "harga", "murah": "harga", "kemahalan": "harga", "overprice": "harga",
    "enak": "rasa", "lezat": "rasa", "nikmat": "rasa", "hambar": "rasa", "gurih": "rasa",
    "asin": "rasa", "pahit": "rasa", "amis": "rasa",
    "packaging": "kemasan", "bungkus": "kemasan",
    **{term: "pengiriman" for term in DELIVERY_TERMS},
    "ramah": "pelayanan", "jutek": "pelayanan", "pelayanannya": "pelayanan",
}
# Promotion vocabulary describes an offer, not an opinion; a promo caption
# without praise or complaint stays neutral (docs/SYSTEM.md section 6).
PROMO_TERMS = frozenset({"diskon", "promo", "gratis", "cashback", "potongan", "voucher", "bonus", "sale"})
_CLAUSE_PUNCTUATION = re.compile(r"[,.;:!?\n]+")


@lru_cache(maxsize=2)
def _load_words(filename: str) -> frozenset[str]:
    with (NLP_DIR / filename).open(encoding="utf-8") as handle:
        return frozenset(
            line.strip().lower()
            for line in handle
            if line.strip() and not line.lstrip().startswith("#")
        )


def _is_negated(tokens: list[str], index: int) -> bool:
    return any(token in NEGATIONS for token in tokens[max(0, index - 2):index])


def _clauses(text: str) -> list[list[str]]:
    clauses: list[list[str]] = []
    for segment in _CLAUSE_PUNCTUATION.split(text):
        current: list[str] = []
        for token in tokenize(segment):
            if token in CLAUSE_BREAKS:
                if current:
                    clauses.append(current)
                current = []
            else:
                current.append(token)
        if current:
            clauses.append(current)
    return clauses


def _topic_present(topic: str, tokens: list[str]) -> bool:
    suffixes = ("nya", "ku", "mu", "an")
    return any(token == topic or token in {topic + suffix for suffix in suffixes} for token in tokens)


class LexiconAnalyzer(BaseAnalyzer):
    name = "lexicon"

    def __init__(self) -> None:
        self.positive = _load_words("lexicon_pos.txt")
        self.negative = _load_words("lexicon_neg.txt")

    async def analyze(
        self, items: list[tuple[str, str]]
    ) -> list[SentimentResult]:
        return [self._analyze_one(comment_id, text) for comment_id, text in items]

    def _analyze_one(self, comment_id: str, text: str) -> SentimentResult:
        tokens = tokenize(text)
        normalized = " ".join(tokens)

        # Context corrections for common Indonesian social-caption constructions
        # that a bag-of-words model cannot understand. "Siapa yang tidak suka"
        # is a rhetorical positive, not a complaint. Launch copy can mention a
        # founder's past failures while clearly presenting a new product.
        if re.search(r"\bsiapa(?:\s+sih)?\s+yang\s+tidak\s+suka\b", normalized):
            return SentimentResult(id=comment_id, sentiment="positif", score=1.0, topics=[])
        if (
            re.search(r"\bakhirnya\b", normalized)
            and re.search(r"\b(?:rasa pertamanya|menunjukkan|bisa kamu nikmati|hadir|meluncur)\b", normalized)
            and not re.search(r"\b(?:tidak enak|terlalu manis|terlalu pahit|kecewa|zonk)\b", normalized)
        ):
            return SentimentResult(id=comment_id, sentiment="positif", score=0.8, topics=[])

        positive = negative = 0
        for clause in _clauses(text):
            # A delivery complaint ("pengirimannya lama") describes the courier,
            # not the product, so it must not flip the product opinion. Its
            # aspect is still reported below.
            if DELIVERY_TERMS.intersection(clause):
                continue
            clause_positive, clause_negative = self._clause_polarity(clause)
            positive += clause_positive
            negative += clause_negative
        score = (positive - negative) / max(1, positive + negative)
        sentiment = "positif" if score > 0.2 else "negatif" if score < -0.2 else "netral"
        hinted = {ASPECT_HINTS[token] for token in tokens if token in ASPECT_HINTS}
        topics = [topic for topic in TOPICS if topic in hinted or _topic_present(topic, tokens)][:3]
        return SentimentResult(
            id=comment_id, sentiment=sentiment, score=score, topics=topics
        )

    def _clause_polarity(self, tokens: list[str]) -> tuple[int, int]:
        positive = negative = 0
        skip_next = False
        for index, token in enumerate(tokens):
            if skip_next:
                skip_next = False
                continue
            following = tokens[index + 1] if index + 1 < len(tokens) else None
            if token in EXCESS_MARKERS and following and following not in ALWAYS_GOOD and not _is_negated(tokens, index):
                # "terlalu manis/mahal/lama" complains about too much of
                # something, even when the word itself is positive.
                negative += 1
                skip_next = True
                continue
            if token in PROMO_TERMS:
                continue
            polarity = 1 if token in self.positive else -1 if token in self.negative else 0
            if polarity and _is_negated(tokens, index):
                polarity *= -1
            positive += polarity > 0
            negative += polarity < 0
        return positive, negative
