from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_list_topics():
    response = client.get("/api/topics")
    assert response.status_code == 200
    data = response.json()
    assert "topics" in data
    assert len(data["topics"]) >= 1


def test_topic_snapshot():
    response = client.get("/api/topics/cappuccino-cincau/snapshot")
    assert response.status_code == 200
    data = response.json()
    assert data["topic"]["name"] == "Cappuccino Cincau"
    assert "top_aspects" in data
    assert "source_summaries" in data
