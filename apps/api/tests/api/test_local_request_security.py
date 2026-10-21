"""Local-only HTTP boundary protections against DNS rebinding and cross-site mutation."""

import io

import pytest
from fastapi.testclient import TestClient

import dev_pre_review.main as main_module
from dev_pre_review.domain.enums import ProjectStatus
from dev_pre_review.main import create_app, get_database
from dev_pre_review.storage.database import Database
from dev_pre_review.storage.repositories import ProjectRepository


def _client(database: Database) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_database] = lambda: database
    return TestClient(app)


def test_rejects_external_origin_before_project_mutation(database: Database) -> None:
    client = _client(database)

    response = client.post(
        "/api/projects",
        json={"name": "must not exist"},
        headers={"Origin": "https://attacker.example"},
    )

    assert response.status_code == 403
    assert ProjectRepository(database.sessions).list_by_status(ProjectStatus.ACTIVE) == []


def test_allows_loopback_origin_for_project_mutation(database: Database) -> None:
    client = _client(database)

    response = client.post(
        "/api/projects",
        json={"name": "loopback project"},
        headers={"Origin": "http://127.0.0.1:17841"},
    )

    assert response.status_code == 201


def test_rejects_untrusted_host(database: Database) -> None:
    response = _client(database).get(
        "/api/health",
        headers={"Host": "attacker.example"},
    )

    assert response.status_code == 400


def test_rejects_oversized_restore_request_before_multipart_parsing(
    database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main_module, "MAX_RESTORE_REQUEST_BYTES", 64)
    client = _client(database)

    response = client.post(
        "/api/restores/preview",
        files={
            "package": (
                "oversized.dprb",
                io.BytesIO(b"x" * 128),
                "application/octet-stream",
            )
        },
        data={"passphrase": "very-secret-passphrase"},
    )

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "request_body_too_large"
