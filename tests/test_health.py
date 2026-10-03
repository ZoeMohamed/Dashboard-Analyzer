from fastapi.testclient import TestClient

from app.main import app


def test_health_and_topic_contract() -> None:
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        response = client.post("/api/topics", json={"name": "Cappuccino Cincau"})
        assert response.status_code == 201
        topic_id = response.json()["id"]
        snapshot = client.get(f"/api/topics/{topic_id}/snapshot")
        assert snapshot.status_code == 200
        body = snapshot.json()
        assert set(body["sentiment"]) == {"positif", "negatif", "netral", "pending"}
        assert len(body["sources"]) == 6
        assert body["source_summaries"] == body["sources"]
