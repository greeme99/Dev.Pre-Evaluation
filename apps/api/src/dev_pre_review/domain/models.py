"""Immutable domain models (ENT-001..ENT-009 subset) and their invariants.

State-changing methods return new instances; persistence and version bumps are
the repository's responsibility.
"""

from datetime import UTC, datetime
from typing import Annotated, Self
from uuid import UUID, uuid4

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from dev_pre_review.domain.enums import (
    ANALYSIS_STEPS,
    AnalysisStep,
    DrawingType,
    EvidenceKind,
    FindingStatus,
    JobState,
    ProjectStatus,
    RuleOperator,
    RuleState,
    Severity,
)
from dev_pre_review.domain.errors import InvalidStateTransition


def utc_now() -> datetime:
    return datetime.now(UTC)


def _ordered_bbox(value: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    x_min, y_min, x_max, y_max = value
    if x_min > x_max or y_min > y_max:
        raise ValueError("bbox must be [x_min, y_min, x_max, y_max] with min <= max")
    return value


BBox = Annotated[tuple[float, float, float, float], AfterValidator(_ordered_bbox)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Timestamp = Annotated[AwareDatetime, Field(default_factory=utc_now)]


class DomainModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ReviewProject(DomainModel):
    """ENT-001: root of cascade deletion."""

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=200)
    status: ProjectStatus = ProjectStatus.ACTIVE
    created_at: Timestamp
    data_version: int = Field(default=1, ge=1)


class KnowledgeCase(DomainModel):
    """ENT-003: one error case imported from Excel (persisted from Task 3)."""

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    text: str
    table: tuple[tuple[str, ...], ...] = ()
    image_refs: tuple[str, ...] = ()
    source_file_sha256: Sha256
    source_sheet: str = Field(min_length=1)
    source_cell: str = Field(pattern=r"^[A-Z]{1,3}[1-9][0-9]*$")
    created_at: Timestamp


class RuleDefinition(DomainModel):
    """ENT-004: governed rule (state transitions implemented in Task 4)."""

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    state: RuleState = RuleState.DRAFT
    drawing_types: tuple[DrawingType, ...] = (DrawingType.PDF, DrawingType.DXF)
    field: str = Field(min_length=1)
    operator: RuleOperator
    value: str
    unit: str | None = None
    exceptions: tuple[str, ...] = ()
    severity: Severity
    source_case_ids: tuple[UUID, ...] = ()
    version: int = Field(default=1, ge=1)


class DrawingArtifact(DomainModel):
    """ENT-005: an uploaded drawing referenced by content hash."""

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    sha256: Sha256
    drawing_type: DrawingType
    source_name: str = Field(min_length=1, max_length=255)
    parser_version: str = Field(min_length=1)
    created_at: Timestamp


class Evidence(DomainModel):
    """ENT-009: rule/case/source reference supporting a finding."""

    kind: EvidenceKind
    ref_id: str = Field(min_length=1)
    score: float | None = Field(default=None, ge=0.0)
    location: str | None = None


class Finding(DomainModel):
    """ENT-008. Severity and confidence are independent fields."""

    id: UUID = Field(default_factory=uuid4)
    job_id: UUID
    status: FindingStatus
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    finding_type: str = Field(min_length=1)
    location: str = Field(min_length=1)
    message: str = Field(min_length=1)
    pixel_bbox: BBox | None = None
    cad_bbox: BBox | None = None
    evidence: tuple[Evidence, ...] = ()
    created_at: Timestamp

    @model_validator(mode="after")
    def _violation_needs_rule(self) -> Self:
        if self.status is FindingStatus.VIOLATION and not any(
            e.kind is EvidenceKind.RULE for e in self.evidence
        ):
            raise ValueError("violation requires at least one approved-rule evidence")
        return self


class AnalysisJob(DomainModel):
    """ENT-007 / FN-007: persistent, checkpointed analysis job."""

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    drawing_id: UUID
    state: JobState = JobState.QUEUED
    completed_steps: tuple[AnalysisStep, ...] = ()
    failed_step: AnalysisStep | None = None
    error_code: str | None = None
    config_versions: dict[str, str] = Field(default_factory=dict)
    created_at: Timestamp
    started_at: AwareDatetime | None = None
    finished_at: AwareDatetime | None = None
    updated_at: Timestamp
    version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _steps_are_ordered_prefix(self) -> Self:
        if self.completed_steps != ANALYSIS_STEPS[: len(self.completed_steps)]:
            raise ValueError("completed_steps must be an ordered prefix of the pipeline")
        return self

    @property
    def next_step(self) -> AnalysisStep | None:
        done = len(self.completed_steps)
        return ANALYSIS_STEPS[done] if done < len(ANALYSIS_STEPS) else None

    def _reject(self, action: str) -> InvalidStateTransition:
        return InvalidStateTransition("AnalysisJob", self.state.value, action)

    def _with(self, **changes: object) -> Self:
        return self.model_copy(update={**changes, "updated_at": utc_now()})

    def start(self) -> Self:
        if self.state is not JobState.QUEUED:
            raise self._reject("start")
        return self._with(state=JobState.RUNNING, started_at=self.started_at or utc_now())

    def complete_step(self, step: AnalysisStep) -> Self:
        if self.state not in (JobState.RUNNING, JobState.CANCELLING):
            raise self._reject("complete a step")
        if step is not self.next_step:
            raise self._reject(f"complete '{step.value}' (next is {self.next_step})")
        steps = (*self.completed_steps, step)
        if len(steps) == len(ANALYSIS_STEPS):
            if self.state is JobState.CANCELLING:
                return self._with(completed_steps=steps)
            return self._with(
                completed_steps=steps, state=JobState.COMPLETED, finished_at=utc_now()
            )
        return self._with(completed_steps=steps)

    def fail(self, step: AnalysisStep, error_code: str) -> Self:
        if self.state not in (JobState.RUNNING, JobState.CANCELLING):
            raise self._reject("fail")
        if step is not self.next_step:
            raise self._reject(f"fail '{step.value}' (next is {self.next_step})")
        return self._with(
            state=JobState.FAILED, failed_step=step, error_code=error_code, finished_at=utc_now()
        )

    def request_cancel(self) -> Self:
        if self.state is JobState.QUEUED:
            return self._with(state=JobState.CANCELLED, finished_at=utc_now())
        if self.state is JobState.RUNNING:
            return self._with(state=JobState.CANCELLING)
        if self.state is JobState.CANCELLING:
            return self
        raise self._reject("cancel")

    def confirm_cancel(self) -> Self:
        if self.state is not JobState.CANCELLING:
            raise self._reject("confirm cancel")
        return self._with(state=JobState.CANCELLED, finished_at=utc_now())

    def retry(self) -> Self:
        if self.state is not JobState.FAILED:
            raise self._reject("retry")
        return self._with(
            state=JobState.QUEUED, failed_step=None, error_code=None, finished_at=None
        )

    def recover_after_restart(self) -> Self:
        """Normalize a job left mid-flight by an unclean shutdown."""
        if self.state is JobState.RUNNING:
            return self._with(state=JobState.QUEUED)
        if self.state is JobState.CANCELLING:
            return self.confirm_cancel()
        return self
