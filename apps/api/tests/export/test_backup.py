"""Tests for encrypted backup and restore round-trip (FN-009, FR-014, TC-027, TC-028)."""

from uuid import uuid4

import pytest

import dev_pre_review.export.backup as backup_module
from dev_pre_review.domain.enums import (
    DrawingType,
    EvidenceKind,
    FindingStatus,
    ProjectStatus,
    Severity,
)
from dev_pre_review.domain.models import (
    AnalysisJob,
    DrawingArtifact,
    Evidence,
    Finding,
    ReviewProject,
    utc_now,
)
from dev_pre_review.export.backup import (
    BackupAuthenticationError,
    BackupService,
    BackupTamperedError,
    BackupTooLargeError,
)
from dev_pre_review.storage.database import Database
from dev_pre_review.storage.repositories import (
    DrawingRepository,
    FindingRepository,
    JobRepository,
    ProjectRepository,
)


@pytest.fixture
def source_db(tmp_path) -> tuple[Database, uuid4, uuid4, uuid4]:
    db = Database.from_path(tmp_path / "source.db")
    db.upgrade()

    proj_repo = ProjectRepository(db.sessions)
    drawing_repo = DrawingRepository(db.sessions)
    job_repo = JobRepository(db.sessions)
    finding_repo = FindingRepository(db.sessions)

    p_id = uuid4()
    d_id = uuid4()
    j_id = uuid4()

    proj_repo.add(ReviewProject(id=p_id, name="백업 대상 프로젝트", created_at=utc_now()))
    drawing_repo.add(
        DrawingArtifact(
            id=d_id,
            project_id=p_id,
            sha256="d" * 64,
            drawing_type=DrawingType.PDF,
            source_name="백업_도면.pdf",
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
        finding_type="RULE-BACKUP-01",
        location="p.1 (5, 5)",
        message="백업 테스트 위반 사항",
        pixel_bbox=(5.0, 5.0, 15.0, 15.0),
        evidence=(Evidence(kind=EvidenceKind.RULE, ref_id="RULE-BACKUP-01"),),
        created_at=utc_now(),
    )
    finding_repo.add_many([finding])
    return db, p_id, d_id, j_id


def test_backup_and_restore_round_trip(source_db, tmp_path) -> None:
    db, p_id, d_id, j_id = source_db
    service = BackupService()
    passphrase = "super-secure-passphrase-2026"

    # 1. Create encrypted backup
    package_bytes = service.create(db.sessions, passphrase=passphrase, include_sources=False)
    assert len(package_bytes) > 0

    # 2. Preview restore
    preview = service.preview(package_bytes, passphrase=passphrase)
    assert preview["project_count"] == 1
    assert preview["drawing_count"] == 1
    assert preview["job_count"] == 1
    assert preview["finding_count"] == 1
    assert "version_manifest" in preview

    # 3. Commit restore to target DB
    target_db = Database.from_path(tmp_path / "target.db")
    target_db.upgrade()

    service.restore(package_bytes, passphrase=passphrase, target_session_factory=target_db.sessions)

    # 4. Verify restored entities in target DB
    proj_repo = ProjectRepository(target_db.sessions)
    finding_repo = FindingRepository(target_db.sessions)

    projects = proj_repo.list_by_status(ProjectStatus.ACTIVE)
    assert len(projects) == 1
    assert projects[0].name == "백업 대상 프로젝트"

    findings = finding_repo.list_for_job(j_id)
    assert len(findings) == 1
    assert findings[0].finding_type == "RULE-BACKUP-01"


def test_restore_with_wrong_passphrase_raises_auth_error(source_db) -> None:
    db, _, _, _ = source_db
    service = BackupService()
    package_bytes = service.create(db.sessions, passphrase="correct-passphrase")

    with pytest.raises(BackupAuthenticationError):
        service.preview(package_bytes, passphrase="wrong-passphrase")


def test_restore_tampered_package_raises_tampered_error(source_db) -> None:
    db, _, _, _ = source_db
    service = BackupService()
    package_bytes = service.create(db.sessions, passphrase="correct-passphrase")

    # Tamper with the ciphertext payload (middle bytes)
    tampered_bytes = bytearray(package_bytes)
    tampered_bytes[-20] ^= 0xFF

    with pytest.raises((BackupTamperedError, BackupAuthenticationError)):
        service.preview(bytes(tampered_bytes), passphrase="correct-passphrase")


def test_backup_service_rejects_oversized_package_before_decrypt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(backup_module, "MAX_BACKUP_PACKAGE_BYTES", 8)
    with pytest.raises(BackupTooLargeError):
        BackupService().preview(
            b"x" * 9,
            passphrase="correct-passphrase",
        )
