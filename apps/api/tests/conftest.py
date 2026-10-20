"""Shared fixtures: a migrated temporary SQLite database and repositories."""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import pytest

from dev_pre_review.domain.enums import DrawingType
from dev_pre_review.domain.models import AnalysisJob, DrawingArtifact, ReviewProject
from dev_pre_review.storage.database import Database
from dev_pre_review.storage.repositories import (
    DrawingRepository,
    FindingRepository,
    JobRepository,
    ProjectRepository,
)

SYNTHETIC_SHA256 = "0" * 64


@dataclass(frozen=True)
class Repos:
    projects: ProjectRepository
    drawings: DrawingRepository
    jobs: JobRepository
    findings: FindingRepository


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Database]:
    db = Database.from_path(tmp_path / "app.db")
    db.upgrade()
    yield db
    db.dispose()


@pytest.fixture
def repos(database: Database) -> Repos:
    return Repos(
        projects=ProjectRepository(database.sessions),
        drawings=DrawingRepository(database.sessions),
        jobs=JobRepository(database.sessions),
        findings=FindingRepository(database.sessions),
    )


@dataclass(frozen=True)
class Seed:
    project: ReviewProject
    drawing: DrawingArtifact

    def new_job(self) -> AnalysisJob:
        return AnalysisJob(project_id=self.project.id, drawing_id=self.drawing.id)


@pytest.fixture
def seed(repos: Repos) -> Seed:
    return seed_project(repos)


def seed_project(repos: Repos, name: str = "합성 프로젝트") -> Seed:
    project = repos.projects.add(ReviewProject(name=name))
    drawing = repos.drawings.add(
        DrawingArtifact(
            project_id=project.id,
            sha256=SYNTHETIC_SHA256,
            drawing_type=DrawingType.PDF,
            source_name="synthetic.pdf",
            parser_version="test-0",
        )
    )
    return Seed(project=project, drawing=drawing)


def project_dir(root: Path, project_id: UUID) -> Path:
    return root / "projects" / str(project_id)
