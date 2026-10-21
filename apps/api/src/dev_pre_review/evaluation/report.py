"""Evaluation report generation in JSON and Markdown formats.

References: TC-101, TC-102, NFR-001, NFR-002, plan.md.
"""

import json
from dataclasses import asdict, dataclass

from dev_pre_review.evaluation.metrics import (
    ClassificationMetrics,
    ExtractionMetrics,
    LatencyMetrics,
    RetrievalMetrics,
)


@dataclass(frozen=True)
class EvaluationReportMetrics:
    classification: ClassificationMetrics
    retrieval: RetrievalMetrics
    extraction: ExtractionMetrics
    latency: LatencyMetrics


@dataclass(frozen=True)
class EvaluationEvidence:
    build_id: str
    environment: str
    evaluator_id: str
    evaluator_capabilities: tuple[str, ...]
    manifest_sha256: str


@dataclass(frozen=True)
class SampleEvaluationEvidence:
    sample_id: str
    terminal_state: str
    error_code: str | None
    extraction_success: bool
    latency_ms: float


@dataclass(frozen=True)
class EvaluationReport:
    manifest_version: str
    dataset_name: str
    app_version: str
    split: str
    created_at: str
    evidence: EvaluationEvidence
    samples: tuple[SampleEvaluationEvidence, ...]
    metrics: EvaluationReportMetrics
    passed: bool
    violations: list[str]

    @property
    def exit_code(self) -> int:
        return 0 if self.passed else 1

    def to_json(self) -> str:
        data = {
            "manifest_version": self.manifest_version,
            "dataset_name": self.dataset_name,
            "app_version": self.app_version,
            "split": self.split,
            "created_at": self.created_at,
            "evidence": asdict(self.evidence),
            "samples": [asdict(sample) for sample in self.samples],
            "passed": self.passed,
            "violations": self.violations,
            "metrics": {
                "classification": asdict(self.metrics.classification),
                "retrieval": {
                    "available": self.metrics.retrieval.available,
                    "total_queries": self.metrics.retrieval.total_queries,
                    "top1_hit_rate": self.metrics.retrieval.hit_rate_at(1)
                    if self.metrics.retrieval.available
                    else None,
                    "top3_hit_rate": self.metrics.retrieval.hit_rate_at(3)
                    if self.metrics.retrieval.available
                    else None,
                    "top5_hit_rate": self.metrics.retrieval.hit_rate_at(5)
                    if self.metrics.retrieval.available
                    else None,
                    "mean_reciprocal_rank": self.metrics.retrieval.mean_reciprocal_rank
                    if self.metrics.retrieval.available
                    else None,
                },
                "extraction": {
                    "total_elements": self.metrics.extraction.total_elements,
                    "successful_elements": self.metrics.extraction.successful_elements,
                    "success_rate": self.metrics.extraction.success_rate,
                },
                "latency": asdict(self.metrics.latency),
            },
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    def to_markdown(self) -> str:
        status_badge = "✅ Pass" if self.passed else "❌ Fail"
        cls = self.metrics.classification
        ret = self.metrics.retrieval
        ext = self.metrics.extraction
        lat = self.metrics.latency

        lines = [
            "# Golden Set Evaluation Report",
            "",
            f"- **Status**: {status_badge}",
            f"- **Dataset**: {self.dataset_name} (Manifest v{self.manifest_version})",
            f"- **Split**: `{self.split}`",
            f"- **App Version**: `{self.app_version}`",
            f"- **Evaluated At**: {self.created_at}",
            f"- **Build ID**: `{self.evidence.build_id}`",
            f"- **Environment**: {self.evidence.environment}",
            f"- **Evaluator**: `{self.evidence.evaluator_id}`",
            f"- **Capabilities**: {', '.join(self.evidence.evaluator_capabilities)}",
            f"- **Manifest SHA-256**: `{self.evidence.manifest_sha256}`",
            "",
            "## Quality Gate Summary",
            "",
            "| Metric | Target (Gate) | Actual Result | Status |",
            "| --- | --- | --- | --- |",
            (
                f"| Extraction Success Rate | ≥ 95.0% | {ext.success_rate:.1%} | "
                f"{'✅' if ext.success_rate >= 0.95 else '❌'} |"
            ),
            (
                f"| Finding Precision | ≥ 90.0% | {cls.precision:.1%} | "
                f"{'✅' if cls.precision >= 0.90 else '❌'} |"
            ),
            (
                f"| Finding Recall | ≥ 80.0% | {cls.recall:.1%} | "
                f"{'✅' if cls.recall >= 0.80 else '❌'} |"
            ),
            (
                f"| Evidence Top-5 Hit Rate | ≥ 80.0% | {ret.hit_rate_at(5):.1%} | "
                f"{'✅' if ret.hit_rate_at(5) >= 0.80 else '❌'} |"
                if ret.available
                else "| Evidence Top-5 Hit Rate | ≥ 80.0% | unavailable | ❌ |"
            ),
            (
                f"| P95 Analysis Latency | ≤ 180,000 ms (3m) | {lat.p95:.1f} ms | "
                f"{'✅' if lat.p95 <= 180000.0 else '❌'} |"
            ),
            "",
        ]

        if self.violations:
            lines.extend(
                [
                    "## Violations",
                    "",
                ]
            )
            for v in self.violations:
                lines.append(f"- ⚠️ {v}")
            lines.append("")

        lines.extend(
            [
                "## Detailed Metrics",
                "",
                "### Classification",
                f"- True Positives: {cls.tp}",
                f"- False Positives: {cls.fp}",
                f"- False Negatives: {cls.fn}",
                f"- True Negatives: {cls.tn}",
                f"- F1-Score: {cls.f1_score:.3f}",
                "",
                "### Retrieval",
                f"- Available: {ret.available}",
                f"- Total Queries: {ret.total_queries}",
                f"- Top-1 Hit Rate: {ret.hit_rate_at(1):.1%}"
                if ret.available
                else "- Top-1 Hit Rate: unavailable",
                f"- Top-3 Hit Rate: {ret.hit_rate_at(3):.1%}"
                if ret.available
                else "- Top-3 Hit Rate: unavailable",
                f"- Top-5 Hit Rate: {ret.hit_rate_at(5):.1%}"
                if ret.available
                else "- Top-5 Hit Rate: unavailable",
                f"- MRR: {ret.mean_reciprocal_rank:.3f}" if ret.available else "- MRR: unavailable",
                "",
                "### Sample Execution Evidence",
                "",
                "| Sample | State | Extraction | Latency ms | Error |",
                "| --- | --- | --- | ---: | --- |",
                *[
                    (
                        f"| {sample.sample_id} | {sample.terminal_state} | "
                        f"{sample.extraction_success} | {sample.latency_ms:.1f} | "
                        f"{sample.error_code or '-'} |"
                    )
                    for sample in self.samples
                ],
                "",
                "### Performance & Latency",
                f"- Samples Tested: {lat.count}",
                f"- P50: {lat.p50:.1f} ms",
                f"- P95: {lat.p95:.1f} ms",
                f"- P99: {lat.p99:.1f} ms",
                f"- Max: {lat.max_latency:.1f} ms",
                f"- Mean: {lat.mean_latency:.1f} ms",
                "",
            ]
        )
        return "\n".join(lines)
