"""Tests for Knowledge Import Commit API endpoint."""

from pathlib import Path

import pytest
from conftest import Seed
from fastapi import status
from fastapi.testclient import TestClient

from dev_pre_review.main import create_app, get_database
from dev_pre_review.storage.database import Database

FIXTURES_DIR = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "excel"


@pytest.fixture
def api_client(database: Database) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_database] = lambda: database
    return TestClient(app)


def test_import_commit_and_list_cases_api(api_client: TestClient, seed: Seed) -> None:
    # 1. Preview
    file_path = FIXTURES_DIR / "standard.xlsx"
    with open(file_path, "rb") as f:
        preview_resp = api_client.post(
            "/api/knowledge/imports/preview",
            files={
                "file": (
                    "standard.xlsx",
                    f,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    assert preview_resp.status_code == status.HTTP_200_OK
    preview = preview_resp.json()
    preview_id = preview["preview_id"]

    # 2. Commit
    commit_payload = {
        "project_id": str(seed.project.id),
        "file_sha256": preview["file_sha256"],
        "file_name": preview["file_name"],
        "sheet_name": "오류사례",
        "column_mapping": {
            "부품명": "part_name",
            "오류설명": "description",
        },
        "idempotency_key": "api-commit-test-1",
        "preview": preview,
    }

    commit_resp = api_client.post(
        f"/api/knowledge/imports/{preview_id}/commit",
        json=commit_payload,
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

    # 4. Re-commit (duplicate detection)
    recommit_resp = api_client.post(
        f"/api/knowledge/imports/{preview_id}/commit",
        json=commit_payload,
    )
    assert recommit_resp.status_code == status.HTTP_200_OK
    recommit_result = recommit_resp.json()
    assert recommit_result["cases_imported"] == 0
    assert recommit_result["duplicate_count"] == 2
