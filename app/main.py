from datetime import datetime, timezone
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import asyncio

from app.config import get_settings
from app.contracts import (
    RefreshResponse,
    Snapshot,
    SourceName,
    SourceStatus,
    SourceSummary,
    Topic,
    TopicCreate,
    TopicListResponse,
)

settings = get_settings()

app = FastAPI(
    title="Dashboard Analyzer API",
    version="0.1.0",
    description="Backend API pemantau tren dan sentimen inovasi produk UMKM Indonesia."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for initial development
SEED_TOPICS: dict[str, Topic] = {
    "cappuccino-cincau": Topic(
        id="cappuccino-cincau",
        name="Cappuccino Cincau",
        keywords=["cappuccino cincau", "capcin"],
        product_terms=["cappuccino", "cincau", "es"],
        exclude_terms=["upin ipin", "kartun"],
        cities=["Bandung", "Jakarta", "Surabaya"],
        created_at=datetime.now(timezone.utc),
    ),
    "seblak-pedas": Topic(
        id="seblak-pedas",
        name="Seblak Pedas",
        keywords=["seblak pedas", "seblak jeletot"],
        product_terms=["seblak", "kerupuk", "pedas"],
        exclude_terms=["gameplay", "mukbang luar negeri"],
        cities=["Bandung", "Garut"],
        created_at=datetime.now(timezone.utc),
    ),
    "keripik-pisang": Topic(
        id="keripik-pisang",
        name="Keripik Pisang Lumer",
        keywords=["keripik pisang", "pisang lumer"],
        product_terms=["keripik", "pisang", "cokelat"],
        exclude_terms=["kartun"],
        cities=["Lampung", "Yogyakarta"],
        created_at=datetime.now(timezone.utc),
    ),
}

SOURCES_LIST = [
    SourceName.TIKTOK,
    SourceName.INSTAGRAM,
    SourceName.FACEBOOK,
    SourceName.MAPS,
    SourceName.SHOPEE,
    SourceName.YOUTUBE,
]


def create_mock_snapshot(topic: Topic) -> Snapshot:
    # Seed aspects and source counts for realistic localhost demonstration
    source_summaries = [
        SourceSummary(
            source=source.value,
            evidence_count=12 if source != SourceName.FACEBOOK else 4,
            status=SourceStatus.FRESH,
            updated_at=datetime.now(timezone.utc),
            message="Data terkumpul.",
        )
        for source in SOURCES_LIST
    ]
    return Snapshot(
        topic=topic,
        total_evidence=64,
        positive_count=42,
        negative_count=8,
        neutral_count=14,
        pending_count=0,
        top_aspects=["rasa", "harga", "kemasan", "porsi", "pelayanan"],
        source_summaries=source_summaries,
        updated_at=datetime.now(timezone.utc),
    )


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "app_env": settings.app_env,
        "service": "Dashboard Analyzer API",
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/topics", response_model=TopicListResponse)
async def list_topics():
    return TopicListResponse(topics=list(SEED_TOPICS.values()))


@app.post("/api/topics", response_model=Topic)
async def create_topic(payload: TopicCreate):
    topic_id = payload.name.lower().replace(" ", "-")
    if topic_id in SEED_TOPICS:
        raise HTTPException(status_code=400, detail="Topik dengan nama tersebut sudah ada.")
    
    new_topic = Topic(
        id=topic_id,
        name=payload.name,
        keywords=payload.keywords or [payload.name],
        product_terms=payload.product_terms,
        exclude_terms=payload.exclude_terms,
        cities=payload.cities,
        created_at=datetime.now(timezone.utc),
    )
    SEED_TOPICS[topic_id] = new_topic
    return new_topic


@app.get("/api/topics/{topic_id}/snapshot", response_model=Snapshot)
async def get_topic_snapshot(topic_id: str):
    topic = SEED_TOPICS.get(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topik tidak ditemukan.")
    return create_mock_snapshot(topic)


@app.post("/api/topics/{topic_id}/refresh", response_model=RefreshResponse)
async def refresh_topic(topic_id: str):
    if topic_id not in SEED_TOPICS:
        raise HTTPException(status_code=404, detail="Topik tidak ditemukan.")
    run_id = f"run-{uuid.uuid4().hex[:8]}"
    return RefreshResponse(run_id=run_id, status=SourceStatus.RUNNING)


@app.get("/api/stream")
async def stream_events():
    async def event_generator():
        while True:
            await asyncio.sleep(15)
            yield f"event: heartbeat\ndata: {datetime.now(timezone.utc).isoformat()}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
