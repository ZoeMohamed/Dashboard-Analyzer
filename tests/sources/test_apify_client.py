"""Test bounded Apify client, token rotation, cooldowns, and error mapping."""

import asyncio
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


def test_apify_401_permission_error() -> None:
    async def _runner() -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": {"message": "Invalid token"}})

        transport = httpx.MockTransport(mock_handler)
        http_client = httpx.AsyncClient(transport=transport)
        client = ApifyClient(tokens=["bad_token"], max_attempts=1, http_client=http_client)

        with pytest.raises(ApifyError) as exc_info:
            await client.run_actor("any-actor", {})
        assert exc_info.value.code == "provider_permission"

        await client.close()

    asyncio.run(_runner())


def test_apify_403_permission_error() -> None:
    async def _runner() -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, json={"error": {"message": "Monthly usage hard limit reached"}})

        transport = httpx.MockTransport(mock_handler)
        http_client = httpx.AsyncClient(transport=transport)
        client = ApifyClient(tokens=["tok_403"], max_attempts=1, http_client=http_client)

        with pytest.raises(ApifyError) as exc_info:
            await client.run_actor("any-actor", {})
        assert exc_info.value.code == "provider_permission"

        await client.close()

    asyncio.run(_runner())


def test_apify_429_budget_exhausted() -> None:
    async def _runner() -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"Retry-After": "30"}, json={"error": {"message": "Rate limited"}})

        transport = httpx.MockTransport(mock_handler)
        http_client = httpx.AsyncClient(transport=transport)
        client = ApifyClient(tokens=["tok_429"], max_attempts=1, http_client=http_client)

        with pytest.raises(ApifyError) as exc_info:
            await client.run_actor("any-actor", {})
        assert exc_info.value.code == "budget_exhausted"

        await client.close()

    asyncio.run(_runner())


def test_apify_500_provider_error() -> None:
    async def _runner() -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"error": {"message": "Internal server error"}})

        transport = httpx.MockTransport(mock_handler)
        http_client = httpx.AsyncClient(transport=transport)
        client = ApifyClient(tokens=["tok_500"], max_attempts=1, http_client=http_client)

        with pytest.raises(ApifyError) as exc_info:
            await client.run_actor("any-actor", {})
        assert exc_info.value.code == "provider_error"

        await client.close()

    asyncio.run(_runner())


def test_apify_request_timeout() -> None:
    async def _runner() -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("Connection timed out")

        transport = httpx.MockTransport(mock_handler)
        http_client = httpx.AsyncClient(transport=transport)
        client = ApifyClient(tokens=["tok_timeout"], max_attempts=1, http_client=http_client)

        with pytest.raises(ApifyError) as exc_info:
            await client.run_actor("any-actor", {})
        assert exc_info.value.code == "provider_timeout"

        await client.close()

    asyncio.run(_runner())


def test_apify_poll_timeout_calls_abort() -> None:
    async def _runner() -> None:
        abort_called: list[str] = []

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            if request.method == "POST" and "/runs" in url_str:
                return httpx.Response(201, json={"data": {"id": "run-timeout-1", "status": "RUNNING"}})
            if request.method == "GET" and "/actor-runs/run-timeout-1" in url_str:
                return httpx.Response(200, json={"data": {"id": "run-timeout-1", "status": "RUNNING"}})
            if request.method == "POST" and "/actor-runs/run-timeout-1/abort" in url_str:
                abort_called.append(url_str)
                return httpx.Response(200, json={"data": {"id": "run-timeout-1", "status": "ABORTING"}})
            return httpx.Response(404)

        transport = httpx.MockTransport(mock_handler)
        http_client = httpx.AsyncClient(transport=transport)
        client = ApifyClient(
            tokens=["mock_token"],
            poll_interval=0.01,
            http_client=http_client,
        )

        with pytest.raises(ApifyError) as exc_info:
            await client.run_actor("any-actor", {}, timeout_seconds=0)

        assert exc_info.value.code == "provider_timeout"
        assert len(abort_called) == 1
        assert "run-timeout-1/abort" in abort_called[0]

        await client.close()

    asyncio.run(_runner())


def test_apify_dataset_failure_raises_error() -> None:
    async def _runner() -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            if request.method == "POST" and "/runs" in url_str:
                return httpx.Response(201, json={"data": {"id": "run-ds-fail", "defaultDatasetId": "ds-fail", "status": "SUCCEEDED"}})
            if request.method == "GET" and "/datasets/ds-fail/items" in url_str:
                return httpx.Response(500, json={"error": "Dataset corrupt"})
            return httpx.Response(404)

        transport = httpx.MockTransport(mock_handler)
        http_client = httpx.AsyncClient(transport=transport)
        client = ApifyClient(tokens=["mock_token"], http_client=http_client)

        with pytest.raises(ApifyError) as exc_info:
            await client.run_actor("any-actor", {})

        # Dataset failure must NOT return empty items, must raise provider_error
        assert exc_info.value.code == "provider_error"

        await client.close()

    asyncio.run(_runner())


def test_apify_malformed_response() -> None:
    async def _runner() -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            if request.method == "POST" and "/runs" in url_str:
                return httpx.Response(400, text="Bad Request: invalid JSON input")
            return httpx.Response(404)

        transport = httpx.MockTransport(mock_handler)
        http_client = httpx.AsyncClient(transport=transport)
        client = ApifyClient(tokens=["mock_token"], http_client=http_client)

        with pytest.raises(ApifyError) as exc_info:
            await client.run_actor("any-actor", {})

        assert exc_info.value.code == "invalid_payload"

        await client.close()

    asyncio.run(_runner())


def test_apify_invalid_input_keeps_apify_reason() -> None:
    async def _runner() -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"error": {"type": "invalid-input", "message": "Input is not valid: Field input.country must be equal to one of the allowed values"}})

        http_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
        client = ApifyClient(tokens=["mock_token"], http_client=http_client)
        with pytest.raises(ApifyError) as exc_info:
            await client.run_actor("any-actor", {})
        assert exc_info.value.code == "invalid_payload"
        assert "input.country" in exc_info.value.message
        await client.close()

    asyncio.run(_runner())
