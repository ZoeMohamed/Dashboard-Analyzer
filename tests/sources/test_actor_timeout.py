"""The platform-configured Apify run timeout reaches every Apify adapter."""

import pytest
from pydantic import SecretStr

from app.config import Settings
from app.contracts import SourceName
from app.services.providers import build_providers
from app.sources.base import Topic
from app.sources.facebook import FacebookAdapter
from app.sources.instagram import InstagramAdapter
from app.sources.maps import MapsAdapter
from app.sources.shopee import ShopeeAdapter
from app.sources.tiktok import TikTokAdapter


class RecordingClient:
    def __init__(self) -> None:
        self.timeouts: list[int] = []

    async def run_actor(self, actor_id, actor_input, *, timeout_seconds: int = 120, limit: int = 50):
        self.timeouts.append(timeout_seconds)
        return {"items": [], "run_id": "run-1"}


@pytest.mark.parametrize("adapter_class", [TikTokAdapter, InstagramAdapter, FacebookAdapter, MapsAdapter, ShopeeAdapter])
async def test_adapter_uses_configured_actor_timeout(adapter_class) -> None:
    client = RecordingClient()
    await adapter_class(client, actor_timeout_seconds=600).collect(Topic(id="t", name="Seblak", cities=["Bandung"]), limit=5)
    assert client.timeouts == [600]


async def test_build_providers_passes_settings_timeout() -> None:
    settings = Settings(_env_file=None, apify_tokens=[SecretStr("token")], apify_actor_timeout_seconds=900)
    providers, clients = build_providers(settings)
    assert providers[SourceName.MAPS].adapter.actor_timeout_seconds == 900
    for client in clients:
        await client.close()
