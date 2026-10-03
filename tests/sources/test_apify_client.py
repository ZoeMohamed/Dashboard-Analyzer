"""Test bounded Apify client, token rotation, cooldowns, and error mapping."""

import json
import httpx
import pytest
from app.sources.apify_client import ApifyClient, ApifyError


def test_token_parsing_and_deduplication() -> None:
    client = ApifyClient(tokens=["token_a", "token_b", "token_a", "  token_c  ", ""])
    assert client.tokens == ["token_a", "token_b", "token_c"]
    assert client.has_tokens is True

    empty_client = ApifyClient(tokens=[])
    assert empty_client.has_tokens is False


def test_round_robin_token_selection() -> None:
    client = ApifyClient(tokens=["tok1", "tok2"])
    assert client._get_next_token() == "tok1"
    assert client._get_next_token() == "tok2"
    assert client._get_next_token() == "tok1"


def test_token_cooldown_and_quarantine() -> None:
    client = ApifyClient(tokens=["tok1", "tok2"], cooldown_seconds=60)
    
    # Mark tok1 as cooldown
    client._mark_cooldown("tok1")
    # Now only tok2 should be returned
    assert client._get_next_token() == "tok2"
    assert client._get_next_token() == "tok2"

    # Quarantine tok2
    client._mark_quarantine("tok2")
    # Now tok1 is on cooldown and tok2 is quarantined -> budget_exhausted
    with pytest.raises(ApifyError) as exc_info:
        client._get_next_token()
    assert exc_info.value.code == "budget_exhausted"


import asyncio

def test_mock_apify_run_success() -> None:
    async def _runner() -> None:
        calls: list[str] = []
        statuses = iter([
            {"data": {"id": "run-test-1", "defaultDatasetId": "ds-test-1", "status": "RUNNING"}},
            {"data": {"id": "run-test-1", "defaultDatasetId": "ds-test-1", "status": "SUCCEEDED"}},
        ])

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            calls.append(f"{request.method} {url_str}")
            assert request.headers["authorization"] == "Bearer mock_token"

            if request.method == "POST" and "/acts/clockworks~tiktok-scraper/runs" in url_str:
                return httpx.Response(201, json=next(statuses))
            if request.method == "GET" and "/actor-runs/run-test-1" in url_str:
                return httpx.Response(200, json=next(statuses))
            if request.method == "GET" and "/datasets/ds-test-1/items" in url_str:
                return httpx.Response(200, json=[{"id": "item1", "text": "Seblak enak"}])
            return httpx.Response(404)

        transport = httpx.MockTransport(mock_handler)
        http_client = httpx.AsyncClient(transport=transport)

        client = ApifyClient(
            tokens=["mock_token"],
            poll_interval=0.001,
            http_client=http_client,
        )

        result = await client.run_actor(
            "clockworks~tiktok-scraper",
            {"searchQueries": ["seblak"]},
            timeout_seconds=5,
        )

        assert result["run_id"] == "run-test-1"
        assert result["dataset_id"] == "ds-test-1"
        assert len(result["items"]) == 1
        assert result["items"][0]["id"] == "item1"

        await client.close()

    asyncio.run(_runner())
