"""Tests for knowledge import preview API endpoint."""

from pathlib import Path

from fastapi.testclient import TestClient

from dev_pre_review.main import create_app

FIXTURES_DIR = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "excel"


def test_import_preview_endpoint() -> None:
    client = TestClient(create_app())
    file_path = FIXTURES_DIR / "standard.xlsx"

    with open(file_path, "rb") as f:
        response = client.post(
            "/api/knowledge/imports/preview",
            files={
                "file": (
                    "standard.xlsx",
                    f,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert "preview_id" in data
    assert "file_sha256" in data
    assert len(data["sheets"]) == 1
    assert data["sheets"][0]["sheet_name"] == "오류사례"
