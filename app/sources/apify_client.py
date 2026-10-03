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
    "ABORTING",
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
            elif start_resp.status_code >= 500:
                last_error = ApifyError("provider_error", f"Apify server error (HTTP {start_resp.status_code}).")
                continue
            elif start_resp.status_code >= 400:
                # Apify explains rejected input (for example an enum value the
                # actor schema does not allow); keep that reason for the run log.
                try:
                    detail = str(start_resp.json().get("error", {}).get("message") or "")[:300]
                except ValueError:
                    detail = ""
                last_error = ApifyError("invalid_payload", f"Apify merespons status {start_resp.status_code}." + (f" {detail}" if detail else ""))
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
            consecutive_poll_errors = 0

            while run_status not in TERMINAL_STATUSES:
                now_poll = datetime.now(timezone.utc).timestamp()
                if (now_poll - start_poll) > timeout_seconds:
                    await self.abort_run(run_id, token)
                    raise ApifyError(
                        "provider_timeout",
                        f"Polling actor run {run_id} melebihi batas {timeout_seconds} detik.",
                    )

                await asyncio.sleep(self.poll_interval)
                try:
                    poll_resp = await client.get(status_url, headers=headers)
                    if poll_resp.status_code == 200:
                        consecutive_poll_errors = 0
                        poll_data = poll_resp.json().get("data", {})
                        run_status = poll_data.get("status", "RUNNING")
                        if not dataset_id:
                            dataset_id = poll_data.get("defaultDatasetId")
                    elif poll_resp.status_code in (401, 403):
                        self._mark_quarantine(token)
                        raise ApifyError(
                            "provider_permission",
                            f"Izin token Apify ditolak saat polling (HTTP {poll_resp.status_code}).",
                        )
                    elif poll_resp.status_code == 429:
                        self._mark_cooldown(token)
                        raise ApifyError("budget_exhausted", "Apify rate limit saat polling (HTTP 429).")
                    elif poll_resp.status_code >= 500:
                        consecutive_poll_errors += 1
                        if consecutive_poll_errors >= 3:
                            raise ApifyError(
                                "provider_error",
                                f"Apify server error saat polling (HTTP {poll_resp.status_code}).",
                            )
                        await asyncio.sleep(min(self.poll_interval * (2 ** consecutive_poll_errors), 5.0))
                except ApifyError:
                    raise
                except httpx.TimeoutException as exc:
                    consecutive_poll_errors += 1
                    if consecutive_poll_errors >= 3:
                        raise ApifyError(
                            "provider_timeout",
                            f"Polling actor run {run_id} timeout berulang kali.",
                        ) from exc
                    await asyncio.sleep(min(self.poll_interval * (2 ** consecutive_poll_errors), 5.0))
                except (httpx.TransportError, Exception) as exc:
                    consecutive_poll_errors += 1
                    if consecutive_poll_errors >= 3:
                        raise ApifyError(
                            "provider_error",
                            f"Polling actor run {run_id} gagal setelah retry berulang: {exc}",
                        ) from exc
                    await asyncio.sleep(min(self.poll_interval * (2 ** consecutive_poll_errors), 5.0))

            if run_status != "SUCCEEDED":
                raise ApifyError("provider_error", f"Actor run {run_id} selesai dengan status '{run_status}'.")

            # 3. Fetch dataset items with bounded retry
            if not dataset_id:
                raise ApifyError("provider_error", f"Actor run {run_id} tidak memiliki defaultDatasetId.")

            dataset_url = f"{APIFY_API_ROOT}/datasets/{dataset_id}/items"
            items_resp = None
            max_ds_attempts = 3
            for ds_attempt in range(max_ds_attempts):
                try:
                    items_resp = await client.get(
                        dataset_url,
                        headers=headers,
                        params={"clean": "true", "format": "json", "limit": limit},
                    )
                except httpx.TimeoutException as exc:
                    if ds_attempt == max_ds_attempts - 1:
                        raise ApifyError("provider_timeout", f"Timeout saat mengambil dataset {dataset_id}.") from exc
                    await asyncio.sleep(2 ** ds_attempt)
                    continue
                except httpx.TransportError as exc:
                    if ds_attempt == max_ds_attempts - 1:
                        raise ApifyError("provider_error", f"Network error saat mengambil dataset {dataset_id}: {exc}") from exc
                    await asyncio.sleep(2 ** ds_attempt)
                    continue

                if items_resp.status_code in (401, 403):
                    self._mark_quarantine(token)
                    raise ApifyError(
                        "provider_permission",
                        f"Izin token Apify ditolak saat mengambil dataset (HTTP {items_resp.status_code}).",
                    )
                if items_resp.status_code == 429:
                    self._mark_cooldown(token)
                    if ds_attempt == max_ds_attempts - 1:
                        raise ApifyError("budget_exhausted", "Apify rate limit saat mengambil dataset (HTTP 429).")
                    await asyncio.sleep(2 ** ds_attempt)
                    continue
                if items_resp.status_code >= 500:
                    if ds_attempt == max_ds_attempts - 1:
                        raise ApifyError(
                            "provider_error",
                            f"Gagal mengambil dataset {dataset_id}: HTTP {items_resp.status_code}",
                        )
                    await asyncio.sleep(2 ** ds_attempt)
                    continue
                break

            if items_resp is None or items_resp.status_code >= 400:
                code_str = str(items_resp.status_code) if items_resp else "Unknown"
                raise ApifyError(
                    "provider_error",
                    f"Gagal mengambil dataset {dataset_id}: HTTP {code_str}",
                )

            try:
                items_json = items_resp.json()
            except Exception as exc:
                raise ApifyError("invalid_payload", f"Respons dataset bukan JSON valid: {exc}")

            if isinstance(items_json, list):
                items = [item for item in items_json if isinstance(item, dict)]
            elif isinstance(items_json, dict) and isinstance(items_json.get("data"), list):
                items = [item for item in items_json["data"] if isinstance(item, dict)]
            else:
                raise ApifyError("invalid_payload", "Dataset items bukan berupa JSON list.")

            return {
                "run_id": run_id,
                "dataset_id": dataset_id,
                "items": items,
            }

        if last_error:
            raise last_error
        raise ApifyError("provider_error", "Gagal mengeksekusi Actor Apify setelah batas percobaan.")

    async def abort_run(self, run_id: str, token: str | None = None) -> None:
        """Abort an active actor run using POST /actor-runs/{run_id}/abort."""
        tok = token or (self.tokens[0] if self.tokens else None)
        if not tok:
            return
        client = self._get_client()
        url = f"{APIFY_API_ROOT}/actor-runs/{run_id}/abort"
        headers = {"Authorization": f"Bearer {tok}", "Accept": "application/json"}
        try:
            await client.post(url, headers=headers)
        except Exception:
            logger.warning("Gagal meng-abort actor run %s", run_id)

