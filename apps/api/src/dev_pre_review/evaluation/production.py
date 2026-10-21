"""Golden evaluator backed by the persisted production analysis workflow."""

import tempfile
import time
from pathlib import Path
from typing import Any

from dev_pre_review.analysis.runtime import create_analysis_worker
from dev_pre_review.domain.enums import AnalysisStep, DrawingType, EvidenceKind
from dev_pre_review.domain.models import AnalysisJob, DrawingArtifact, ReviewProject, utc_now
from dev_pre_review.evaluation.runner import GoldenSample
from dev_pre_review.storage.database import Database
from dev_pre_review.storage.files import FileStore
from dev_pre_review.storage.repositories import (
    DrawingRepository,
    FindingRepository,
    ProjectRepository,
)


class ProductionSampleEvaluator:
    """Execute one sample through the same validator/parser/rule worker used by the API."""

    evaluator_id = "production-rule-pipeline-v1"
    capabilities = ("validation", "extraction", "rule_evaluation")

    def __call__(self, sample: GoldenSample) -> dict[str, Any]:
        started = time.perf_counter()
        source = Path(sample.file_path)
        drawing_type = self._drawing_type(source)
        if drawing_type is None:
            return self._failed(started, "unsupported_evaluation_file")

        with tempfile.TemporaryDirectory(prefix="dev-pre-review-eval-") as temporary_dir:
            root = Path(temporary_dir)
            database = Database.from_path(root / "evaluation.db")
            try:
                database.upgrade()
                project = ProjectRepository(database.sessions).add(
                    ReviewProject(name=f"Golden sample {sample.id}", created_at=utc_now())
                )
                stored = FileStore(root / "artifacts").save_bytes(source.read_bytes(), source.name)
                drawing = DrawingRepository(database.sessions).add(
                    DrawingArtifact(
                        project_id=project.id,
                        sha256=stored.sha256,
                        drawing_type=drawing_type,
                        source_name=source.name,
                        parser_version="evaluation-production-v1",
                        created_at=utc_now(),
                    )
                )
                worker = create_analysis_worker(database, root / "artifacts")
                queued = worker.runner.enqueue(
                    AnalysisJob(
                        project_id=project.id,
                        drawing_id=drawing.id,
                        config_versions={"analysis_profile": "rule_only"},
                        created_at=utc_now(),
                        updated_at=utc_now(),
                    )
                )
                analysis_started = time.perf_counter()
                final = worker.runner.run_next()
                if final is None or final.id != queued.id:
                    return self._failed(analysis_started, "evaluation_job_not_run")
                analysis_latency_ms = (time.perf_counter() - analysis_started) * 1000

                findings = FindingRepository(database.sessions).list_for_job(final.id)
                predicted = []
                for finding in findings:
                    rule_code = next(
                        (
                            item.ref_id
                            for item in finding.evidence
                            if item.kind is EvidenceKind.RULE
                        ),
                        finding.finding_type,
                    )
                    predicted.append(
                        {
                            "rule_code": rule_code,
                            "status": finding.status.value,
                            "severity": finding.severity.value,
                        }
                    )

                return {
                    "predicted_findings": predicted,
                    "retrieval_ranks": [],
                    "retrieval_available": False,
                    "extraction_success": AnalysisStep.EXTRACT in final.completed_steps,
                    "latency_ms": analysis_latency_ms,
                    "terminal_state": final.state.value,
                    "error_code": final.error_code,
                }
            except Exception as exc:  # noqa: BLE001
                return self._failed(started, f"evaluation_exception:{type(exc).__name__}")
            finally:
                database.dispose()

    @staticmethod
    def _drawing_type(path: Path) -> DrawingType | None:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return DrawingType.PDF
        if suffix == ".dxf":
            return DrawingType.DXF
        return None

    @staticmethod
    def _failed(started: float, error_code: str) -> dict[str, Any]:
        return {
            "predicted_findings": [],
            "retrieval_ranks": [],
            "retrieval_available": False,
            "extraction_success": False,
            "latency_ms": (time.perf_counter() - started) * 1000,
            "terminal_state": "failed",
            "error_code": error_code,
        }
