"""Filter relevansi produk dan penangkal noise untuk produk UMKM Indonesia."""

from __future__ import annotations

import re
from typing import Any

from app.contracts import Evidence, Topic
from app.intelligence.normalize import normalize

COMMERCE_CONTEXT_TERMS: frozenset[str] = frozenset({
    "rasa", "enak", "gurih", "manis", "pedas", "pahit", "asam", "asin",
    "harga", "beli", "jual", "pesan", "order", "warung", "toko", "kedai",
    "kafe", "cafe", "menu", "porsi", "resep", "cara membuat", "minum",
    "makan", "kuliner", "jajan", "jajanan", "umkm", "usaha", "modal",
    "omzet", "franchise", "kemasan", "review", "nyobain", "rekomendasi",
    "diskon", "promo", "langganan", "kualitas", "pelayanan", "produk",
})

DEFAULT_HARD_EXCLUDE: frozenset[str] = frozenset({
    "upin ipin", "kartun", "episode", "animasi", "trailer", "gameplay",
    "anime", "sinetron", "dongeng", "manga",
})


def get_signals(topic: Topic) -> list[str]:
    """Ekstrak dan normalkan seluruh kata sinyal dari topik."""
    values = [topic.name, *topic.keywords, *topic.product_terms]
    signals: list[str] = []
    for val in values:
        norm = normalize(val)
        if norm and norm not in signals:
            signals.append(norm)
    return signals


def contains_signal(text: str, signal: str) -> bool:
    """Periksa keberadaan kata sinyal dengan memperhitungkan klitika Indonesia (-nya, -ku, -mu)."""
    norm_text = normalize(text)
    pattern = rf"(?<!\w){re.escape(signal)}(?:nya|ku|mu)?(?!\w)"
    return bool(re.search(pattern, norm_text))


def mentions_product(text: str, topic: Topic) -> bool:
    """Periksa apakah teks menyebutkan salah satu sinyal produk."""
    signals = get_signals(topic)
    return any(contains_signal(text, sig) for sig in signals)


def has_commerce_context(text: str) -> bool:
    """Periksa apakah teks memiliki konteks konsumsi, pembelian, review, atau UMKM."""
    norm_text = normalize(text)
    tokens = set(norm_text.split())
    return bool(tokens & COMMERCE_CONTEXT_TERMS)


def is_relevant_evidence(
    text: str,
    topic: Topic,
    *,
    threshold: float = 0.5,
) -> tuple[bool, float, str]:
    """Tentukan apakah sebuah teks/konten relevan dengan produk UMKM yang dipantau.

    Mengembalikan tuple: (is_relevant, relevance_score, reason).
    """
    if not text or not text.strip():
        return False, 0.0, "Teks kosong"

    norm_text = normalize(text)

    # 1. Hard exclusion check (misal: kartun, Upin & Ipin, anime, trailer)
    all_excludes = set(DEFAULT_HARD_EXCLUDE) | {
        normalize(term) for term in topic.exclude_terms if normalize(term)
    }
    for exc in all_excludes:
        if exc in norm_text:
            # Jika mengandung kata kartun/hiburan, otomatis tolak kecuali ada bukti review/pembelian UMKM kuat
            return False, 0.1, f"Mengandung istilah yang dikecualikan: '{exc}'"

    # 2. Product signal check
    signals = get_signals(topic)
    matched_signals = [sig for sig in signals if contains_signal(norm_text, sig)]
    if not matched_signals:
        return False, 0.0, "Tidak menyebutkan nama produk atau kata kunci produk"

    # 3. Context validation (commerce, review, kuliner, UMKM)
    commerce_hit = has_commerce_context(norm_text)
    
    # Hitung skor relevansi
    score = 0.6  # Base score jika menyebut produk
    if commerce_hit:
        score += 0.35  # Bonus jika ada konteks review/jual beli UMKM
    if len(matched_signals) > 1:
        score += 0.05

    score = min(1.0, score)
    is_rel = score >= threshold
    reason = "Lolos filter relevansi produk UMKM" if is_rel else "Konteks produk tidak mencukupi"

    return is_rel, score, reason


def filter_relevant_evidence(
    items: list[Evidence],
    topic: Topic,
    *,
    threshold: float = 0.5,
) -> list[Evidence]:
    """Saring daftar evidence dan perbarui relevance_score."""
    relevant_items: list[Evidence] = []
    for item in items:
        combined_text = f"{item.title or ''} {item.text or ''}".strip()
        is_rel, score, _ = is_relevant_evidence(combined_text, topic, threshold=threshold)
        if is_rel:
            item.relevance_score = score
            relevant_items.append(item)
    return relevant_items
