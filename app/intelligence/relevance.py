"""Product relevance rules for Google Maps places and reviews."""

from __future__ import annotations

import re

from app.models import Topic
from app.nlp.preprocess import normalize
from app.maps.parsing import ParsedPlace


def _signals(topic: Topic) -> list[str]:
    values = [topic.name, *topic.product_terms, *topic.keywords]
    return list(dict.fromkeys(normalize(value) for value in values if normalize(value)))


def _contains(text: str, signals: list[str]) -> bool:
    normalized = normalize(text)
    # Indonesian reviews frequently attach possessive/emphasis clitics to the
    # product term ("cincaunya", "rasaku"). Treat those as the same word while
    # retaining whole-phrase boundaries to avoid unrelated substring matches.
    return any(
        re.search(rf"(?<!\w){re.escape(signal)}(?:nya|ku|mu)?(?!\w)", normalized)
        for signal in signals
    )


def mentions_product(text: str, topic: Topic) -> bool:
    return _contains(text, _signals(topic))


def is_relevant_evidence(text: str, topic: Topic) -> bool:
    """Deterministic product gate from docs/SYSTEM.md section 5.

    Exclude terms always reject. A full keyword or the topic name accepts.
    Otherwise enough distinct product terms must appear: two, or the only one
    when the topic has a single term. A lone generic term such as "pedas" or
    "level" is not enough to treat an unrelated post as product evidence.
    """

    if any(_contains(text, [normalize(term)]) for term in topic.exclude_terms if normalize(term)):
        return False
    phrases = [normalize(value) for value in [topic.name, *topic.keywords] if normalize(value)]
    if _contains(text, phrases):
        return True
    terms = list(dict.fromkeys(normalize(value) for value in topic.product_terms if normalize(value)))
    hits = sum(1 for term in terms if _contains(text, [term]))
    return hits >= min(2, len(terms)) if terms else False


def place_relevance(place: ParsedPlace, topic: Topic) -> tuple[bool, bool, list[bool]]:
    """Return (relevant, name_mentions_product, review_mentions)."""

    signals = _signals(topic)
    name_hit = _contains(place.name, signals)
    review_hits = [_contains(review.text, signals) for review in place.reviews]
    excluded = any(_contains(place.name, [normalize(term)]) for term in topic.exclude_terms)
    # A place can be discovered through its category/name or through a review
    # that explicitly discusses the product. Permanently closed businesses are
    # retained only as non-relevant history.
    closed = (place.business_status or "").upper() in {"CLOSED_PERMANENTLY", "CLOSED"}
    relevant = not closed and not excluded and (name_hit or any(review_hits))
    return relevant, name_hit, review_hits
