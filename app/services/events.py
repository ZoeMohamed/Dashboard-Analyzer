"""Bounded in-process event broker for SSE and live refresh indicators."""

from __future__ import annotations

import asyncio

from app.contracts import StreamEvent


class EventBroker:
    def __init__(self, max_queue_size: int = 200) -> None:
        self.max_queue_size = max_queue_size
        self._subscribers: set[asyncio.Queue[StreamEvent]] = set()

    async def publish(self, event: StreamEvent) -> None:
        for queue in tuple(self._subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                continue

    def subscribe(self) -> asyncio.Queue[StreamEvent]:
        queue: asyncio.Queue[StreamEvent] = asyncio.Queue(maxsize=self.max_queue_size)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[StreamEvent]) -> None:
        self._subscribers.discard(queue)
