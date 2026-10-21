"""Tests for export, backup, restore and diagnostics API endpoints (API-012~API-014, API-016)."""

import io
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import dev_pre_review.api.export as export_api
from dev_pre_review.domain.enums import DrawingType, EvidenceKind, FindingStatus, Severity
from dev_pre_review.domain.models import (
    AnalysisJob,
    DrawingArtifact,
    Evidence,
    Finding,
    ReviewProject,
    utc_now,
)
from dev_pre_review.main import create_app, set_database
from dev_pre_review.storage.database import Database
from dev_pre_review.storage.repositories import (
    DrawingRepository,
    FindingRepository,
    JobRepository,
    ProjectRepository,
)


@pytest.fixture
def api_client(tmp_path) -> tuple[TestClient, Database, uuid4]:
    db = Database.from_path(tmp_path / "test_api_export.db")
    db.upgrade()
    set_database(db)

    proj_repo = ProjectRepository(db.sessions)
    drawing_repo = DrawingRepository(db.sessions)
    job_repo = JobRepository(db.sessions)
    finding_repo = FindingRepository(db.sessions)

    p_id = uuid4()
    d_id = uuid4()
    j_id = uuid4()

    proj_repo.add(ReviewProject(id=p_id, name="API Export Proj", created_at=utc_now()))
    drawing_repo.add(
        DrawingArtifact(
            id=d_id,
            project_id=p_id,
            sha256="e" * 64,
            drawing_type=DrawingType.PDF,
            source_name="api_test.pdf",
            parser_version="1.0.0",
            created_at=utc_now(),
        )
    )
    job_repo.add(
        AnalysisJob(
            id=j_id,
            project_id=p_id,
            drawing_id=d_id,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
    )
    finding = Finding(
        id=uuid4(),
        job_id=j_id,
        status=FindingStatus.VIOLATION,
        severity=Severity.HIGH,
        confidence=0.9,
        finding_type="RULE-EXP-01",
        location="p.1 (1, 1)",
        message="API 내보내기 테스트 메시지",
        pixel_bbox=(1.0, 1.0, 10.0, 10.0),
        evidence=(Evidence(kind=EvidenceKind.RULE, ref_id="RULE-EXP-01"),),
        created_at=utc_now(),
    )
    finding_repo.add_many([finding])

    app = create_app()
    client = TestClient(app)
    return client, db, j_id


def test_export_findings_xlsx_and_csv_endpoints(api_client) -> None:
    client, _, j_id = api_client

    # 1. GET /api/analyses/{id}/export.xlsx
    xlsx_resp = client.get(f"/api/analyses/{j_id}/export.xlsx")
    assert xlsx_resp.status_code == 200
    assert "spreadsheetml" in xlsx_resp.headers["content-type"]
    assert len(xlsx_resp.content) > 0

    # 2. GET /api/analyses/{id}/export.csv
    csv_resp = client.get(f"/api/analyses/{j_id}/export.csv")
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]
    assert csv_resp.content.startswith(b"\xef\xbb\xbf")
    assert "RULE-EXP-01" in csv_resp.content.decode("utf-8-sig")


def test_backup_and_restore_endpoints(api_client) -> None:
    client, _, _ = api_client

    # 1. POST /api/backups
    backup_resp = client.post("/api/backups", json={"passphrase": "very-secret-passphrase"})
    assert backup_resp.status_code == 200
    package_bytes = backup_resp.content
    assert package_bytes.startswith(b"DPRB")

    # 2. POST /api/restores/preview
    files = {"package": ("backup.dprb", io.BytesIO(package_bytes), "application/octet-stream")}
    data = {"passphrase": "very-secret-passphrase"}
    prev_resp = client.post("/api/restores/preview", files=files, data=data)
    assert prev_resp.status_code == 200
    preview_data = prev_resp.json()
    assert preview_data["project_count"] == 1
    assert preview_data["finding_count"] == 1

    # 3. POST /api/restores/commit
    files2 = {"package": ("backup.dprb", io.BytesIO(package_bytes), "application/octet-stream")}
    commit_resp = client.post("/api/restores/commit", files=files2, data=data)
    assert commit_resp.status_code == 200
    assert commit_resp.json()["status"] == "restored"


@pytest.mark.parametrize("endpoint", ["preview", "commit"])
def test_restore_upload_rejects_oversized_package(
    api_client, monkeypatch: pytest.MonkeyPatch, endpoint: str
) -> None:
    client, _, _ = api_client
    monkeypatch.setattr(export_api, "MAX_BACKUP_UPLOAD_BYTES", 8)

    response = client.post(
        f"/api/restores/{endpoint}",
        files={"package": ("oversized.dprb", io.BytesIO(b"x" * 9), "application/octet-stream")},
        data={"passphrase": "very-secret-passphrase"},
    )

    assert response.status_code == 413


def test_diagnostics_endpoint(api_client) -> None:
    client, _, _ = api_client

    resp = client.post(
        "/api/diagnostics",
        json={
            "error_codes": ["ERR_TEST_API"],
            "step_latencies_ms": {"extract": 45.0},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["app_version"]
    assert data["error_codes"] == ["ERR_TEST_API"]
