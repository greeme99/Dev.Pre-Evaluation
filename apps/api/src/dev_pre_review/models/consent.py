"""Data transmission consent management (FN-007, SEC-001~SEC-004)."""

import secrets
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from dev_pre_review.domain.models import Finding, Timestamp, utc_now


class ConsentError(ValueError):
    """Raised when external AI transmission is attempted without explicit user consent."""


class TransmissionPreview(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    job_id: UUID
    token: str
    payload_summary: list[dict[str, Any]]
    created_at: Timestamp


class ConsentManager:
    """Manages explicit per-job consent for external AI data transmissions."""

    def __init__(self) -> None:
        self._consents: dict[UUID, str] = {}
        self._previews: dict[UUID, TransmissionPreview] = {}

    def create_preview(self, job_id: UUID, findings: list[Finding]) -> TransmissionPreview:
        token = secrets.token_hex(16)
        summary: list[dict[str, Any]] = []

        for f in findings:
            item = {
                "finding_id": str(f.id),
                "severity": f.severity.value,
                "message": f.message,
                "location": f.location,
                "evidence_count": len(f.evidence),
            }
            summary.append(item)

        preview = TransmissionPreview(
            job_id=job_id,
            token=token,
            payload_summary=summary,
            created_at=utc_now(),
        )
        self._previews[job_id] = preview
        return preview

    def grant_consent(self, job_id: UUID, token: str) -> None:
        preview = self._previews.get(job_id)
        if not preview or preview.token != token:
            raise ConsentError("Invalid or missing preview token for consent grant.")
        self._consents[job_id] = token

    def revoke_consent(self, job_id: UUID) -> None:
        self._consents.pop(job_id, None)
        self._previews.pop(job_id, None)

    def has_consent(self, job_id: UUID) -> bool:
        return job_id in self._consents

    def clear_payload(self, job_id: UUID) -> None:
        """Immediately purge transmitted artifacts from memory upon completion or error."""
        self.revoke_consent(job_id)
