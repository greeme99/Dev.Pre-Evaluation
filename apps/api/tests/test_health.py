from fastapi.testclient import TestClient

from dev_pre_review import __version__
from dev_pre_review.main import create_app


def test_health_returns_version() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
