"""Structured improvement suggestions and local generator (FN-007, SUG-001~SUG-003)."""

from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from dev_pre_review.domain.enums import DrawingType, RuleOperator, RuleState
from dev_pre_review.domain.models import Finding, RuleDefinition


class ImprovementSuggestion(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: UUID
    issue: str
    location: str
    recommendation: str
    evidence_refs: list[str] = Field(default_factory=list)
    verification_condition: str


class SuggestionProvider(Protocol):
    def suggest(self, finding: Finding) -> ImprovementSuggestion: ...


class LocalSuggestionProvider:
    """Local JSON schema based suggestion generator (Qwen3-4B-Instruct GGUF compliant)."""

    def suggest(self, finding: Finding) -> ImprovementSuggestion:
        ev_refs = [e.ref_id for e in finding.evidence]
        ref_text = ", ".join(ev_refs) if ev_refs else "N/A"

        # Deterministic structured suggestion
        issue = f"[{finding.severity.value.upper()}] {finding.message}"
        recommendation = (
            f"검토 위치({finding.location})의 항목을 확인하고 표준 사양에 맞게 보정하십시오. "
            f"(참조 근거: {ref_text})"
        )
        verification_condition = (
            f"수정 후 도면 검증 시 {finding.finding_type} 규칙을 "
            f"재평가하여 위반이 발생하지 않아야 함."
        )

        return ImprovementSuggestion(
            finding_id=finding.id,
            issue=issue,
            location=finding.location,
            recommendation=recommendation,
            evidence_refs=ev_refs,
            verification_condition=verification_condition,
        )

    def generate_draft_rule_candidate(
        self,
        finding: Finding,
        project_id: UUID,
    ) -> RuleDefinition:
        """Local generator may only create interpretive rule candidates in DRAFT state."""
        return RuleDefinition(
            id=uuid4(),
            project_id=project_id,
            state=RuleState.DRAFT,
            drawing_types=(DrawingType.PDF, DrawingType.DXF),
            field=finding.finding_type,
            operator=RuleOperator.REQUIRED,
            value=finding.message,
            severity=finding.severity,
            version=1,
        )
