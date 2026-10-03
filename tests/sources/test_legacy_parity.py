"""Comprehensive legacy parity tests covering revisi.md specifications for all sources."""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import httpx
import pytest

from app.sources.apify_client import ApifyClient, ApifyError
from app.sources.base import CollectionResult, Evidence, Topic
from app.sources.youtube import (
    PublicYouTubeClient,
    YouTubeAdapter,
    YouTubeClient,
    YouTubeError,
    build_query,
    parse_youtube_item,
    parse_youtube_payload,
)
from app.sources.maps import (
    MapsAdapter,
    build_maps_input,
    parse_maps_payload,
    parse_maps_place_items,
)
from app.sources.shopee import (
    ShopeeAdapter,
    build_shopee_input,
    parse_shopee_item,
    parse_shopee_payload,
)
from app.sources.tiktok import (
    TikTokAdapter,
    build_tiktok_input,
    parse_tiktok_item,
    parse_tiktok_payload,
)
from app.sources.instagram import (
    InstagramAdapter,
    build_instagram_input,
    parse_instagram_item,
    parse_instagram_payload,
)
from app.sources.facebook import (
    FacebookAdapter,
    build_facebook_input,
    parse_facebook_item,
    parse_facebook_payload,
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


# ==============================================================================
# SECTION 1: YOUTUBE API ERROR SEMANTICS & BOUNDED RETRIES
# ==============================================================================

def test_youtube_api_401_raises_provider_permission(topic: Topic) -> None:
    """Section 6: HTTP 401 must raise YouTubeError with provider_permission."""
    async def _test() -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, text="API key invalid")

        client = YouTubeClient("bad_key", client=httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)))
        adapter = YouTubeAdapter(client=client)
        result = await adapter.collect(topic)
        assert result.error_code == "provider_permission"
        assert result.items == []

    asyncio.run(_test())


def test_youtube_api_403_quota_exceeded_raises_budget_exhausted(topic: Topic) -> None:
    """Section 6: HTTP 403 quotaExceeded must raise YouTubeError with budget_exhausted."""
    async def _test() -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                403,
                json={
                    "error": {
                        "errors": [{"reason": "quotaExceeded", "message": "The request cannot be completed"}],
                        "message": "The request cannot be completed because you have exceeded your quota.",
                    }
                },
            )

        client = YouTubeClient("key", client=httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)))
        adapter = YouTubeAdapter(client=client)
        result = await adapter.collect(topic)
        assert result.error_code == "budget_exhausted"
        assert "quota" in (result.message or "").lower()

    asyncio.run(_test())


def test_youtube_api_403_daily_limit_exceeded_raises_budget_exhausted(topic: Topic) -> None:
    """Section 6: HTTP 403 dailyLimitExceeded must map to budget_exhausted."""
    async def _test() -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                403,
                json={"error": {"errors": [{"reason": "dailyLimitExceeded"}], "message": "Daily limit"}},
            )

        client = YouTubeClient("key", client=httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)))
        adapter = YouTubeAdapter(client=client)
        result = await adapter.collect(topic)
        assert result.error_code == "budget_exhausted"

    asyncio.run(_test())


def test_youtube_api_403_generic_permission_raises_provider_permission(topic: Topic) -> None:
    """Section 6: HTTP 403 generic permission must map to provider_permission."""
    async def _test() -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                403,
                json={"error": {"errors": [{"reason": "accessNotConfigured"}], "message": "API not enabled"}},
            )

        client = YouTubeClient("key", client=httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)))
        adapter = YouTubeAdapter(client=client)
        result = await adapter.collect(topic)
        assert result.error_code == "provider_permission"

    asyncio.run(_test())


def test_youtube_api_429_raises_budget_exhausted(topic: Topic) -> None:
    """Section 6: HTTP 429 must map to budget_exhausted."""
    async def _test() -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, text="Too Many Requests")

        client = YouTubeClient("key", client=httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)))
        adapter = YouTubeAdapter(client=client)
        result = await adapter.collect(topic)
        assert result.error_code == "budget_exhausted"

    asyncio.run(_test())


def test_youtube_api_500_retries_and_raises_provider_error(topic: Topic) -> None:
    """Section 6: HTTP 500 must retry bounded (3 attempts) then return provider_error."""
    async def _test() -> None:
        attempts = 0

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            return httpx.Response(500, text="Internal Server Error")

        client = YouTubeClient("key", client=httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)))
        adapter = YouTubeAdapter(client=client)
        result = await adapter.collect(topic)
        assert attempts == 3
        assert result.error_code == "provider_error"

    asyncio.run(_test())


