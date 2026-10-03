"""Test YouTube adapter, payload parsing, relevance filtering, discovery, and classifiers."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import httpx
import pytest

from app.sources.base import Topic
from app.sources.youtube import (
    PublicYouTubeClient,
    YouTubeAdapter,
    YouTubeClient,
    YouTubeError,
    build_query,
    classify_content_type,
    is_relevant,
    parse_count,
    parse_youtube_item,
    parse_youtube_payload,
    relative_datetime,
)


@pytest.fixture
def topic() -> Topic:
    return Topic(
        id="seblak-bandung",
        name="Seblak Bandung",
        keywords=["seblak", "seblak prasmanan"],
        product_terms=["seblak", "kerupuk"],
        exclude_terms=["kartun", "animasi"],
        cities=["Bandung"],
    )


@pytest.fixture
def youtube_fixture() -> list[dict]:
    path = Path(__file__).parent.parent / "fixtures" / "providers" / "youtube.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_parse_youtube_fixture(topic: Topic, youtube_fixture: list[dict]) -> None:
    items = parse_youtube_payload(youtube_fixture, topic)

    # Item 3 is 'Kartun Animasi Anak' which must be filtered out!
    assert len(items) == 2

    first = items[0]
    assert first.id == "youtube:abc123XYZ"
    assert first.source == "youtube"
    assert "RESEP SEBLAK" in (first.title or "")
    assert first.metrics is not None
    assert first.metrics.views == 125000
    assert first.metrics.likes == 4300
    assert first.metrics.comments == 210
    assert first.metadata.get("views_per_day") is not None
    assert first.metadata.get("content_type") == "ide_usaha"

    second = items[1]
    assert second.id == "youtube:def456UVW"
    assert "Review Seblak" in (second.title or "")
    assert second.metrics is not None
    assert second.metrics.views == 45000
    assert second.metrics.comments is None  # Missing in statistics, stays None
    assert second.metadata.get("content_type") == "review"


def test_youtube_adapter_not_configured(topic: Topic) -> None:
    adapter = YouTubeAdapter(client=None, auto_fallback=False)
    result = asyncio.run(adapter.collect(topic))
    assert result.error_code == "not_configured"


# ==================== GROUP B: YOUTUBE REGRESSION TESTS ====================

def test_youtube_is_relevant_product_and_intent(topic: Topic) -> None:
    # 1. Product + Intent = Relevant
    item = {
        "id": "v1",
        "snippet": {
            "title": "Review Produk Seblak Instan Pedas, Rasa dan Harga Murah",
            "channelTitle": "Foodie",
        },
    }
    assert is_relevant(item, topic) is True


def test_youtube_is_relevant_product_without_intent(topic: Topic) -> None:
    # 2. Product without intent = Rejected
    item = {
        "id": "v2",
        "snippet": {
            "title": "Funny animation mentioning seblak once in background",
            "channelTitle": "Random Vids",
        },
    }
    assert is_relevant(item, topic) is False


def test_youtube_is_relevant_intent_without_product(topic: Topic) -> None:
    # 3. Intent without product = Rejected
    item = {
        "id": "v3",
        "snippet": {
            "title": "Review makanan murah enak ide jualan omzet jutaan",
            "channelTitle": "Bisnis Anak Muda",
        },
    }
    assert is_relevant(item, topic) is False


def test_youtube_is_relevant_excluded_term(topic: Topic) -> None:
    # 4. Excluded term active = Rejected even if product and intent are present
    item = {
        "id": "v4",
        "snippet": {
            "title": "Kartun Seblak Lucu Episode 1 Ide Usaha",
            "channelTitle": "Animasi Anak",
        },
    }
    assert is_relevant(item, topic) is False

    # Also builtin exclusion like 'gameplay'
    item_gameplay = {
        "id": "v4b",
        "snippet": {
            "title": "Gameplay terbaru jualan seblak simulator",
            "channelTitle": "Gamer ID",
        },
    }
    assert is_relevant(item_gameplay, topic) is False


def test_youtube_is_relevant_mixed_case_and_slang(topic: Topic) -> None:
    # 5. Mixed case and Indonesian slang normalization
    item = {
        "id": "v5",
        "snippet": {
            "title": "Nyobain SeBLak PaLing RamEEE bgt, hrg Murah!",
            "channelTitle": "Kuliner Nusantara",
        },
    }
    # 'hrg' -> 'harga' (intent), 'RamEEE' -> 'rame' (intent), 'seblak' (product)
    assert is_relevant(item, topic) is True


def test_youtube_is_relevant_signals_in_description_and_channel(topic: Topic) -> None:
    # 6. Product signal in description, intent in title
    item = {
        "id": "v6",
        "snippet": {
            "title": "Review Makanan Pedas Gurih",
            "description": "Hari ini kita mencoba seblak prasmanan di Bandung...",
            "channelTitle": "Vlogger Kuliner",
        },
    }
    assert is_relevant(item, topic) is True

    # 7. Intent in channel, product in title
    item_ch = {
        "id": "v7",
        "snippet": {
            "title": "Seblak Pedas Mantap",
            "description": "Paling enak di daerah ini",
            "channelTitle": "Review Makanan Indonesia",
        },
    }
    assert is_relevant(item_ch, topic) is True


def test_youtube_build_query(topic: Topic) -> None:
    query = build_query(topic)
    assert 'seblak' in query
    assert '"seblak prasmanan"' in query
    assert '-kartun' in query
    assert '-animasi' in query


def test_youtube_parse_count_localized() -> None:
    assert parse_count("12 rb") == 12000
    assert parse_count("1,2 jt") == 1200000
    assert parse_count("3 juta") == 3000000
    assert parse_count("1 miliar") == 1000000000
    assert parse_count("500") == 500
    assert parse_count("2.500") == 2500
    assert parse_count(None) is None
    assert parse_count("") is None


def test_youtube_relative_datetime() -> None:
    now = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Menit
    dt_mnt = relative_datetime("15 menit lalu", now=now)
    assert dt_mnt == now - timedelta(minutes=15)

    # Jam
    dt_jam = relative_datetime("3 jam lalu", now=now)
    assert dt_jam == now - timedelta(hours=3)

    # Hari
    dt_hari = relative_datetime("2 hari lalu", now=now)
    assert dt_hari == now - timedelta(days=2)

    # Minggu
    dt_mgg = relative_datetime("1 mgg lalu", now=now)
    assert dt_mgg == now - timedelta(days=7)

    # Bulan
    dt_bln = relative_datetime("2 bln lalu", now=now)
    assert dt_bln == now - timedelta(days=60)

    # Tahun
    dt_thn = relative_datetime("1 tahun lalu", now=now)
    assert dt_thn == now - timedelta(days=365)


def test_youtube_views_per_day_calculation(topic: Topic) -> None:
    now = datetime.now(timezone.utc)
    published = (now - timedelta(days=10)).isoformat()
    item = {
        "id": "v_vpd",
        "snippet": {
            "title": "Review Seblak Enak Ide Usaha",
            "publishedAt": published,
        },
        "statistics": {
            "viewCount": "10000",
        },
    }
    evidence = parse_youtube_item(item, topic)
    assert evidence is not None
    assert evidence.metrics is not None
    assert evidence.metrics.views == 10000
    # ~1000 views per day
    assert 900 <= evidence.metadata["views_per_day"] <= 1100


def test_youtube_classify_content_type_priority() -> None:
    # Priority: ide_usaha > resep > review > lainnya
    # Has both ide_usaha ('modal') and review ('review')
    assert classify_content_type("Review Seblak dengan Modal 50 Ribu") == "ide_usaha"

    # Has both resep ('cara membuat') and review ('review')
    assert classify_content_type("Review Cara Membuat Seblak Gurih") == "resep"

    # Review only
    assert classify_content_type("Review Jujur Seblak Terpedas") == "review"

    # Lainnya
    assert classify_content_type("Vlog Jalan-Jalan Keliling Kota") == "lainnya"


def test_youtube_client_discovery_passes(topic: Topic) -> None:
    async def _runner() -> None:
        calls: list[str] = []

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            calls.append(url_str)
            if "/search" in url_str:
                if "order=date" in url_str:
                    return httpx.Response(200, json={
                        "items": [{"id": {"videoId": "vid_date_1"}}, {"id": {"videoId": "vid_dup"}}],
                        "nextPageToken": None,
                    })
                if "order=viewCount" in url_str:
                    return httpx.Response(200, json={
                        "items": [{"id": {"videoId": "vid_pop_1"}}, {"id": {"videoId": "vid_dup"}}],
                    })
            if "/videos" in url_str:
                return httpx.Response(200, json={
                    "items": [
                        {
                            "id": "vid_date_1",
                            "snippet": {"title": "Resep Seblak 1", "publishedAt": "2026-09-01T00:00:00Z"},
                            "statistics": {"viewCount": "1000"},
                        },
                        {
                            "id": "vid_pop_1",
                            "snippet": {"title": "Review Seblak Populer", "publishedAt": "2026-09-05T00:00:00Z"},
                            "statistics": {"viewCount": "50000"},
                        },
                        {
                            "id": "vid_dup",
                            "snippet": {"title": "Seblak Ide Usaha", "publishedAt": "2026-09-10T00:00:00Z"},
                            "statistics": {"viewCount": "20000"},
                        },
                    ]
                })
            return httpx.Response(404)

        transport = httpx.MockTransport(mock_handler)
        http_client = httpx.AsyncClient(transport=transport)
        client = YouTubeClient("fake_key", client=http_client)

        items = await client.search(topic, limit=10)
        assert len(items) == 3
        # Ensure date and viewCount calls were both made
        assert any("order=date" in c for c in calls)
        assert any("order=viewCount" in c for c in calls)

        await client.close()

    asyncio.run(_runner())


def test_public_youtube_search_http_failure_raises_provider_error(topic: Topic) -> None:
    """Case 1: Public search HTTP 500 on discovery must raise YouTubeError and return provider_error."""
    async def _runner() -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="Internal Server Error")

        transport = httpx.MockTransport(mock_handler)
        http_client = httpx.AsyncClient(transport=transport)
        client = PublicYouTubeClient(client=http_client)
        adapter = YouTubeAdapter(client=client)

        result = await adapter.collect(topic)
        assert result.error_code == "provider_error"
        assert result.items == []
        assert "500" in (result.message or "")

        await client.close()

    asyncio.run(_runner())


def test_public_youtube_search_malformed_html_raises_provider_error(topic: Topic) -> None:
    """Case 2: Public search HTTP 200 without ytInitialData must return provider_error, not empty result."""
    async def _runner() -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<html><body>No initial data here</body></html>")

        transport = httpx.MockTransport(mock_handler)
        http_client = httpx.AsyncClient(transport=transport)
        client = PublicYouTubeClient(client=http_client)
        adapter = YouTubeAdapter(client=client)

        result = await adapter.collect(topic)
        assert result.error_code == "provider_error"
        assert result.items == []
        assert "ytInitialData" in (result.message or "")

        await client.close()

    asyncio.run(_runner())


def test_public_youtube_one_discovery_pass_failure_raises_provider_error(topic: Topic) -> None:
    """Case 3: If date discovery returns 500 while popularity is 200, propagate provider_error without partial success."""
    async def _runner() -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            if "sp=CAI%3D" in url_str:
                return httpx.Response(500, text="Date discovery failed")
            return httpx.Response(200, text="<html><body>var ytInitialData = {};</body></html>")

        transport = httpx.MockTransport(mock_handler)
        http_client = httpx.AsyncClient(transport=transport)
        client = PublicYouTubeClient(client=http_client)
        adapter = YouTubeAdapter(client=client)

        result = await adapter.collect(topic)
        assert result.error_code == "provider_error"
        assert result.items == []
        assert "date (CAI%3D)" in (result.message or "")

        await client.close()

    asyncio.run(_runner())


def test_public_youtube_watch_page_refresh_failure_falls_back_to_candidate(topic: Topic) -> None:
    """Case 4: Watch-page enrichment failure must NOT fail collection if discovery succeeded."""
    async def _runner() -> None:
        html_search = """
        <html><body><script>
        var ytInitialData = {
            "contents": {
                "twoColumnSearchResultsRenderer": {
                    "primaryContents": {
                        "sectionListRenderer": {
                            "contents": [{
                                "itemSectionRenderer": {
                                    "contents": [{
                                        "videoRenderer": {
                                            "videoId": "cand_vid_1",
                                            "title": {"runs": [{"text": "Review Resep Seblak Enak Ide Jualan"}]},
                                            "ownerText": {"runs": [{"text": "Dapur Seblak"}]},
                                            "viewCountText": {"simpleText": "10 rb x ditonton"},
                                            "publishedTimeText": {"simpleText": "2 hari lalu"}
                                        }
                                    }]
                                }
                            }]
                        }
                    }
                }
            }
        };
        </script></body></html>
        """

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            if "/results" in url_str:
                return httpx.Response(200, text=html_search)
            if "/watch" in url_str:
                return httpx.Response(500, text="Watch page error")
            return httpx.Response(404)

        transport = httpx.MockTransport(mock_handler)
        http_client = httpx.AsyncClient(transport=transport)
        client = PublicYouTubeClient(client=http_client)
        adapter = YouTubeAdapter(client=client)

        result = await adapter.collect(topic)
        assert result.error_code is None
        assert len(result.items) == 1
        ev = result.items[0]
        assert ev.external_id == "cand_vid_1"
        assert "Review Resep Seblak" in (ev.title or "")
        assert ev.metrics is not None
        assert ev.metrics.views == 10000

        await client.close()

    asyncio.run(_runner())
