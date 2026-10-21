"""Tests for knowledge import preview API endpoint."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import dev_pre_review.api.knowledge as knowledge_api
from dev_pre_review.main import create_app

FIXTURES_DIR = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "excel"


def test_import_preview_endpoint_persists_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setattr(knowledge_api, "get_artifacts_dir", lambda: artifacts_dir, raising=False)
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
    assert (artifacts_dir / "import-previews" / f"{data['preview_id']}.xlsx").is_file()
