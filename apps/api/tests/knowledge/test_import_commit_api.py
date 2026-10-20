"""Tests for Knowledge Import Commit API endpoint."""

from pathlib import Path
from uuid import uuid4

import pytest
from conftest import Seed
from fastapi import status
from fastapi.testclient import TestClient
from openpyxl import Workbook

import dev_pre_review.api.knowledge as knowledge_api
from dev_pre_review.main import create_app, get_database
from dev_pre_review.storage.database import Database

FIXTURES_DIR = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "excel"


@pytest.fixture
def api_client(database: Database, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(
        knowledge_api, "get_artifacts_dir", lambda: tmp_path / "artifacts", raising=False
    )
    app = create_app()
    app.dependency_overrides[get_database] = lambda: database
    return TestClient(app)


def upload(api_client: TestClient, file_path: Path) -> dict:
    with file_path.open("rb") as f:
        response = api_client.post(
            "/api/knowledge/imports/preview",
            files={"file": (file_path.name, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert response.status_code == status.HTTP_200_OK
    return response.json()


def commit_payload(project_id: str, **overrides: object) -> dict:
    return {
        "project_id": project_id,
        "sheet_name": "오류사례",
        "column_mapping": {"부품명": "part_name", "오류설명": "description"},
        "idempotency_key": "api-commit-test-1",
        **overrides,
    }


def test_import_commit_and_list_cases_api(api_client: TestClient, seed: Seed) -> None:
    file_path = FIXTURES_DIR / "standard.xlsx"
    preview = upload(api_client, file_path)
    preview_id = preview["preview_id"]

    commit_resp = api_client.post(
        f"/api/knowledge/imports/{preview_id}/commit",
        json=commit_payload(str(seed.project.id)),
    )
    assert commit_resp.status_code == status.HTTP_200_OK
    result = commit_resp.json()
    assert result["cases_imported"] == 2
    assert result["duplicate_count"] == 0

    # 3. List cases for project
    cases_resp = api_client.get(f"/api/knowledge/cases?project_id={seed.project.id}")
    assert cases_resp.status_code == status.HTTP_200_OK
    cases = cases_resp.json()
    assert len(cases) == 2

    recommit_resp = api_client.post(
        f"/api/knowledge/imports/{preview_id}/commit",
        json=commit_payload(str(seed.project.id)),
    )
    assert recommit_resp.status_code == status.HTTP_200_OK
    recommit_result = recommit_resp.json()
    assert recommit_result["cases_imported"] == 0
    assert recommit_result["duplicate_count"] == 2


def test_commit_imports_all_nonempty_rows_from_server_source(api_client: TestClient, seed: Seed, tmp_path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "오류사례"
    sheet.append(["부품명", "오류설명"])
    for index in range(7):
        sheet.append([f"부품 {index + 1}", f"오류 설명 {index + 1}"])
    path = tmp_path / "seven-rows.xlsx"
    workbook.save(path)
    preview = upload(api_client, path)
    assert len(preview["sheets"][0]["sample_rows"]) == 5

    response = api_client.post(
        f"/api/knowledge/imports/{preview['preview_id']}/commit",
        json=commit_payload(str(seed.project.id), idempotency_key="seven-rows"),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["cases_imported"] == 7


def test_commit_rejects_client_supplied_preview_authority(api_client: TestClient, seed: Seed) -> None:
    preview = upload(api_client, FIXTURES_DIR / "standard.xlsx")
    forged = {**preview, "file_sha256": "f" * 64}
    response = api_client.post(
        f"/api/knowledge/imports/{preview['preview_id']}/commit",
        json=commit_payload(str(seed.project.id), preview=forged, file_sha256="f" * 64, file_name="forged.xlsx"),
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_commit_rejects_unknown_preview_id(api_client: TestClient, seed: Seed) -> None:
    response = api_client.post(
        f"/api/knowledge/imports/{uuid4()}/commit",
        json=commit_payload(str(seed.project.id), idempotency_key="unknown-preview"),
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_commit_rejects_missing_sheet_and_project(api_client: TestClient, seed: Seed) -> None:
    preview = upload(api_client, FIXTURES_DIR / "standard.xlsx")
    missing_sheet = api_client.post(
        f"/api/knowledge/imports/{preview['preview_id']}/commit",
        json=commit_payload(str(seed.project.id), sheet_name="missing"),
    )
    assert missing_sheet.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    missing_project = api_client.post(
        f"/api/knowledge/imports/{preview['preview_id']}/commit",
        json=commit_payload(str(uuid4()), idempotency_key="missing-project"),
    )
    assert missing_project.status_code == status.HTTP_404_NOT_FOUND
