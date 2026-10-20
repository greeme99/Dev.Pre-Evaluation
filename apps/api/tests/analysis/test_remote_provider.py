"""Tests for remote AI provider, consent management, and fault isolation.

FN-007, SEC-001~SEC-004, TC-023, TC-024.
"""

from unittest.mock import patch
from uuid import uuid4

import pytest

from dev_pre_review.domain.enums import EvidenceKind, FindingStatus, Severity
from dev_pre_review.domain.models import Evidence, Finding, utc_now
from dev_pre_review.models.consent import (
    ConsentError,
    ConsentManager,
    TransmissionPreview,
)
from dev_pre_review.models.generation import (
    ImprovementSuggestion,
    LocalSuggestionProvider,
)
from dev_pre_review.models.openai_provider import OpenAISuggestionProvider


def make_test_finding(job_id) -> Finding:
    return Finding(
        job_id=job_id,
        status=FindingStatus.VIOLATION,
        severity=Severity.HIGH,
        confidence=1.0,
        finding_type="tolerance_exceeded",
        location="p1",
        message="가공 공차 초과",
        evidence=(Evidence(kind=EvidenceKind.RULE, ref_id="R-001"),),
        created_at=utc_now(),
    )


def test_consent_manager_requires_explicit_grant() -> None:
    cm = ConsentManager()
    job_id = uuid4()
    finding = make_test_finding(job_id)

    # Generate preview
    preview = cm.create_preview(job_id=job_id, findings=[finding])
    assert isinstance(preview, TransmissionPreview)
    assert len(preview.payload_summary) > 0
    assert not cm.has_consent(job_id)

    # Grant consent
    cm.grant_consent(job_id, preview.token)
    assert cm.has_consent(job_id)

    # Revoke consent
    cm.revoke_consent(job_id)
    assert not cm.has_consent(job_id)


def test_remote_provider_rejects_without_consent() -> None:
    cm = ConsentManager()
    job_id = uuid4()
    finding = make_test_finding(job_id)

    provider = OpenAISuggestionProvider(api_key="mock-key", consent_manager=cm)

    with pytest.raises(ConsentError):
        provider.generate_suggestion(finding, job_id=job_id)


def test_remote_failure_isolates_and_preserves_findings() -> None:
    cm = ConsentManager()
    job_id = uuid4()
    finding = make_test_finding(job_id)

    preview = cm.create_preview(job_id, [finding])
    cm.grant_consent(job_id, preview.token)

    provider = OpenAISuggestionProvider(api_key="mock-key", consent_manager=cm)

    # Mock OpenAI client raising API/connection error
    with patch.object(provider, "_call_api", side_effect=RuntimeError("OpenAI API unreachable")):
        result = provider.generate_suggestion_safe(finding, job_id=job_id)

        assert result.success is False
        assert result.remote_status == "failed_without_data_retention"
        assert result.suggestion is None
        # Transmitted memory payload is immediately cleared
        assert not cm.has_consent(job_id)


def test_local_suggestion_provider_generates_structured_suggestion() -> None:
    local_provider = LocalSuggestionProvider()
    job_id = uuid4()
    finding = make_test_finding(job_id)

    suggestion = local_provider.suggest(finding)
    assert isinstance(suggestion, ImprovementSuggestion)
    assert suggestion.finding_id == finding.id
    assert len(suggestion.issue) > 0
    assert len(suggestion.recommendation) > 0
    assert len(suggestion.verification_condition) > 0
    assert "R-001" in suggestion.evidence_refs
