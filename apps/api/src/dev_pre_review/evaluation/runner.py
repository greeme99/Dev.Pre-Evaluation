"""Evaluation runner executing golden set evaluation pipelines.

References: TC-101, TC-102, NFR-001, NFR-002, plan.md.
"""

import hashlib
import json
import os
import platform
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from dev_pre_review import __version__
from dev_pre_review.domain.models import utc_now
from dev_pre_review.evaluation.metrics import (
    ClassificationMetrics,
    ExtractionMetrics,
    LatencyMetrics,
    QualityGateConfig,
    RetrievalMetrics,
    check_quality_gates,
)
from dev_pre_review.evaluation.report import (
    EvaluationEvidence,
    EvaluationReport,
    EvaluationReportMetrics,
    SampleEvaluationEvidence,
)


class EvaluationDatasetSplit(StrEnum):
    TUNING = "tuning"
    FINAL = "final"


class GoldenSample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    file_path: str
    sha256: str
    split: EvaluationDatasetSplit
    expected_findings: list[dict[str, Any]] = Field(default_factory=list)
    expected_evidence_queries: list[str] = Field(default_factory=list)


class EvaluationManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest_version: str
    dataset_name: str
    description: str = ""
    samples: list[GoldenSample] = Field(default_factory=list)

    @classmethod
    def from_file(cls, path: Path) -> "EvaluationManifest":
        content = json.loads(path.read_text(encoding="utf-8"))
        return cls.model_validate(content)

    def verify_integrity(self) -> None:
        """Verifies that all files exist and match their expected SHA-256 hashes."""
        for sample in self.samples:
            p = Path(sample.file_path)
            if not p.exists():
                raise FileNotFoundError(f"Sample file {sample.file_path} not found")
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            if digest.lower() != sample.sha256.lower():
                msg = f"Hash mismatch for '{sample.id}': expected {sample.sha256}, got {digest}"
                raise ValueError(msg)

    def get_samples(self, split: EvaluationDatasetSplit) -> list[GoldenSample]:
        return [s for s in self.samples if s.split == split]


@dataclass
class EvaluationRunner:
    manifest: EvaluationManifest
    config: QualityGateConfig = QualityGateConfig()

    def evaluate(
        self,
        split: EvaluationDatasetSplit,
        eval_fn: Callable[[GoldenSample], dict[str, Any]],
        evidence: EvaluationEvidence | None = None,
    ) -> EvaluationReport:
        """Evaluates all samples for a specific dataset split."""
        samples = self.manifest.get_samples(split)

        tp = 0
        fp = 0
        fn = 0
        tn = 0

        all_ranks: list[int | None] = []
        total_extractions = len(samples)
        successful_extractions = 0
        latencies: list[float] = []
        unavailable_retrieval_queries = 0
        sample_evidence: list[SampleEvaluationEvidence] = []

        for sample in samples:
            res = eval_fn(sample)

            if res.get("extraction_success", False):
                successful_extractions += 1

            latency = res.get("latency_ms")
            if isinstance(latency, int | float):
                latencies.append(float(latency))
            else:
                latency = 0.0

            extraction_success = bool(res.get("extraction_success", False))
            sample_evidence.append(
                SampleEvaluationEvidence(
                    sample_id=sample.id,
                    terminal_state=str(
                        res.get(
                            "terminal_state",
                            "completed" if extraction_success else "failed",
                        )
                    ),
                    error_code=str(res["error_code"]) if res.get("error_code") else None,
                    extraction_success=extraction_success,
                    latency_ms=float(latency),
                )
            )

            if sample.expected_evidence_queries and not res.get("retrieval_available", True):
                unavailable_retrieval_queries += len(sample.expected_evidence_queries)
            else:
                ranks = res.get("retrieval_ranks", [])
                all_ranks.extend(ranks)

            predicted = res.get("predicted_findings", [])
            expected = sample.expected_findings

            # Key comparison by (rule_code, status)
            expected_keys = {(f.get("rule_code"), f.get("status")) for f in expected}
            predicted_keys = {(f.get("rule_code"), f.get("status")) for f in predicted}

            matched = expected_keys.intersection(predicted_keys)
            sample_tp = len(matched)
            sample_fp = len(predicted_keys - expected_keys)
            sample_fn = len(expected_keys - predicted_keys)

            tp += sample_tp
            fp += sample_fp
            fn += sample_fn

            # If both expected and predicted are empty (compliant drawing)
            if not expected_keys and not predicted_keys:
                tn += 1

        cls_metrics = ClassificationMetrics.from_counts(tp=tp, fp=fp, fn=fn, tn=tn)
        ret_metrics = (
            RetrievalMetrics.unavailable()
            if unavailable_retrieval_queries
            else RetrievalMetrics.from_ranks(all_ranks)
        )
        ext_metrics = ExtractionMetrics(
            total_elements=total_extractions,
            successful_elements=successful_extractions,
        )
        lat_metrics = LatencyMetrics.from_list(latencies)

        passed, violations = check_quality_gates(
            cls_metrics=cls_metrics,
            ret_metrics=ret_metrics,
            ext_metrics=ext_metrics,
            lat_metrics=lat_metrics,
            config=self.config,
        )
        if unavailable_retrieval_queries:
            violations.append(
                "Evidence retrieval evaluator unavailable for "
                f"{unavailable_retrieval_queries} golden queries"
            )
            passed = False

        report_evidence = evidence or EvaluationEvidence(
            build_id=os.environ.get("DEV_PRE_REVIEW_BUILD_ID")
            or os.environ.get("GITHUB_SHA")
            or "local-unverified",
            environment=f"{platform.platform()}; Python {platform.python_version()}",
            evaluator_id=getattr(eval_fn, "evaluator_id", "injected-evaluator"),
            evaluator_capabilities=tuple(getattr(eval_fn, "capabilities", ("unspecified",))),
            manifest_sha256="unavailable",
        )

        return EvaluationReport(
            manifest_version=self.manifest.manifest_version,
            dataset_name=self.manifest.dataset_name,
            app_version=__version__,
            split=split.value,
            created_at=utc_now().isoformat(),
            evidence=report_evidence,
            samples=tuple(sample_evidence),
            metrics=EvaluationReportMetrics(
                classification=cls_metrics,
                retrieval=ret_metrics,
                extraction=ext_metrics,
                latency=lat_metrics,
            ),
            passed=passed,
            violations=violations,
        )
