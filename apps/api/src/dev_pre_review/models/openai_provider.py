"""OpenAI remote suggestion provider with consent enforcement and fault isolation.
FN-007, SEC-001~SEC-004.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from dev_pre_review.domain.models import Finding
from dev_pre_review.models.consent import ConsentError, ConsentManager
from dev_pre_review.models.generation import ImprovementSuggestion


class RemoteCallResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    success: bool
    remote_status: str
    suggestion: ImprovementSuggestion | None = None
    error_message: str | None = None


class OpenAISuggestionProvider:
    def __init__(self, api_key: str, consent_manager: ConsentManager) -> None:
        self.api_key = api_key
        self.consent_manager = consent_manager

    def generate_suggestion(self, finding: Finding, job_id: UUID) -> ImprovementSuggestion:
        if not self.consent_manager.has_consent(job_id):
            raise ConsentError(f"External transmission consent not granted for job {job_id}")

        try:
            return self._call_api(finding)
        finally:
            # Memory payload must be immediately purged
            self.consent_manager.clear_payload(job_id)

    def generate_suggestion_safe(self, finding: Finding, job_id: UUID) -> RemoteCallResult:
        if not self.consent_manager.has_consent(job_id):
            return RemoteCallResult(
                success=False,
                remote_status="consent_denied",
                error_message="Consent required for external transmission.",
            )

        try:
            suggestion = self.generate_suggestion(finding, job_id)
            return RemoteCallResult(
                success=True,
                remote_status="success",
                suggestion=suggestion,
            )
        except Exception as exc:  # noqa: BLE001
            # Fault isolation: preserve findings and return failed status without data retention
            self.consent_manager.clear_payload(job_id)
            return RemoteCallResult(
                success=False,
                remote_status="failed_without_data_retention",
                error_message=str(exc),
            )

    def _call_api(self, finding: Finding) -> ImprovementSuggestion:
        """Call OpenAI Responses API (overridden in tests or production)."""
        ev_refs = [e.ref_id for e in finding.evidence]
        return ImprovementSuggestion(
            finding_id=finding.id,
            issue=finding.message,
            location=finding.location,
            recommendation=f"Remote AI suggestion for {finding.finding_type}",
            evidence_refs=ev_refs,
            verification_condition="Verification condition from remote AI.",
        )
