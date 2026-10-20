"""Real API workflow tests for persisted project drawings and analysis jobs."""

import hashlib
import time
from pathlib import Path

from fastapi.testclient import TestClient

from dev_pre_review.analysis.runtime import create_analysis_worker
from dev_pre_review.domain.enums import AnalysisStep, DrawingType, JobState
from dev_pre_review.domain.models import AnalysisJob, DrawingArtifact, ReviewProject, utc_now
from dev_pre_review.main import create_app, set_database
from dev_pre_review.storage.database import Database
from dev_pre_review.storage.files import FileStore
from dev_pre_review.storage.repositories import (
    DrawingRepository,
    FindingRepository,
    JobRepository,
    ProjectRepository,
)


def test_project_creation_and_persistent_drawing_upload(tmp_path: Path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    db = Database.from_path(tmp_path / "app.db")
    db.upgrade()
    set_database(db)
    monkeypatch.setenv("DEV_PRE_REVIEW_DATA_DIR", str(data_dir))
    client = TestClient(create_app())

    with client:
        project_response = client.post("/api/projects", json={"name": "공정 검토"})
        assert project_response.status_code == 201
        project = project_response.json()
        assert project["name"] == "공정 검토"

        content = Path("tests/fixtures/dxf/missing-xref.dxf").read_bytes()
        upload_response = client.post(
            f"/api/projects/{project['id']}/drawings",
            files={"file": ("drawing.dxf", content, "application/dxf")},
        )
        assert upload_response.status_code == 201
        drawing = upload_response.json()
        assert drawing["project_id"] == project["id"]
        assert drawing["sha256"] == hashlib.sha256(content).hexdigest()
        stored = list((data_dir / "artifacts" / "files").glob("*/*/*"))
        assert len(stored) == 1
        assert stored[0].read_bytes() == content

    db.dispose()
    set_database(None)


def test_file_store_resolves_persisted_drawing_artifact(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    content = b"persisted drawing bytes"
    stored = store.save_bytes(content, "saved.dxf")
    drawing = DrawingArtifact(
        project_id=ReviewProject(name="resolve").id,
        sha256=stored.sha256,
        drawing_type=DrawingType.DXF,
        source_name="saved.dxf",
        parser_version="test",
    )

    resolved = store.resolve(drawing)

    assert resolved.sha256 == stored.sha256
    assert resolved.original_name == "saved.dxf"
    assert resolved.path.read_bytes() == content


def test_startup_recovery_reparses_document_before_rules(tmp_path: Path) -> None:
    db = Database.from_path(tmp_path / "recovery.db")
    db.upgrade()
    project = ProjectRepository(db.sessions).add(
        ReviewProject(name="recovery", created_at=utc_now())
    )
    fixture = Path("tests/fixtures/dxf/missing-xref.dxf")
    stored = FileStore(tmp_path / "artifacts").save_bytes(fixture.read_bytes(), fixture.name)
    drawing = DrawingRepository(db.sessions).add(
        DrawingArtifact(
            project_id=project.id,
            sha256=stored.sha256,
            drawing_type=DrawingType.DXF,
            source_name=fixture.name,
            parser_version="1.0.0",
            created_at=utc_now(),
        )
    )
    job = JobRepository(db.sessions).add(
        AnalysisJob(
            project_id=project.id,
            drawing_id=drawing.id,
            state=JobState.RUNNING,
            completed_steps=(AnalysisStep.VALIDATE, AnalysisStep.EXTRACT),
            started_at=utc_now(),
            created_at=utc_now(),
            updated_at=utc_now(),
        )
    )

    worker = create_analysis_worker(db, tmp_path / "artifacts")
    worker.runner.resume_pending()
    result = worker.runner.run_next()

    assert result is not None
    assert result.id == job.id
    assert result.state is JobState.COMPLETED
    recovered_findings = FindingRepository(db.sessions).list_for_job(job.id)
    assert any(finding.finding_type == "quality_blocked" for finding in recovered_findings)
    db.dispose()


def test_missing_xref_dxf_completes_analysis_and_exports_finding(
    tmp_path: Path, monkeypatch
) -> None:
    data_dir = tmp_path / "data"
    db = Database.from_path(tmp_path / "app.db")
    db.upgrade()
    set_database(db)
    monkeypatch.setenv("DEV_PRE_REVIEW_DATA_DIR", str(data_dir))
    client = TestClient(create_app())

    with client:
        project_response = client.post("/api/projects", json={"name": "XREF 검토"})
        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        fixture = Path("tests/fixtures/dxf/missing-xref.dxf")
        with fixture.open("rb") as source:
            upload_response = client.post(
                f"/api/projects/{project_id}/drawings",
                files={"file": (fixture.name, source, "application/dxf")},
            )
        assert upload_response.status_code == 201
        drawing_id = upload_response.json()["id"]

        job_response = client.post(
            "/api/analyses", json={"project_id": project_id, "drawing_id": drawing_id}
        )
        assert job_response.status_code == 201
        job_id = job_response.json()["id"]
        assert job_response.json()["config_versions"]["analysis_profile"] == "rule_only"

        deadline = time.monotonic() + 10
        job = job_response.json()
        while job["state"] not in {"completed", "failed", "cancelled"}:
            assert time.monotonic() < deadline, "background analysis did not reach terminal state"
            time.sleep(0.05)
            job = client.get(f"/api/analyses/{job_id}").json()

        assert job["state"] == "completed"
        findings_response = client.get(f"/api/analyses/{job_id}/findings")
        assert findings_response.status_code == 200
        findings_payload = findings_response.json()
        assert findings_payload["suggestions"] == []
        findings = findings_payload["findings"]
        assert any(finding["finding_type"] == "quality_blocked" for finding in findings)

        csv_response = client.get(f"/api/analyses/{job_id}/export.csv")
        assert csv_response.status_code == 200
        assert "quality_blocked" in csv_response.content.decode("utf-8-sig")

    db.dispose()
    set_database(None)
