"""Bounded Apify HTTP client with token pool rotation, cooldown, and error isolation."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any
import httpx

from .base import SourceErrorCode

logger = logging.getLogger(__name__)

APIFY_API_ROOT = "https://api.apify.com/v2"
TERMINAL_STATUSES = {
    "SUCCEEDED",
    "FAILED",
    "TIMING-OUT",
    "TIMED-OUT",
    "ABORTED",
}


class ApifyError(Exception):
    """Base Apify client exception with standardized error code."""

    def __init__(self, code: SourceErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ApifyClient:
    """Bounded, token-rotating Apify client for Dashboard Analyzer."""

    def __init__(
        self,
        tokens: list[str] | None = None,
        *,
        max_attempts: int = 4,
        cooldown_seconds: int = 300,
        poll_interval: float = 2.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.tokens = self._parse_tokens(tokens)
        self.max_attempts = max_attempts
        self.cooldown_seconds = cooldown_seconds
        self.poll_interval = poll_interval
        self._http_client = http_client
        self._owns_client = http_client is None
        self._token_index = 0
        self._cooldowns: dict[str, float] = {}  # token -> cooldown expiry timestamp
        self._quarantined: set[str] = set()

    @staticmethod
    def _parse_tokens(tokens: list[str] | None) -> list[str]:
        if tokens:
            cleaned = [t.strip() for t in tokens if t and t.strip()]
            return list(dict.fromkeys(cleaned))

        raw_pool = os.getenv("APIFY_TOKENS") or ""
        raw_single = os.getenv("APIFY_TOKEN") or ""
        combined = [t.strip() for t in raw_pool.split(",") if t.strip()]
        if raw_single.strip() and raw_single.strip() not in combined:
            combined.append(raw_single.strip())

        return list(dict.fromkeys(combined))

    @property
    def has_tokens(self) -> bool:
        return len(self.tokens) > 0

    def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
        return self._http_client

    async def close(self) -> None:
        if self._owns_client and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    def _get_next_token(self) -> str:
        """Select a healthy token from pool using round-robin and respecting cooldown."""
        if not self.tokens:
            raise ApifyError(
                "not_configured", "Tidak ada APIFY_TOKENS atau APIFY_TOKEN yang dikonfigurasi."
            )

        now = datetime.now(timezone.utc).timestamp()
        available_tokens = [
            t for t in self.tokens
            if t not in self._quarantined and self._cooldowns.get(t, 0) <= now
        ]

        if not available_tokens:
            # Check if all are quarantined
            if len(self._quarantined) >= len(self.tokens):
                raise ApifyError(
                    "provider_permission", "Semua token Apify ditolak atau tidak memiliki izin."
                )
            # All available are in cooldown
            min_cooldown = min(self._cooldowns.values()) if self._cooldowns else now
            wait_time = max(1.0, min_cooldown - now)
            raise ApifyError(
                "budget_exhausted",
                f"Seluruh token Apify sedang dalam cooldown. Coba lagi setelah {int(wait_time)} detik.",
            )

        selected = available_tokens[self._token_index % len(available_tokens)]
        self._token_index = (self._token_index + 1) % len(available_tokens)
        return selected

    def _mark_cooldown(self, token: str, custom_seconds: int | None = None) -> None:
        seconds = custom_seconds or self.cooldown_seconds
        now = datetime.now(timezone.utc).timestamp()
        self._cooldowns[token] = now + seconds

    def _mark_quarantine(self, token: str) -> None:
        self._quarantined.add(token)

    async def run_actor(
        self,
        actor_id: str,
        actor_input: dict[str, Any],
        *,
        timeout_seconds: int = 120,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Start actor run, poll until complete, and fetch dataset items."""
        client = self._get_client()
        attempts = 0
        last_error: ApifyError | None = None

        while attempts < self.max_attempts:
            attempts += 1
            try:
                token = self._get_next_token()
            except ApifyError as exc:
                raise exc

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

            # 1. Start Actor run
            start_url = f"{APIFY_API_ROOT}/acts/{actor_id}/runs"
            try:
                start_resp = await client.post(start_url, json=actor_input, headers=headers)
            except httpx.TimeoutException:
                last_error = ApifyError("provider_timeout", f"Timeout saat memulai actor {actor_id}.")
                continue
            except httpx.TransportError as exc:
                last_error = ApifyError("provider_error", f"Network error saat menghubungi Apify: {exc}")
                continue

            if start_resp.status_code == 429:
                retry_after = start_resp.headers.get("Retry-After")
                cd = int(retry_after) if retry_after and retry_after.isdigit() else self.cooldown_seconds
                self._mark_cooldown(token, cd)
                last_error = ApifyError("budget_exhausted", "Apify rate limit (HTTP 429).")
                continue
            elif start_resp.status_code in (401, 403):
                self._mark_quarantine(token)
                last_error = ApifyError("provider_permission", f"Izin token Apify ditolak (HTTP {start_resp.status_code}).")
                continue
            elif start_resp.status_code >= 400:
                last_error = ApifyError("invalid_payload", f"Apify merespons status {start_resp.status_code}.")
                raise last_error

            start_data = start_resp.json().get("data", {})
            run_id = start_data.get("id")
            dataset_id = start_data.get("defaultDatasetId")
            if not run_id:
                raise ApifyError("invalid_payload", "Respon Apify tidak memiliki ID run.")

            # 2. Poll until terminal status
            status_url = f"{APIFY_API_ROOT}/actor-runs/{run_id}"
            start_poll = datetime.now(timezone.utc).timestamp()
            run_status = start_data.get("status", "RUNNING")

            while run_status not in TERMINAL_STATUSES:
                now_poll = datetime.now(timezone.utc).timestamp()
                if (now_poll - start_poll) > timeout_seconds:
                    raise ApifyError("provider_timeout", f"Polling actor run {run_id} melebihi batas {timeout_seconds} detik.")

                await asyncio.sleep(self.poll_interval)
                try:
                    poll_resp = await client.get(status_url, headers=headers)
                    if poll_resp.status_code == 200:
                        run_status = poll_resp.json().get("data", {}).get("status", "RUNNING")
                        if not dataset_id:
                            dataset_id = poll_resp.json().get("data", {}).get("defaultDatasetId")
                except Exception:
                    # Ignore transient polling network drops
                    pass

            if run_status != "SUCCEEDED":
                raise ApifyError("provider_error", f"Actor run {run_id} selesai dengan status '{run_status}'.")

            # 3. Fetch dataset items
            dataset_url = f"{APIFY_API_ROOT}/datasets/{dataset_id}/items?limit={limit}"
            items_resp = await client.get(dataset_url, headers=headers)
            items = items_resp.json() if items_resp.status_code == 200 else []
            if not isinstance(items, list):
                items = []

            return {
                "run_id": run_id,
                "dataset_id": dataset_id,
                "items": items,
            }

        if last_error:
            raise last_error
        raise ApifyError("provider_error", "Gagal mengeksekusi Actor Apify setelah batas percobaan.")
