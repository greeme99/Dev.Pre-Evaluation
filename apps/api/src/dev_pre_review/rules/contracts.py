"""Rule contracts and requests."""

from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from dev_pre_review.domain.enums import DrawingType, RuleOperator, RuleState, Severity


class RuleCandidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    drawing_types: tuple[DrawingType, ...] = (DrawingType.PDF, DrawingType.DXF)
    field: str = Field(min_length=1)
    operator: RuleOperator
    value: str = Field(min_length=1)
    unit: str | None = None
    exceptions: tuple[str, ...] = ()
    severity: Severity = Severity.MEDIUM
    source_case_ids: tuple[UUID, ...] = ()


class RuleCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    drawing_types: list[DrawingType] = Field(
        default_factory=lambda: [DrawingType.PDF, DrawingType.DXF]
    )
    field: str = Field(min_length=1)
    operator: RuleOperator
    value: str = Field(min_length=1)
    unit: str | None = None
    exceptions: list[str] = Field(default_factory=list)
    severity: Severity = Severity.MEDIUM
    source_case_ids: list[UUID] = Field(default_factory=list)


class RuleTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_state: RuleState
    expected_version: int = Field(ge=1)
