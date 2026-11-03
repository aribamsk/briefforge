from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_describes_pipeline():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_short_topic_is_rejected():
    response = client.post("/brief", json={"topic": "a"})

    assert response.status_code == 422
