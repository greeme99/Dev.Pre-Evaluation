"""Tests for FindingFusion: rule supremacy, AI non-escalation, and evidence-backed invariants.

FN-007, RULE-001~RULE-005, TC-021, TC-022.
"""

from uuid import uuid4

from dev_pre_review.analysis.fusion import FindingFusion
from dev_pre_review.domain.enums import EvidenceKind, FindingStatus, Severity
from dev_pre_review.domain.models import Evidence, Finding, utc_now
from dev_pre_review.retrieval.hybrid import RetrievedCase
from dev_pre_review.retrieval.pixel_rag import VisualEvidence


def make_rule_violation(job_id) -> Finding:
    rule_id = str(uuid4())
    rule_ev = Evidence(kind=EvidenceKind.RULE, ref_id=rule_id)
    return Finding(
        job_id=job_id,
        status=FindingStatus.VIOLATION,
        severity=Severity.HIGH,
        confidence=1.0,
        finding_type="tolerance_exceeded",
        location="p1",
        message="치수 공차 0.05mm 초과",
        evidence=(rule_ev,),
        created_at=utc_now(),
    )


def test_rule_supremacy_preserves_violation() -> None:
    job_id = uuid4()
    fusion = FindingFusion()
    viol = make_rule_violation(job_id)

    # Fusion with retrieved cases
    retrieved = [
        RetrievedCase(
            case_id=uuid4(),
            discipline="mechanical",
            error_type="tolerance_exceeded",
            severity="high",
            content="과거 공차 초과 사례",
            score=0.03,
            text_rank=1,
        )
    ]

    fused = fusion.merge(rule_findings=[viol], retrieved_cases=retrieved, job_id=job_id)
    assert len(fused) >= 1
    # Original violation must remain VIOLATION with RULE evidence
    rule_findings = [f for f in fused if f.status == FindingStatus.VIOLATION]
    assert len(rule_findings) == 1
    assert any(e.kind == EvidenceKind.RULE for e in rule_findings[0].evidence)


def test_ai_non_escalation_only_produces_suspected() -> None:
    job_id = uuid4()
    fusion = FindingFusion()

    # No rule violation, only retrieved similar case
    retrieved = [
        RetrievedCase(
            case_id=uuid4(),
            discipline="electrical",
            error_type="wiring_defect",
            severity="high",
            content="유사 배선 결선 누락 불량 의심",
            score=0.03,
            text_rank=1,
        )
    ]

    fused = fusion.merge(rule_findings=[], retrieved_cases=retrieved, job_id=job_id)
    assert len(fused) == 1
    case_finding = fused[0]
    # AI/RAG cannot escalate to VIOLATION; must be SUSPECTED
    assert case_finding.status == FindingStatus.SUSPECTED
    assert any(e.kind == EvidenceKind.CASE for e in case_finding.evidence)
    # Must NOT have RULE evidence
    assert not any(e.kind == EvidenceKind.RULE for e in case_finding.evidence)


def test_fusion_incorporates_visual_evidence() -> None:
    job_id = uuid4()
    fusion = FindingFusion()
    case_id = uuid4()

    vis_ev = [
        VisualEvidence(
            case_id=case_id,
            image_ref="ref_crack_01",
            page_number=1,
            pixel_bbox=(100.0, 100.0, 200.0, 200.0),
            visual_score=0.88,
            text_score=0.75,
            fused_score=0.815,
        )
    ]

    fused = fusion.merge(
        rule_findings=[],
        retrieved_cases=[],
        visual_evidences=vis_ev,
        job_id=job_id,
    )

    assert len(fused) == 1
    vf = fused[0]
    assert vf.status == FindingStatus.SUSPECTED
    assert vf.pixel_bbox == (100.0, 100.0, 200.0, 200.0)
    assert any(e.kind == EvidenceKind.CASE and e.ref_id == str(case_id) for e in vf.evidence)


def test_findings_require_supporting_evidence() -> None:
    job_id = uuid4()
    fusion = FindingFusion()

    # Merging empty rule and empty retrieval yields empty findings
    fused = fusion.merge(
        rule_findings=[],
        retrieved_cases=[],
        visual_evidences=[],
        job_id=job_id,
    )
    assert len(fused) == 0
