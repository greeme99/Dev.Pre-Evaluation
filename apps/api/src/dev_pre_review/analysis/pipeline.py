"""Analysis pipeline orchestration with checkpoints and cancel support (FN-007, JOB-001~JOB-005)."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dev_pre_review.analysis.fusion import FindingFusion
from dev_pre_review.domain.enums import AnalysisStep, JobState
from dev_pre_review.domain.models import Finding, RuleDefinition
from dev_pre_review.drawings.contracts import DrawingDocument
from dev_pre_review.models.generation import ImprovementSuggestion, SuggestionProvider
from dev_pre_review.retrieval.hybrid import RetrievedCase
from dev_pre_review.retrieval.pixel_rag import VisualEvidence
from dev_pre_review.rules.engine import RuleEvaluator


class PipelineContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    document: DrawingDocument
    approved_rules: list[RuleDefinition] = Field(default_factory=list)
    retrieved_cases: list[RetrievedCase] = Field(default_factory=list)
    visual_evidences: list[VisualEvidence] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    job_id: UUID
    state: JobState
    findings: list[Finding]
    suggestions: list[ImprovementSuggestion]
    completed_steps: list[AnalysisStep]


class AnalysisPipeline:
    def __init__(
        self,
        job_repo: Any,
        rule_evaluator: RuleEvaluator,
        fusion_engine: FindingFusion,
        suggestion_provider: SuggestionProvider,
        on_step_completed: Callable[[AnalysisStep], None] | None = None,
    ) -> None:
        self.job_repo = job_repo
        self.rule_evaluator = rule_evaluator
        self.fusion_engine = fusion_engine
        self.suggestion_provider = suggestion_provider
        self.on_step_completed = on_step_completed

    def run(self, job_id: UUID, context: PipelineContext) -> AnalysisResult:
        job = self.job_repo.get(job_id)
        if job.state is JobState.QUEUED:
            job = job.start()
            self.job_repo.update(job)

        rule_findings: list[Finding] = []
        all_findings: list[Finding] = []
        suggestions: list[ImprovementSuggestion] = []

        # Sequential pipeline steps
        steps_to_run = [
            AnalysisStep.VALIDATE,
            AnalysisStep.EXTRACT,
            AnalysisStep.RULES,
            AnalysisStep.RETRIEVE,
            AnalysisStep.SUGGEST,
            AnalysisStep.EXPORT_READY,
        ]

        for step in steps_to_run:
            if step in job.completed_steps:
                continue

            # Execute step work
            if step is AnalysisStep.VALIDATE:
                pass
            elif step is AnalysisStep.EXTRACT:
                pass
            elif step is AnalysisStep.RULES:
                rule_res = self.rule_evaluator.evaluate(
                    context.document,
                    context.approved_rules,
                    job_id=job.id,
                )
                rule_findings = rule_res.findings
            elif step is AnalysisStep.RETRIEVE:
                pass
            elif step is AnalysisStep.SUGGEST:
                all_findings = self.fusion_engine.merge(
                    rule_findings=rule_findings,
                    retrieved_cases=context.retrieved_cases,
                    visual_evidences=context.visual_evidences,
                    job_id=job.id,
                )
                suggestions = [self.suggestion_provider.suggest(f) for f in all_findings]
            elif step is AnalysisStep.EXPORT_READY:
                pass

            # Advance checkpoint
            job = job.complete_step(step)
            self.job_repo.update(job)

            if self.on_step_completed:
                self.on_step_completed(step)

            # Check cancel at step boundary
            current_job = self.job_repo.get(job_id)
            if current_job.state is JobState.CANCELLING:
                cancelled_job = current_job.confirm_cancel()
                self.job_repo.update(cancelled_job)
                return AnalysisResult(
                    job_id=job_id,
                    state=JobState.CANCELLED,
                    findings=all_findings or rule_findings,
                    suggestions=suggestions,
                    completed_steps=list(cancelled_job.completed_steps),
                )

        final_job = self.job_repo.get(job_id)
        return AnalysisResult(
            job_id=job_id,
            state=final_job.state,
            findings=all_findings or rule_findings,
            suggestions=suggestions,
            completed_steps=list(final_job.completed_steps),
        )
