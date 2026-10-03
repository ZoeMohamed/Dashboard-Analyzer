"""Intelligence, relevance, and sentiment analysis module for Dashboard Analyzer."""

from .normalize import normalize, tokenize
from .relevance import is_relevant_evidence, mentions_product, filter_relevant_evidence
from .sentiment import LexiconAnalyzer, extract_aspects, top_keywords

__all__ = [
    "normalize",
    "tokenize",
    "is_relevant_evidence",
    "mentions_product",
    "filter_relevant_evidence",
    "LexiconAnalyzer",
    "extract_aspects",
    "top_keywords",
]
