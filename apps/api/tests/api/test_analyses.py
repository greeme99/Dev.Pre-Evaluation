"""Tests for analyses and settings API endpoints (FN-007, API-001~API-005, TC-027, TC-028)."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from dev_pre_review.domain.enums import DrawingType, JobState
from dev_pre_review.domain.models import AnalysisJob, DrawingArtifact, ReviewProject, utc_now
from dev_pre_review.main import create_app, set_database
from dev_pre_review.storage.database import Database
from dev_pre_review.storage.repositories import (
    DrawingRepository,
    JobRepository,
    ProjectRepository,
)


@pytest.fixture
def api_client(tmp_path) -> tuple[TestClient, Database]:
    db = Database.from_path(tmp_path / "test_api.db")
    db.upgrade()
    set_database(db)

    app = create_app()
    client = TestClient(app)
    return client, db


def test_create_get_cancel_retry_analysis_job(api_client) -> None:
    client, db = api_client
    project_repo = ProjectRepository(db.sessions)
    drawing_repo = DrawingRepository(db.sessions)
    job_repo = JobRepository(db.sessions)

    p_id = uuid4()
    d_id = uuid4()
    project_repo.add(ReviewProject(id=p_id, name="Test Proj", created_at=utc_now()))
    drawing_repo.add(
        DrawingArtifact(
            id=d_id,
            project_id=p_id,
            sha256="a" * 64,
            drawing_type=DrawingType.PDF,
            source_name="test.pdf",
            parser_version="1.0.0",
            created_at=utc_now(),
        )
    )

    # 1. POST /api/analyses (Create job)
    create_resp = client.post(
        "/api/analyses",
        json={"project_id": str(p_id), "drawing_id": str(d_id)},
    )
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    job_id = created_data["id"]
    assert created_data["state"] == "queued"

    # 2. GET /api/analyses/{id}
    get_resp = client.get(f"/api/analyses/{job_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == job_id
    assert get_resp.json()["state"] == "queued"

    # 3. POST /api/analyses/{id}/cancel
    cancel_resp = client.post(f"/api/analyses/{job_id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["state"] == "cancelled"

    # 4. Fail job directly to test retry
    cancelled_job = job_repo.get(UUID(job_id) if isinstance(job_id, str) else job_id)
    # Manually transition to failed in DB for retry test
    db_job = cancelled_job.model_copy(update={"state": JobState.FAILED, "error_code": "ERR_TEST"})
    job_repo.update(db_job)

    # 5. POST /api/analyses/{id}/retry
    retry_resp = client.post(f"/api/analyses/{job_id}/retry")
    assert retry_resp.status_code == 200
    assert retry_resp.json()["state"] == "queued"


def test_get_analysis_findings_and_suggestions(api_client) -> None:
    client, db = api_client
    project_repo = ProjectRepository(db.sessions)
    drawing_repo = DrawingRepository(db.sessions)
    job_repo = JobRepository(db.sessions)

    p_id = uuid4()
    d_id = uuid4()
    j_id = uuid4()

    project_repo.add(ReviewProject(id=p_id, name="Findings Proj", created_at=utc_now()))
    drawing_repo.add(
        DrawingArtifact(
            id=d_id,
            project_id=p_id,
            sha256="b" * 64,
            drawing_type=DrawingType.PDF,
            source_name="findings.pdf",
            parser_version="1.0.0",
            created_at=utc_now(),
        )
    )
    job_repo.add(
        AnalysisJob(
            id=j_id,
            project_id=p_id,
            drawing_id=d_id,
            state=JobState.COMPLETED,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
    )

    resp = client.get(f"/api/analyses/{j_id}/findings")
    assert resp.status_code == 200
    data = resp.json()
    assert "findings" in data
    assert "suggestions" in data
    assert isinstance(data["findings"], list)


def test_get_system_settings_and_profile(api_client) -> None:
    client, _ = api_client

    resp = client.get("/api/settings/profile")
    assert resp.status_code == 200
    data = resp.json()
    assert "hardware_profile" in data
    assert "recommendation" in data
    assert data["hardware_profile"]["execution_provider"] in ("cpu", "cuda")


def test_not_found_returns_rfc7807_problem_details(api_client) -> None:
    client, _ = api_client
    random_id = str(uuid4())

    resp = client.get(f"/api/analyses/{random_id}")
    assert resp.status_code == 404
    data = resp.json()
    assert "title" in data
    assert "detail" in data
    assert "NotFound" in data["title"] or "찾을 수 없습니다" in data["detail"]