def test_youtube_safesearch_and_lookback_params(topic: Topic) -> None:
    """Section 7 & 10: safeSearch='moderate' and lookback_days default 90."""
    async def _test() -> None:
        captured_params: list[dict] = []

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            captured_params.append(dict(request.url.params))
            if "/search" in str(request.url):
                return httpx.Response(200, json={"items": [{"id": {"videoId": "v1"}}], "nextPageToken": None})
            return httpx.Response(200, json={"items": []})

        client = YouTubeClient("key", client=httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)))
        now = datetime(2026, 10, 3, 12, 0, 0, tzinfo=timezone.utc)
        await client.search(topic, limit=10, now=now)

        assert len(captured_params) >= 2
        for params in captured_params[:2]:
            assert params.get("safeSearch") == "moderate"
            assert "publishedAfter" in params
            published_after = datetime.fromisoformat(params["publishedAfter"].replace("Z", "+00:00"))
            # Expected 90 days lookback
            expected_cutoff = now - timedelta(days=90)
            assert abs((published_after - expected_cutoff).total_seconds()) < 5

    asyncio.run(_test())


def test_youtube_candidate_video_cutoff_rejection(topic: Topic) -> None:
    """Section 7.2: Candidate video older than cutoff is rejected."""
    now = datetime(2026, 10, 3, 12, 0, 0, tzinfo=timezone.utc)
    # Old video: 120 days ago (outside 90 days lookback)
    old_date = (now - timedelta(days=120)).isoformat()
    # Recent video: 10 days ago (inside lookback)
    recent_date = (now - timedelta(days=10)).isoformat()

    items = [
        {
            "id": "v_old",
            "snippet": {
                "title": "Resep Seblak Lama",
                "description": "seblak pedas enak",
                "channelTitle": "Chef",
                "publishedAt": old_date,
            },
            "statistics": {"viewCount": "1000"},
        },
        {
            "id": "v_new",
            "snippet": {
                "title": "Review Seblak Baru",
                "description": "seblak prasmanan",
                "channelTitle": "Foodie",
                "publishedAt": recent_date,
            },
            "statistics": {"viewCount": "2000"},
        },
    ]

    results = parse_youtube_payload(items, topic, limit=10, lookback_days=90, now=now)
    assert len(results) == 1
    assert results[0].external_id == "v_new"


