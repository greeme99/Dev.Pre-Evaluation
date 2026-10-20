"""Tests for AnalysisPipeline execution, checkpoints, and cancel handling.

FN-007, JOB-001~JOB-005, TC-025, TC-026.
"""

from uuid import uuid4

from dev_pre_review.analysis.fusion import FindingFusion
from dev_pre_review.analysis.pipeline import AnalysisPipeline, PipelineContext
from dev_pre_review.domain.enums import (
    AnalysisStep,
    DrawingType,
    FindingStatus,
    JobState,
    RuleOperator,
    RuleState,
    Severity,
)
from dev_pre_review.domain.models import AnalysisJob, RuleDefinition, utc_now
from dev_pre_review.drawings.contracts import DrawingDocument, TextRegion
from dev_pre_review.models.generation import LocalSuggestionProvider
from dev_pre_review.rules.engine import RuleEvaluator


class InMemoryJobRepo:
    def __init__(self) -> None:
        self.jobs: dict[uuid4, AnalysisJob] = {}

    def get(self, job_id) -> AnalysisJob:
        return self.jobs[job_id]

    def update(self, job: AnalysisJob) -> None:
        self.jobs[job.id] = job


def make_test_job(job_id, project_id, drawing_id) -> AnalysisJob:
    return AnalysisJob(
        id=job_id,
        project_id=project_id,
        drawing_id=drawing_id,
        state=JobState.QUEUED,
        created_at=utc_now(),
        updated_at=utc_now(),
    )


def test_pipeline_executes_all_steps_and_records_checkpoints() -> None:
    job_id = uuid4()
    p_id = uuid4()
    d_id = uuid4()

    job_repo = InMemoryJobRepo()
    job = make_test_job(job_id, p_id, d_id)
    job_repo.jobs[job_id] = job

    # Create dummy document with text region
    doc = DrawingDocument(
        drawing_id=d_id,
        drawing_type=DrawingType.PDF,
        file_name="test.pdf",
        file_sha256="0" * 64,
        page_count=1,
        regions=[
            TextRegion(
                page_or_sheet=1,
                raw_text="공차: +-0.05 mm",
                pixel_bbox=(10.0, 10.0, 50.0, 50.0),
                confidence=1.0,
            )
        ],
    )

    rule = RuleDefinition(
        id=uuid4(),
        project_id=p_id,
        drawing_types=(DrawingType.PDF,),
        field="tolerance",
        operator=RuleOperator.MAX,
        value="0.02",
        unit="mm",
        severity=Severity.HIGH,
        state=RuleState.APPROVED,
    )

    pipeline = AnalysisPipeline(
        job_repo=job_repo,
        rule_evaluator=RuleEvaluator(),
        fusion_engine=FindingFusion(),
        suggestion_provider=LocalSuggestionProvider(),
    )

    result = pipeline.run(
        job_id=job_id,
        context=PipelineContext(
            document=doc,
            approved_rules=[rule],
            retrieved_cases=[],
            visual_evidences=[],
        ),
    )

    final_job = job_repo.get(job_id)
    assert final_job.state == JobState.COMPLETED
    assert len(final_job.completed_steps) == 6
    assert final_job.completed_steps[-1] == AnalysisStep.EXPORT_READY

    assert len(result.findings) == 1
    assert result.findings[0].status == FindingStatus.VIOLATION
    assert len(result.suggestions) >= 1


def test_pipeline_stops_at_step_boundary_when_cancelling() -> None:
    job_id = uuid4()
    p_id = uuid4()
    d_id = uuid4()

    job_repo = InMemoryJobRepo()
    job = make_test_job(job_id, p_id, d_id)
    job_repo.jobs[job_id] = job

    doc = DrawingDocument(
        drawing_id=d_id,
        drawing_type=DrawingType.PDF,
        file_name="test.pdf",
        file_sha256="0" * 64,
        page_count=1,
        regions=[],
    )

    pipeline = AnalysisPipeline(
        job_repo=job_repo,
        rule_evaluator=RuleEvaluator(),
        fusion_engine=FindingFusion(),
        suggestion_provider=LocalSuggestionProvider(),
    )

    # Trigger cancel before/during execution
    def cancel_after_validate(step: AnalysisStep) -> None:
        if step == AnalysisStep.VALIDATE:
            current = job_repo.get(job_id)
            job_repo.update(current.request_cancel())

    pipeline.on_step_completed = cancel_after_validate

    pipeline.run(
        job_id=job_id,
        context=PipelineContext(
            document=doc,
            approved_rules=[],
            retrieved_cases=[],
            visual_evidences=[],
        ),
    )

    cancelled_job = job_repo.get(job_id)
    assert cancelled_job.state == JobState.CANCELLED
    # Execution stopped at step boundary
    assert len(cancelled_job.completed_steps) == 1
    assert cancelled_job.completed_steps[0] == AnalysisStep.VALIDATE
