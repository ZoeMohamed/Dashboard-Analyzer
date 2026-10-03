"""Penganalisis sentimen berbasis Gemini LLM dengan parser terstruktur dan fallback aman."""

from __future__ import annotations

import json
from typing import Any, Literal
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ValidationError

from app.contracts import Analysis, SentimentLabel
from app.intelligence.sentiment import LexiconAnalyzer

SYSTEM_PROMPT = """Kamu adalah analis sentimen untuk produk UMKM Indonesia.
Pahami bahasa gaul, slang, ejaan tidak baku, emoji, konteks promosi, dan negasi retoris.
Untuk setiap teks, tentukan sentimen penulis TERHADAP PRODUK:
"positif", "negatif", atau "netral".
Negasi retoris seperti "siapa sih yang nggak suka es ini?" bernilai POSITIF.
"sc" adalah skor dari -1.0 (sangat negatif) sampai 1.0 (sangat positif).
"tp" berisi maksimal 3 aspek (contoh: harga, rasa, kemasan, pengiriman, porsi, kualitas).
Kembalikan JSON array dengan satu objek per komentar."""


class BatchItem(BaseModel):
    i: str
    s: Literal["positif", "negatif", "netral"]
    sc: float
    tp: list[str] = Field(default_factory=list)


def parse_gemini_payload(response: Any) -> list[dict[str, Any]]:
    """Ubah respons mentah Gemini menjadi list objek dictionary."""
    if hasattr(response, "text"):
        raw_text = response.text
    elif isinstance(response, (str, bytes)):
        raw_text = response.decode("utf-8") if isinstance(response, bytes) else response
    elif isinstance(response, list):
        return response
    elif isinstance(response, dict):
        return response.get("items", response.get("results", []))
    else:
        raw_text = str(response)

    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        raw_text = "\n".join(lines[1:-1]).strip()

    try:
        data = json.loads(raw_text)
        if isinstance(data, dict):
            data = data.get("items", data.get("results", []))
        if isinstance(data, list):
            return data
        raise ValueError("Respons JSON bukan bertipe list")
    except Exception as exc:
        raise ValueError(f"Gagal mem-parse JSON Gemini: {exc}") from exc


def parse_response(
    raw_response: Any,
    short_to_original: dict[str, str],
) -> list[Analysis]:
    """Validasi respons Gemini dan petakan ID pendek (c1..cN) ke Evidence ID asli."""
    items_data = parse_gemini_payload(raw_response)
    results: list[Analysis] = []
    seen: set[str] = set()

    for raw in items_data:
        if not isinstance(raw, dict):
            continue
        short_id = raw.get("i")
        if not short_id or short_id not in short_to_original or short_id in seen:
            continue
        try:
            validated = BatchItem.model_validate(raw)
        except ValidationError:
            continue

        seen.add(short_id)
        original_id = short_to_original[short_id]

        label = {
            "positif": SentimentLabel.POSITIF,
            "negatif": SentimentLabel.NEGATIF,
            "netral": SentimentLabel.NETRAL,
        }.get(validated.s, SentimentLabel.NETRAL)

        aspects = [str(a).strip().lower() for a in validated.tp if str(a).strip()][:3]

        results.append(
            Analysis(
                evidence_id=original_id,
                label=label,
                score=max(-1.0, min(1.0, float(validated.sc))),
                confidence=0.92,
                aspects=aspects,
                analyzer="gemini",
                analyzed_at=datetime.now(timezone.utc),
            )
        )
    return results


class GeminiAnalyzer:
    """Analyzer Gemini dengan fallback otomatis ke LexiconAnalyzer jika API offline/kuota habis."""

    name = "gemini"

    def __init__(
        self,
        api_keys: list[str] | None = None,
        model: str = "gemini-2.0-flash",
    ) -> None:
        self.api_keys = api_keys or []
        self.model = model
        self.fallback_analyzer = LexiconAnalyzer()

    async def analyze(
        self,
        items: list[tuple[str, str]],
    ) -> list[Analysis]:
        """Analisis batch teks. Jika Gemini gagal atau belum dikonfigurasi, gunakan fallback leksikon."""
        if not items:
            return []

        if not self.api_keys:
            # Belum ada API key, gunakan leksikon lokal
            return self.fallback_analyzer.analyze_batch(items)

        short_to_original = {
            f"c{idx}": evidence_id for idx, (evidence_id, _) in enumerate(items, start=1)
        }
        
        try:
            # Simulasi atau panggilan client riil jika ada modul google-genai
            from google import genai  # type: ignore
            client = genai.Client(api_key=self.api_keys[0])
            compact_items = [
                {"i": f"c{idx}", "t": text}
                for idx, (_, text) in enumerate(items, start=1)
            ]
            prompt = json.dumps(compact_items, ensure_ascii=False)
            response = await client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
            )
            return parse_response(response, short_to_original)
        except Exception:
            # Fallback jika terjadi error kuota, network, atau invalid payload
            return self.fallback_analyzer.analyze_batch(items)