def test_youtube_public_scraper_cutoff_rejection(topic: Topic) -> None:
    """Section 8: Public scraper discards video older than configured lookback (e.g. '2 bulan lalu')."""
    async def _test() -> None:
        now = datetime(2026, 10, 3, 12, 0, 0, tzinfo=timezone.utc)

        html_response = """
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
                                            "videoId": "pub_old_vid",
                                            "title": {"runs": [{"text": "Review Seblak Enak"}]},
                                            "ownerText": {"runs": [{"text": "Foodie"}]},
                                            "viewCountText": {"simpleText": "10 rb x ditonton"},
                                            "publishedTimeText": {"simpleText": "2 bulan lalu"}
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
            return httpx.Response(200, text=html_response)

        client = PublicYouTubeClient(client=httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)))
        # With lookback_days=30, '2 bulan lalu' (~60 days) must be rejected
        items = await client.search(topic, limit=10, lookback_days=30, refresh_watch_page=False, now=now)
        assert items == []

    asyncio.run(_test())


def test_youtube_public_watch_page_refresh() -> None:
    """Section 9: Watch page parses ytInitialPlayerResponse to refresh details."""
    async def _test() -> None:
        now = datetime(2026, 10, 3, 12, 0, 0, tzinfo=timezone.utc)
        watch_html = """
        <html><body><script>
        var ytInitialPlayerResponse = {
            "videoDetails": {
                "title": "Refreshed Seblak Title",
                "author": "Chef Terkenal",
                "channelId": "UC12345",
                "viewCount": "500000",
                "shortDescription": "Deskripsi seblak prasmanan lengkap"
            },
            "microformat": {
                "playerMicroformatRenderer": {
                    "publishDate": "2026-10-01T10:00:00Z"
                }
            }
        };
        </script></body></html>
        """

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=watch_html)

        client = PublicYouTubeClient(client=httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)))
        base_item = {
            "id": "watch_vid_1",
            "snippet": {"title": "Old Title", "channelTitle": "Old Author", "publishedAt": "2026-09-01T00:00:00Z"},
            "statistics": {"viewCount": 100},
        }

        refreshed = await client._fetch_watch_page("watch_vid_1", now, base_item)
        assert refreshed["snippet"]["title"] == "Refreshed Seblak Title"
        assert refreshed["snippet"]["channelTitle"] == "Chef Terkenal"
        assert refreshed["snippet"]["publishedAt"] == "2026-10-01T10:00:00Z"
        assert refreshed["statistics"]["viewCount"] == 500000

    asyncio.run(_test())


# ==============================================================================
# SECTION 2: MAPS RELEVANCE GATING & PROVIDER BOUND
# ==============================================================================

def test_maps_strict_relevance_gating(topic: Topic) -> None:
    """Section 16: Place without name hit and without review hits produces 0 items."""
    irrelevant_place = {
        "placeId": "p_irrelevant",
        "title": "Bengkel Motor Berkah",
        "reviews": [
            {"reviewId": "r1", "text": "Ganti oli cepat dan ramah"},
            {"reviewId": "r2", "text": "Ruang tunggu nyaman ber-AC"},
        ],
    }
    assert parse_maps_place_items(irrelevant_place, topic) == []

    # Place with review hit generates place summary + matching review
    review_hit_place = {
        "placeId": "p_warung",
        "title": "Warung Makan Barokah",
        "reviews": [
            {"reviewId": "r1", "text": "Seblaknya enak banget kuah pedas"},
            {"reviewId": "r2", "text": "Nasi gorengnya biasa saja"},
        ],
    }
    items = parse_maps_place_items(review_hit_place, topic)
    assert len(items) == 2
    assert items[0].metadata["type"] == "place"
    assert items[1].metadata["type"] == "review"
    assert items[1].id == "maps:r1"

    # Place with name hit generates place summary even if reviews don't mention product
    name_hit_place = {
        "placeId": "p_seblak",
        "title": "Seblak Prasmanan Viral",
        "reviews": [
            {"reviewId": "r3", "text": "Tempat bersih dan luas"},
        ],
    }
    name_items = parse_maps_place_items(name_hit_place, topic)
    assert len(name_items) == 1
    assert name_items[0].metadata["type"] == "place"


def test_maps_clitic_matching_precision(topic: Topic) -> None:
    """Section 18: Clitic regex matches 'seblaknya', 'seblakku', 'seblakmu' but not 'reseblakan'."""
    valid_clitics = ["seblaknya", "seblakku", "seblakmu"]
    for word in valid_clitics:
        place = {
            "placeId": f"p_{word}",
            "title": "Kedai Makanan",
            "reviews": [{"reviewId": f"r_{word}", "text": f"Mencoba {word} di sini mantap"}],
        }
        res = parse_maps_place_items(place, topic)
        assert len(res) == 2, f"Failed for clitic {word}"

    # Non-clitic substring must NOT match
    invalid = {
        "placeId": "p_invalid",
        "title": "Kedai Makanan",
        "reviews": [{"reviewId": "r_sub", "text": "Suasana reseblakan yang asik"}],
    }
    assert parse_maps_place_items(invalid, topic) == []


def test_maps_provider_max_places_separated_from_evidence_limit(topic: Topic) -> None:
    """Section 19: maxCrawledPlacesPerSearch defaults to 3 even when limit=50."""
    inp = build_maps_input(topic, limit=50)
    assert inp["maxCrawledPlacesPerSearch"] == 3


# ==============================================================================
# SECTION 3: SOCIAL LOOKBACK CUTOFF & EXPLICIT BOUNDED PARAMETERS
# ==============================================================================

def test_tiktok_explicit_bounded_flags(topic: Topic) -> None:
    """Section 30: Explicit bounded flags in TikTok input."""
    inp = build_tiktok_input(topic, limit=20)
    assert inp["maxFollowersPerProfile"] == 0
    assert inp["maxFollowingPerProfile"] == 0
    assert inp["commentsPerPost"] == 0
    assert inp["topLevelCommentsPerPost"] == 0
    assert inp["maxRepliesPerComment"] == 0
    assert inp["scrapeRelatedSearchWords"] is False
    assert inp["scrapeRelatedVideos"] is False
    assert inp["scrapeAdditionalAuthorMeta"] is False
    assert inp["shouldDownloadVideos"] is False
    assert inp["shouldDownloadCovers"] is False
    assert inp["shouldDownloadSlideshowImages"] is False
    assert inp["shouldDownloadAvatars"] is False
    assert inp["shouldDownloadMusicCovers"] is False
    assert inp["downloadSubtitlesOptions"] == "NEVER_DOWNLOAD_SUBTITLES"
    assert inp["aiVideoDescription"] is False
    assert inp["aiVideoSummary"] is False
    assert inp["proxyCountryCode"] == "ID"


def test_social_lookback_cutoff_rejection(topic: Topic) -> None:
    """Section 28: Social adapters reject posts older than configured lookback days."""
    now = datetime(2026, 10, 3, 12, 0, 0, tzinfo=timezone.utc)
    old_time = (now - timedelta(days=60)).isoformat()
    recent_time = (now - timedelta(days=5)).isoformat()

    # TikTok
    tt_items = [
        {"id": "tt_old", "text": "Seblak enak", "createTimeISO": old_time},
        {"id": "tt_new", "text": "Seblak viral", "createTimeISO": recent_time},
    ]
    tt_res = parse_tiktok_payload(tt_items, topic, limit=10, lookback_days=30, now=now)
    assert len(tt_res) == 1
    assert tt_res[0].external_id == "tt_new"

    # Instagram
    ig_items = [
        {"id": "ig_old", "caption": "Seblak enak", "timestamp": old_time},
        {"id": "ig_new", "caption": "Seblak viral", "timestamp": recent_time},
    ]
    ig_res = parse_instagram_payload(ig_items, topic, limit=10, lookback_days=30, now=now)
    assert len(ig_res) == 1
    assert ig_res[0].external_id == "ig_new"

    # Facebook
    fb_items = [
        {"id": "fb_old", "text": "Seblak enak", "publishedAt": old_time},
        {"id": "fb_new", "text": "Seblak viral", "publishedAt": recent_time},
    ]
    fb_res = parse_facebook_payload(fb_items, topic, limit=10, lookback_days=30, now=now)
    assert len(fb_res) == 1
    assert fb_res[0].external_id == "fb_new"
