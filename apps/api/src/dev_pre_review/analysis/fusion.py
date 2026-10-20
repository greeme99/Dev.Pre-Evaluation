"""Finding fusion engine enforcing rule supremacy and AI non-escalation.

FN-007, RULE-001~RULE-005.
"""

from uuid import UUID, uuid4

from dev_pre_review.domain.enums import EvidenceKind, FindingStatus, Severity
from dev_pre_review.domain.models import Evidence, Finding, utc_now
from dev_pre_review.retrieval.hybrid import RetrievedCase
from dev_pre_review.retrieval.pixel_rag import VisualEvidence


class FindingFusion:
    """Fuses deterministic rule evaluation findings with RAG-retrieved evidence.

    Invariants:
    1. Rule Supremacy: Rule-based violations remain untouched.
    2. AI Non-Escalation: Retrieved cases/visuals NEVER produce VIOLATION (only SUSPECTED).
    3. Evidence-Backed: No finding is produced without supporting evidence.
    """

    def merge(
        self,
        rule_findings: list[Finding],
        retrieved_cases: list[RetrievedCase] | None = None,
        visual_evidences: list[VisualEvidence] | None = None,
        job_id: UUID | None = None,
    ) -> list[Finding]:
        actual_job_id = job_id or uuid4()
        now = utc_now()
        results: list[Finding] = []

        # 1. Rule findings always preserved (Rule Supremacy)
        results.extend(rule_findings)

        # 2. Text RAG retrieved cases produce SUSPECTED findings (AI Non-Escalation)
        if retrieved_cases:
            for case in retrieved_cases:
                case_ev = Evidence(
                    kind=EvidenceKind.CASE,
                    ref_id=str(case.case_id),
                    score=case.score,
                    location=case.discipline,
                )
                finding = Finding(
                    job_id=actual_job_id,
                    status=FindingStatus.SUSPECTED,
                    severity=self._map_severity(case.severity),
                    confidence=min(1.0, case.score * 30.0),  # Normalize ~0.03 RRF to ~0.9
                    finding_type=case.error_type,
                    location=f"case:{case.case_id}",
                    message=f"과거 유사 불량 사례 감지: {case.content}",
                    evidence=(case_ev,),
                    created_at=now,
                )
                results.append(finding)

        # 3. Visual RAG retrieved cases produce SUSPECTED findings with bbox
        if visual_evidences:
            for vis in visual_evidences:
                vis_ev = Evidence(
                    kind=EvidenceKind.CASE,
                    ref_id=str(vis.case_id),
                    score=vis.visual_score,
                    location=vis.image_ref,
                )
                finding = Finding(
                    job_id=actual_job_id,
                    status=FindingStatus.SUSPECTED,
                    severity=Severity.HIGH if vis.visual_score >= 0.8 else Severity.MEDIUM,
                    confidence=vis.visual_score,
                    finding_type="visual_defect_suspected",
                    location=f"page:{vis.page_number}",
                    message=f"도면 타일 시각적 유사 불량 의심 (유사도 {vis.visual_score:.2f})",
                    pixel_bbox=vis.pixel_bbox,
                    evidence=(vis_ev,),
                    created_at=now,
                )
                results.append(finding)

        return results

    def _map_severity(self, sev_str: str) -> Severity:
        s = sev_str.lower()
        if s == "high":
            return Severity.HIGH
        if s == "low":
            return Severity.LOW
        return Severity.MEDIUM
