"""Build the production drawing analysis worker from persistent services."""

from collections import Counter
from pathlib import Path
from uuid import UUID

from dev_pre_review.analysis.exceptions import StepFailed
from dev_pre_review.analysis.jobs import JobRunner
from dev_pre_review.analysis.worker import JobWorker
from dev_pre_review.domain.enums import AnalysisStep, RuleState
from dev_pre_review.domain.models import AnalysisJob, DrawingArtifact, Finding
from dev_pre_review.drawings.contracts import DrawingDocument
from dev_pre_review.drawings.ports import get_default_registry
from dev_pre_review.drawings.validation import DrawingValidator
from dev_pre_review.rules.catalog import RuleCatalog
from dev_pre_review.rules.engine import RuleEvaluator
from dev_pre_review.storage.database import Database
from dev_pre_review.storage.files import FileStore
from dev_pre_review.storage.repositories import (
    DrawingRepository,
    FindingRepository,
    JobRepository,
)


def create_analysis_worker(db: Database, artifacts_dir: Path) -> JobWorker:
    jobs = JobRepository(db.sessions)
    drawings = DrawingRepository(db.sessions)
    findings = FindingRepository(db.sessions)
    rules = RuleCatalog(db.sessions)
    files = FileStore(artifacts_dir)
    validator = DrawingValidator()
    parser_registry = get_default_registry()
    documents: dict[UUID, DrawingDocument] = {}

    def parse_document(drawing: DrawingArtifact) -> DrawingDocument:
        stored = files.resolve(drawing)
        try:
            parsed = parser_registry.get(drawing.drawing_type).parse(stored)
        except Exception as exc:
            raise StepFailed("drawing_parse_failed") from exc
        return parsed.model_copy(update={"drawing_id": drawing.id})

    def validate(job: AnalysisJob) -> None:
        drawing = drawings.get(job.drawing_id)
        stored = files.resolve(drawing)
        report = validator.validate(stored.path, drawing.source_name)
        if not report.is_valid:
            code = report.errors[0].code.value if report.errors else "invalid_drawing"
            raise StepFailed(code)

    def extract(job: AnalysisJob) -> None:
        drawing = drawings.get(job.drawing_id)
        documents[job.id] = parse_document(drawing)

    def evaluate_rules(job: AnalysisJob) -> None:
        document = documents.get(job.id)
        if document is None:
            document = parse_document(drawings.get(job.drawing_id))
            documents[job.id] = document
        approved = rules.list_rules(project_id=job.project_id, state=RuleState.APPROVED)
        rule_findings = RuleEvaluator().evaluate(document, approved, job_id=job.id).findings
        existing_signatures = Counter(
            finding_signature(finding) for finding in findings.list_for_job(job.id)
        )
        evaluated_signatures: Counter[tuple[object, ...]] = Counter()
        new_findings: list[Finding] = []
        for finding in rule_findings:
            signature = finding_signature(finding)
            evaluated_signatures[signature] += 1
            if evaluated_signatures[signature] > existing_signatures[signature]:
                new_findings.append(finding)
        if new_findings:
            findings.add_many(new_findings)

    def finding_signature(finding: Finding) -> tuple[object, ...]:
        evidence = tuple(
            (item.kind.value, item.ref_id, item.score, item.location) for item in finding.evidence
        )
        return (
            finding.status.value,
            finding.severity.value,
            finding.confidence,
            finding.finding_type,
            finding.location,
            finding.message,
            finding.pixel_bbox,
            finding.cad_bbox,
            evidence,
        )

    def skip_optional_capability(_job: AnalysisJob) -> None:
        # The persisted analysis_profile identifies this as rule-only execution.
        return

    return JobWorker(
        JobRunner(
            jobs,
            {
                AnalysisStep.VALIDATE: validate,
                AnalysisStep.EXTRACT: extract,
                AnalysisStep.RULES: evaluate_rules,
                AnalysisStep.RETRIEVE: skip_optional_capability,
                AnalysisStep.SUGGEST: skip_optional_capability,
                AnalysisStep.EXPORT_READY: skip_optional_capability,
            },
        )
    )
