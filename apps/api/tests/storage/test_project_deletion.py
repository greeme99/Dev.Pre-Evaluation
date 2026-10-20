"""Project cascade deletion across DB and external stores (FR-016, RULE-008, TC-031)."""

from pathlib import Path
from uuid import UUID

import pytest
from conftest import Repos, Seed, project_dir, seed_project
from sqlalchemy import func, select

from dev_pre_review.domain.enums import (
    EvidenceKind,
    FindingStatus,
    JobState,
    ProjectStatus,
    Severity,
)
from dev_pre_review.domain.errors import ProjectBusy, ProjectDeletionIncomplete
from dev_pre_review.domain.models import Evidence, Finding
from dev_pre_review.storage.database import Database
from dev_pre_review.storage.deletion import FileStorePurger, ProjectDeletionService
from dev_pre_review.storage.schema import metadata


class FlakyPurger:
    """Fails the first N calls, then purges, mimicking a locked vector index."""

    name = "flaky-vectors"

    def __init__(self, failures: int) -> None:
        self.remaining_failures = failures
        self.purged: list[UUID] = []

    def purge_project(self, project_id: UUID) -> None:
        if self.remaining_failures > 0:
            self.remaining_failures -= 1
            raise OSError("index locked")
        self.purged.append(project_id)


def row_counts(database: Database) -> dict[str, int]:
    with database.engine.connect() as connection:
        return {
            table.name: connection.execute(select(func.count()).select_from(table)).scalar_one()
            for table in metadata.sorted_tables
        }


def populate(repos: Repos, seed: Seed, root: Path) -> None:
    job = repos.jobs.add(seed.new_job())
    repos.findings.add_many(
        [
            Finding(
                job_id=job.id,
                status=FindingStatus.VIOLATION,
                severity=Severity.HIGH,
                confidence=1.0,
                finding_type="tolerance",
                location="page:1",
                message="합성 위반",
                evidence=(Evidence(kind=EvidenceKind.RULE, ref_id="R-001"),),
            )
        ]
    )
    tiles = project_dir(root, seed.project.id) / "tiles"
    tiles.mkdir(parents=True)
    (tiles / "t0.png").write_bytes(b"\x89PNG synthetic")


def test_delete_removes_db_rows_and_files(
    database: Database, repos: Repos, seed: Seed, tmp_path: Path
) -> None:
    root = tmp_path / "data"
    populate(repos, seed, root)
    service = ProjectDeletionService(repos.projects, repos.jobs, [FileStorePurger(root)])

    service.delete(seed.project.id)

    assert set(row_counts(database).values()) == {0}
    assert not project_dir(root, seed.project.id).exists()


def test_delete_keeps_other_projects(
    database: Database, repos: Repos, seed: Seed, tmp_path: Path
) -> None:
    root = tmp_path / "data"
    other = seed_project(repos, name="다른 프로젝트")
    populate(repos, seed, root)
    populate(repos, other, root)
    service = ProjectDeletionService(repos.projects, repos.jobs, [FileStorePurger(root)])

    service.delete(seed.project.id)

    assert repos.projects.get(other.project.id).status is ProjectStatus.ACTIVE
    assert project_dir(root, other.project.id).exists()
    assert row_counts(database)["findings"] == 1


def test_partial_failure_is_resumable_until_nothing_remains(
    database: Database, repos: Repos, seed: Seed, tmp_path: Path
) -> None:
    root = tmp_path / "data"
    populate(repos, seed, root)
    queued = repos.jobs.add(seed.new_job())
    flaky = FlakyPurger(failures=1)
    service = ProjectDeletionService(repos.projects, repos.jobs, [FileStorePurger(root), flaky])

    with pytest.raises(ProjectDeletionIncomplete) as excinfo:
        service.delete(seed.project.id)

    assert excinfo.value.failed_stores == ("flaky-vectors",)
    assert repos.projects.get(seed.project.id).status is ProjectStatus.DELETING
    assert repos.jobs.get(queued.id).state is JobState.CANCELLED
    assert repos.jobs.claim_next() is None

    assert service.resume_pending() == [seed.project.id]

    assert flaky.purged == [seed.project.id]
    assert set(row_counts(database).values()) == {0}
    assert not project_dir(root, seed.project.id).exists()


def test_delete_blocked_while_job_running(repos: Repos, seed: Seed, tmp_path: Path) -> None:
    repos.jobs.add(seed.new_job())
    assert repos.jobs.claim_next() is not None
    service = ProjectDeletionService(repos.projects, repos.jobs, [FileStorePurger(tmp_path)])

    with pytest.raises(ProjectBusy):
        service.delete(seed.project.id)

    assert repos.projects.get(seed.project.id).status is ProjectStatus.ACTIVE


def test_delete_missing_project_is_a_no_op(repos: Repos, tmp_path: Path) -> None:
    service = ProjectDeletionService(repos.projects, repos.jobs, [FileStorePurger(tmp_path)])
    service.delete(UUID(int=0))
