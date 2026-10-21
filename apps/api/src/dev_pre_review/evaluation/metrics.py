"""Quality metrics and threshold checks for golden set evaluation.

References: TC-101, TC-102, NFR-001, NFR-002.
"""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ClassificationMetrics:
    tp: int
    fp: int
    fn: int
    tn: int
    precision: float
    recall: float
    f1_score: float
    total_samples: int

    @classmethod
    def from_counts(cls, tp: int, fp: int, fn: int, tn: int) -> "ClassificationMetrics":
        total = tp + fp + fn + tn
        p_denom = tp + fp
        precision = (tp / p_denom) if p_denom > 0 else 0.0

        r_denom = tp + fn
        recall = (tp / r_denom) if r_denom > 0 else 0.0

        f1_denom = precision + recall
        f1 = (2.0 * precision * recall / f1_denom) if f1_denom > 0 else 0.0

        return cls(
            tp=tp,
            fp=fp,
            fn=fn,
            tn=tn,
            precision=precision,
            recall=recall,
            f1_score=f1,
            total_samples=total,
        )


@dataclass(frozen=True)
class RetrievalMetrics:
    total_queries: int
    ranks: tuple[int | None, ...]
    mean_reciprocal_rank: float
    available: bool = True

    @classmethod
    def from_ranks(cls, ranks: list[int | None]) -> "RetrievalMetrics":
        total = len(ranks)
        if total == 0:
            return cls(total_queries=0, ranks=(), mean_reciprocal_rank=0.0)

        reciprocal_sum = 0.0
        for r in ranks:
            if r is not None and r > 0:
                reciprocal_sum += 1.0 / r

        mrr = reciprocal_sum / total
        return cls(total_queries=total, ranks=tuple(ranks), mean_reciprocal_rank=mrr)

    def hit_rate_at(self, k: int) -> float:
        if self.total_queries == 0:
            return 0.0
        hits = sum(1 for r in self.ranks if r is not None and 1 <= r <= k)
        return hits / self.total_queries

    @classmethod
    def unavailable(cls) -> "RetrievalMetrics":
        return cls(total_queries=0, ranks=(), mean_reciprocal_rank=0.0, available=False)


@dataclass(frozen=True)
class ExtractionMetrics:
    total_elements: int
    successful_elements: int

    @property
    def success_rate(self) -> float:
        if self.total_elements == 0:
            return 1.0
        return self.successful_elements / self.total_elements


@dataclass(frozen=True)
class LatencyMetrics:
    count: int
    p50: float
    p95: float
    p99: float
    max_latency: float
    mean_latency: float

    @classmethod
    def from_list(cls, latencies: list[float]) -> "LatencyMetrics":
        if not latencies:
            return cls(
                count=0,
                p50=0.0,
                p95=0.0,
                p99=0.0,
                max_latency=0.0,
                mean_latency=0.0,
            )

        arr = np.array(latencies, dtype=float)
        return cls(
            count=len(latencies),
            p50=float(np.percentile(arr, 50)),
            p95=float(np.percentile(arr, 95)),
            p99=float(np.percentile(arr, 99)),
            max_latency=float(np.max(arr)),
            mean_latency=float(np.mean(arr)),
        )


@dataclass(frozen=True)
class QualityGateConfig:
    min_extraction_rate: float = 0.95
    min_precision: float = 0.90
    min_recall: float = 0.80
    min_top5_hit_rate: float = 0.80
    max_p95_latency_ms: float = 180000.0  # 3 minutes budget (TC-101)


def check_quality_gates(
    cls_metrics: ClassificationMetrics,
    ret_metrics: RetrievalMetrics,
    ext_metrics: ExtractionMetrics,
    lat_metrics: LatencyMetrics,
    config: QualityGateConfig | None = None,
) -> tuple[bool, list[str]]:
    """Checks all evaluation metrics against quality gate thresholds."""
    cfg = config or QualityGateConfig()
    violations: list[str] = []

    if ext_metrics.success_rate < cfg.min_extraction_rate:
        violations.append(
            f"Extraction success rate {ext_metrics.success_rate:.1%} "
            f"below threshold {cfg.min_extraction_rate:.1%}"
        )

    if cls_metrics.precision < cfg.min_precision:
        violations.append(
            f"Finding precision {cls_metrics.precision:.1%} below threshold {cfg.min_precision:.1%}"
        )

    if cls_metrics.recall < cfg.min_recall:
        violations.append(
            f"Finding recall {cls_metrics.recall:.1%} below threshold {cfg.min_recall:.1%}"
        )

    if ret_metrics.available:
        top5_hit = ret_metrics.hit_rate_at(5)
        if top5_hit < cfg.min_top5_hit_rate:
            violations.append(
                f"Evidence Top-5 hit rate {top5_hit:.1%} "
                f"below threshold {cfg.min_top5_hit_rate:.1%}"
            )

    if lat_metrics.count > 0 and lat_metrics.p95 > cfg.max_p95_latency_ms:
        violations.append(
            f"P95 latency {lat_metrics.p95:.1f}ms "
            f"exceeds performance budget {cfg.max_p95_latency_ms:.1f}ms"
        )

    return len(violations) == 0, violations
