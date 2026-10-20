"""Analysis jobs and findings endpoints (FN-007, API-001~API-005)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field

from dev_pre_review.domain.enums import JobState
from dev_pre_review.domain.models import AnalysisJob, Finding, utc_now
from dev_pre_review.main import get_database
from dev_pre_review.models.generation import ImprovementSuggestion, LocalSuggestionProvider
from dev_pre_review.storage.database import Database
from dev_pre_review.storage.repositories import (
    DrawingRepository,
    FindingRepository,
    JobRepository,
    ProjectRepository,
)

router = APIRouter(prefix="/api/analyses", tags=["analyses"])

DbDep = Annotated[Database, Depends(get_database)]


class CreateAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    drawing_id: UUID
    config_versions: dict[str, str] = Field(default_factory=dict)


class AnalysisJobResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID
    project_id: UUID
    drawing_id: UUID
    state: str
    completed_steps: list[str]
    failed_step: str | None = None
    error_code: str | None = None
    config_versions: dict[str, str]


class FindingsResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    job_id: UUID
    findings: list[Finding]
    suggestions: list[ImprovementSuggestion]


def _to_response(job: AnalysisJob) -> AnalysisJobResponse:
    return AnalysisJobResponse(
        id=job.id,
        project_id=job.project_id,
        drawing_id=job.drawing_id,
        state=job.state.value,
        completed_steps=[s.value for s in job.completed_steps],
        failed_step=job.failed_step.value if job.failed_step else None,
        error_code=job.error_code,
        config_versions=job.config_versions,
    )


@router.post("", response_model=AnalysisJobResponse, status_code=status.HTTP_201_CREATED)
def create_analysis_job(
    req: CreateAnalysisRequest,
    db: DbDep,
) -> AnalysisJobResponse:
    project_repo = ProjectRepository(db.sessions)
    drawing_repo = DrawingRepository(db.sessions)
    job_repo = JobRepository(db.sessions)

    # Verify project and drawing exist
    project_repo.get(req.project_id)
    drawing_repo.get(req.drawing_id)

    job = AnalysisJob(
        project_id=req.project_id,
        drawing_id=req.drawing_id,
        config_versions=req.config_versions,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    saved = job_repo.add(job)
    return _to_response(saved)


@router.get("/{job_id}", response_model=AnalysisJobResponse)
def get_analysis_job(
    job_id: UUID,
    db: DbDep,
) -> AnalysisJobResponse:
    job_repo = JobRepository(db.sessions)
    job = job_repo.get(job_id)
    return _to_response(job)


@router.post("/{job_id}/cancel", response_model=AnalysisJobResponse)
def cancel_analysis_job(
    job_id: UUID,
    db: DbDep,
) -> AnalysisJobResponse:
    job_repo = JobRepository(db.sessions)
    job = job_repo.get(job_id)

    updated = job.request_cancel()
    if updated.state is JobState.CANCELLING:
        # For non-worker direct cancel, confirm immediately
        updated = updated.confirm_cancel()

    job_repo.update(updated)
    return _to_response(updated)


@router.post("/{job_id}/retry", response_model=AnalysisJobResponse)
def retry_analysis_job(
    job_id: UUID,
    db: DbDep,
) -> AnalysisJobResponse:
    job_repo = JobRepository(db.sessions)
    job = job_repo.get(job_id)

    retried = job.retry()
    job_repo.update(retried)
    return _to_response(retried)


@router.get("/{job_id}/findings", response_model=FindingsResponse)
def get_analysis_findings(
    job_id: UUID,
    db: DbDep,
) -> FindingsResponse:
    job_repo = JobRepository(db.sessions)
    finding_repo = FindingRepository(db.sessions)

    job_repo.get(job_id)
    findings = finding_repo.list_for_job(job_id)

    suggestion_provider = LocalSuggestionProvider()
    suggestions = [suggestion_provider.suggest(f) for f in findings]

    return FindingsResponse(
        job_id=job_id,
        findings=findings,
        suggestions=suggestions,
    )
