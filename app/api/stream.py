from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_pipeline
from app.services.pipeline import PipelineService

router = APIRouter(tags=["stream"])


@router.get("/stream")
async def stream(request: Request, pipeline: PipelineService = Depends(get_pipeline)) -> StreamingResponse:
    queue = pipeline.broker.subscribe()

    async def events():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=20)
                    # Send a default SSE message because the frontend uses
                    # EventSource.onmessage. The payload still carries `type`.
                    yield f"data: {json.dumps(event.model_dump(mode='json'))}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            pipeline.broker.unsubscribe(queue)

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
