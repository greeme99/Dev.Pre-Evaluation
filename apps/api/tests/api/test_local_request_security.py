"""Local-only HTTP boundary protections against DNS rebinding and cross-site mutation."""

import asyncio
import io

import pytest
from fastapi.testclient import TestClient

import dev_pre_review.main as main_module
from dev_pre_review.domain.enums import ProjectStatus
from dev_pre_review.main import RequestBodyLimitMiddleware, create_app, get_database
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


def test_rejects_oversized_excel_request_before_multipart_parsing(
    database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main_module, "MAX_EXCEL_REQUEST_BYTES", 64)
    client = _client(database)

    response = client.post(
        "/api/knowledge/imports/preview",
        files={"file": ("oversized.xlsx", io.BytesIO(b"x" * 128))},
    )

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "request_body_too_large"


def test_rejects_chunked_upload_when_accumulated_body_exceeds_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_module, "MAX_EXCEL_REQUEST_BYTES", 64)
    messages = iter(
        [
            {"type": "http.request", "body": b"x" * 40, "more_body": True},
            {"type": "http.request", "body": b"y" * 40, "more_body": False},
        ]
    )
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return next(messages)

    async def downstream(scope: object, receive_body: object, send: object) -> None:
        del scope, send
        while True:
            message = await receive_body()  # type: ignore[operator]
            if not message.get("more_body", False):
                break

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    middleware = RequestBodyLimitMiddleware(downstream)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/knowledge/imports/preview",
        "headers": [],
    }

    asyncio.run(middleware(scope, receive, send))  # type: ignore[arg-type]

    response_start = next(message for message in sent if message["type"] == "http.response.start")
    assert response_start["status"] == 413
