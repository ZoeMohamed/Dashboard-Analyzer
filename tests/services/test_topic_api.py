from fastapi.testclient import TestClient

from app.config import get_settings
from app.contracts import Evidence, SourceName
from app.main import app


def test_topic_limit_default_city_and_source_filtered_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "max_active_topics", 1)
    with TestClient(app) as client:
        created = client.post("/api/topics", json={"name": "Seblak"})
        assert created.status_code == 201
        assert created.json()["cities"] == [get_settings().default_city]
        assert client.post("/api/topics", json={"name": "Bakso"}).status_code == 409

        topic_id = created.json()["id"]
        repository = app.state.repository
        client.portal.call(repository.upsert_evidence, [
            Evidence(source=SourceName.TIKTOK, topic_id=topic_id, external_id="a", text="seblak", url="https://example.com/a"),
            Evidence(source=SourceName.YOUTUBE, topic_id=topic_id, external_id="b", text="seblak", url="https://example.com/b"),
        ])
        body = client.get(f"/api/topics/{topic_id}/snapshot", params={"source": "youtube"}).json()
        assert [item["source"] for item in body["evidence"]] == ["youtube"]
        assert body["total_evidence"] == 1
        assert {item["source"]: item["evidence_count"] for item in body["sources"]}["tiktok"] == 1

        insights = client.get(f"/api/topics/{topic_id}/insights").json()
        assert insights["total_evidence"] == 2 and len(insights["sentiment_daily"]) == 30
        assert client.get("/api/topics/missing/insights").status_code == 404
