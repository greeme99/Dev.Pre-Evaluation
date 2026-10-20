"""Real API workflow tests for persisted project drawings and analysis jobs."""

import hashlib
import threading
import time
from pathlib import Path

from fastapi.testclient import TestClient

from dev_pre_review.analysis.runtime import create_analysis_worker
from dev_pre_review.domain.enums import (
    AnalysisStep,
    DrawingType,
    FindingStatus,
    JobState,
    Severity,
)
from dev_pre_review.domain.models import (
    AnalysisJob,
    DrawingArtifact,
    Finding,
    ReviewProject,
    utc_now,
)
from dev_pre_review.drawings.dxf_parser import DxfParser
from dev_pre_review.drawings.validation import DrawingValidator
from dev_pre_review.main import create_app, set_database
from dev_pre_review.rules.engine import RuleEvaluator
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


def test_recovery_after_rule_findings_saved_does_not_duplicate_or_delete_findings(
    tmp_path: Path,
) -> None:
    db = Database.from_path(tmp_path / "rule-recovery.db")
    db.upgrade()
    project = ProjectRepository(db.sessions).add(
        ReviewProject(name="rule recovery", created_at=utc_now())
    )
    fixture = Path("tests/fixtures/dxf/missing-xref.dxf")
    artifacts_dir = tmp_path / "artifacts"
    stored = FileStore(artifacts_dir).save_bytes(fixture.read_bytes(), fixture.name)
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
    document = DxfParser().parse(stored).model_copy(update={"drawing_id": drawing.id})
    prior_rule_findings = RuleEvaluator().evaluate(document, [], job_id=job.id).findings
    retained_finding = Finding(
        job_id=job.id,
        status=FindingStatus.INSUFFICIENT_INFORMATION,
        severity=Severity.MEDIUM,
        confidence=0.7,
        finding_type="human_note",
        location="review",
        message="Keep this finding",
        created_at=utc_now(),
    )
    finding_repo = FindingRepository(db.sessions)
    finding_repo.add_many([*prior_rule_findings, retained_finding])

    worker = create_analysis_worker(db, artifacts_dir)
    worker.runner.resume_pending()
    result = worker.runner.run_next()

    assert result is not None
    assert result.state is JobState.COMPLETED
    recovered_findings = finding_repo.list_for_job(job.id)
    assert [finding.finding_type for finding in recovered_findings].count("quality_blocked") == 1
    assert [finding.message for finding in recovered_findings].count("Keep this finding") == 1
    db.dispose()


def test_cancelling_running_analysis_keeps_worker_alive_for_next_job(
    tmp_path: Path, monkeypatch
) -> None:
    data_dir = tmp_path / "data"
    db = Database.from_path(tmp_path / "cancel.db")
    db.upgrade()
    set_database(db)
    monkeypatch.setenv("DEV_PRE_REVIEW_DATA_DIR", str(data_dir))
    client = TestClient(create_app())
    entered_validation = threading.Event()
    release_validation = threading.Event()
    original_validate = DrawingValidator.validate

    with client:
        project_response = client.post("/api/projects", json={"name": "cancel test"})
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

        def pause_worker_validation(self, path, original_name):
            entered_validation.set()
            assert release_validation.wait(timeout=5)
            return original_validate(self, path, original_name)

        monkeypatch.setattr(DrawingValidator, "validate", pause_worker_validation)
        first = client.post(
            "/api/analyses", json={"project_id": project_id, "drawing_id": drawing_id}
        )
        assert first.status_code == 201
        first_job_id = first.json()["id"]
        assert entered_validation.wait(timeout=5)

        second = client.post(
            "/api/analyses", json={"project_id": project_id, "drawing_id": drawing_id}
        )
        assert second.status_code == 201
        second_job_id = second.json()["id"]

        cancel_response = client.post(f"/api/analyses/{first_job_id}/cancel")
        release_validation.set()
        deadline = time.monotonic() + 10
        second_job = second.json()
        while second_job["state"] not in {"completed", "failed", "cancelled"}:
            assert time.monotonic() < deadline, "worker did not process the next queued job"
            time.sleep(0.05)
            second_job = client.get(f"/api/analyses/{second_job_id}").json()

        assert cancel_response.json()["state"] == "cancelling"
        assert client.get(f"/api/analyses/{first_job_id}").json()["state"] == "cancelled"
        assert second_job["state"] == "completed"
        assert client.app.state.analysis_worker._thread.is_alive()

    release_validation.set()
    db.dispose()
    set_database(None)


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
