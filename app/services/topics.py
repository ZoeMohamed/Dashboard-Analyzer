"""Topic rules shared by the API and background jobs."""

from __future__ import annotations

from app.config import Settings
from app.contracts import Topic, TopicCreate
from app.errors import TopicLimitError


class TopicService:
    def __init__(self, repository: object, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    async def create(self, payload: TopicCreate) -> Topic:
        if await self.repository.count_active_topics() >= self.settings.max_active_topics:
            raise TopicLimitError(f"Maksimal {self.settings.max_active_topics} topik aktif")
        if not payload.cities:
            # Maps needs a location; without one it searches all of Indonesia.
            payload = payload.model_copy(update={"cities": [self.settings.default_city]})
        return await self.repository.create_topic(payload)
