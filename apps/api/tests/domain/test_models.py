"""Domain invariants: job state machine (FN-007) and finding verdict rules."""

from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from dev_pre_review.domain.enums import (
    ANALYSIS_STEPS,
    AnalysisStep,
    EvidenceKind,
    FindingStatus,
    JobState,
    Severity,
)
from dev_pre_review.domain.errors import InvalidStateTransition
from dev_pre_review.domain.models import AnalysisJob, Evidence, Finding, ReviewProject


def new_job() -> AnalysisJob:
    return AnalysisJob(project_id=uuid4(), drawing_id=uuid4())


def running_job(*completed: AnalysisStep) -> AnalysisJob:
    return new_job().model_copy(
        update={"state": JobState.RUNNING, "completed_steps": tuple(completed)}
    )


class TestAnalysisJobSteps:
    def test_steps_follow_fixed_pipeline_order(self) -> None:
        job = new_job().start()
        visited = []
        while job.next_step is not None:
            visited.append(job.next_step)
            job = job.complete_step(job.next_step)

        assert visited == list(ANALYSIS_STEPS)
        assert job.state is JobState.COMPLETED
        assert job.finished_at is not None

    def test_out_of_order_step_is_rejected(self) -> None:
        with pytest.raises(InvalidStateTransition):
            new_job().start().complete_step(AnalysisStep.EXTRACT)

    def test_completed_steps_must_be_an_ordered_prefix(self) -> None:
        with pytest.raises(ValidationError):
            AnalysisJob(
                project_id=uuid4(),
                drawing_id=uuid4(),
                completed_steps=(AnalysisStep.EXTRACT,),
            )

    def test_only_queued_job_can_start(self) -> None:
        with pytest.raises(InvalidStateTransition):
            running_job().start()


class TestAnalysisJobCancelRetryRecover:
    def test_cancelling_queued_job_is_immediate(self) -> None:
        assert new_job().request_cancel().state is JobState.CANCELLED

    def test_cancelling_running_job_waits_for_step_boundary(self) -> None:
        job = running_job(AnalysisStep.VALIDATE).request_cancel()
        assert job.state is JobState.CANCELLING

        job = job.complete_step(AnalysisStep.EXTRACT)
        assert job.state is JobState.CANCELLING

        cancelled = job.confirm_cancel()
        assert cancelled.state is JobState.CANCELLED
        assert cancelled.completed_steps == (AnalysisStep.VALIDATE, AnalysisStep.EXTRACT)

    def test_terminal_job_cannot_be_cancelled(self) -> None:
        completed = new_job().model_copy(
            update={"state": JobState.COMPLETED, "completed_steps": ANALYSIS_STEPS}
        )
        with pytest.raises(InvalidStateTransition):
            completed.request_cancel()

    def test_retry_keeps_completed_steps_and_clears_failure(self) -> None:
        failed = running_job(AnalysisStep.VALIDATE).fail(AnalysisStep.EXTRACT, "parse_error")
        assert failed.state is JobState.FAILED
        assert failed.failed_step is AnalysisStep.EXTRACT

        retried = failed.retry()
        assert retried.state is JobState.QUEUED
        assert retried.completed_steps == (AnalysisStep.VALIDATE,)
        assert retried.next_step is AnalysisStep.EXTRACT
        assert retried.failed_step is None
        assert retried.error_code is None

    def test_fail_must_target_the_next_step(self) -> None:
        with pytest.raises(InvalidStateTransition):
            running_job().fail(AnalysisStep.RULES, "x")

    def test_recover_after_restart(self) -> None:
        interrupted = running_job(AnalysisStep.VALIDATE, AnalysisStep.EXTRACT)
        recovered = interrupted.recover_after_restart()
        assert recovered.state is JobState.QUEUED
        assert recovered.next_step is AnalysisStep.RULES

        cancelling = interrupted.request_cancel()
        assert cancelling.recover_after_restart().state is JobState.CANCELLED


class TestFindingAndEvidence:
    def _finding(self, status: FindingStatus, *evidence: Evidence) -> Finding:
        return Finding(
            job_id=uuid4(),
            status=status,
            severity=Severity.HIGH,
            confidence=0.9,
            finding_type="tolerance",
            location="page:1",
            message="공차 표기 누락",
            evidence=evidence,
        )

    def test_violation_requires_rule_evidence(self) -> None:
        case_only = Evidence(kind=EvidenceKind.CASE, ref_id="case-1", score=0.8)
        with pytest.raises(ValidationError):
            self._finding(FindingStatus.VIOLATION, case_only)

        rule = Evidence(kind=EvidenceKind.RULE, ref_id="R-001")
        assert self._finding(FindingStatus.VIOLATION, rule).status is FindingStatus.VIOLATION

    def test_suspected_may_rely_on_case_evidence(self) -> None:
        case = Evidence(kind=EvidenceKind.CASE, ref_id="case-1", score=0.8)
        assert self._finding(FindingStatus.SUSPECTED, case).status is FindingStatus.SUSPECTED

    @pytest.mark.parametrize("confidence", [-0.01, 1.01])
    def test_confidence_is_bounded(self, confidence: float) -> None:
        with pytest.raises(ValidationError):
            Finding(
                job_id=uuid4(),
                status=FindingStatus.INSUFFICIENT_INFORMATION,
                severity=Severity.LOW,
                confidence=confidence,
                finding_type="unit",
                location="page:1",
                message="단위 불명",
            )

    def test_bbox_must_be_ordered(self) -> None:
        with pytest.raises(ValidationError):
            Finding(
                job_id=uuid4(),
                status=FindingStatus.INSUFFICIENT_INFORMATION,
                severity=Severity.LOW,
                confidence=0.5,
                finding_type="unit",
                location="page:1",
                message="단위 불명",
                pixel_bbox=(10.0, 0.0, 5.0, 5.0),
            )


def test_timestamps_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError):
        ReviewProject(name="p", created_at=datetime(2026, 1, 1))  # noqa: DTZ001
