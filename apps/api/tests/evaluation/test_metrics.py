"""Tests for evaluation metrics and quality gate threshold checks."""

import pytest

from dev_pre_review.evaluation.metrics import (
    ClassificationMetrics,
    ExtractionMetrics,
    LatencyMetrics,
    QualityGateConfig,
    RetrievalMetrics,
    check_quality_gates,
)


def test_classification_metrics_standard_confusion_matrix() -> None:
    # TP=90, FP=10 -> precision = 90 / 100 = 0.90
    # TP=90, FN=10 -> recall = 90 / 100 = 0.90
    metrics = ClassificationMetrics.from_counts(tp=90, fp=10, fn=10, tn=890)
    assert pytest.approx(metrics.precision, 0.001) == 0.90
    assert pytest.approx(metrics.recall, 0.001) == 0.90
    assert pytest.approx(metrics.f1_score, 0.001) == 0.90
    assert metrics.total_samples == 1000


def test_classification_metrics_zero_denominators() -> None:
    # All zeros
    metrics = ClassificationMetrics.from_counts(tp=0, fp=0, fn=0, tn=0)
    assert metrics.precision == 0.0
    assert metrics.recall == 0.0
    assert metrics.f1_score == 0.0


def test_retrieval_metrics_top_k() -> None:
    # 10 queries:
    # 8 queries found relevant item in top 5, 2 did not.
    # rank hits: [1, 1, 2, 3, 4, 5, 5, 5, None, None]
    ranks = [1, 1, 2, 3, 4, 5, 5, 5, None, None]
    metrics = RetrievalMetrics.from_ranks(ranks)
    assert metrics.total_queries == 10
    assert pytest.approx(metrics.hit_rate_at(1), 0.01) == 0.20  # 2 / 10
    assert pytest.approx(metrics.hit_rate_at(3), 0.01) == 0.40  # 4 / 10
    assert pytest.approx(metrics.hit_rate_at(5), 0.01) == 0.80  # 8 / 10
    # MRR: (1/1 + 1/1 + 1/2 + 1/3 + 1/4 + 1/5 + 1/5 + 1/5 + 0 + 0) / 10
    expected_mrr = (1 + 1 + 0.5 + (1 / 3) + 0.25 + 0.2 + 0.2 + 0.2) / 10
    assert pytest.approx(metrics.mean_reciprocal_rank, 0.01) == expected_mrr


def test_extraction_metrics() -> None:
    metrics = ExtractionMetrics(total_elements=100, successful_elements=96)
    assert pytest.approx(metrics.success_rate, 0.001) == 0.96

    zero_metrics = ExtractionMetrics(total_elements=0, successful_elements=0)
    assert zero_metrics.success_rate == 1.0


def test_latency_metrics_percentiles() -> None:
    latencies = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    metrics = LatencyMetrics.from_list(latencies)
    assert metrics.count == 10
    assert pytest.approx(metrics.p50, 0.01) == 55.0
    assert pytest.approx(metrics.p95, 0.01) == 95.5
    assert pytest.approx(metrics.p99, 0.01) == 99.1
    assert metrics.max_latency == 100.0
    assert pytest.approx(metrics.mean_latency, 0.01) == 55.0


def test_check_quality_gates_pass() -> None:
    cls_metrics = ClassificationMetrics.from_counts(tp=92, fp=8, fn=15, tn=885)  # P=92%, R=86%
    ret_metrics = RetrievalMetrics.from_ranks([1, 2, 3, 4, 5, 1, 2, 3, None, None])  # Top-5 = 80%
    ext_metrics = ExtractionMetrics(total_elements=100, successful_elements=97)  # 97%
    lat_metrics = LatencyMetrics.from_list([1000.0, 2000.0, 3000.0])  # well under 180s

    cfg = QualityGateConfig(
        min_extraction_rate=0.95,
        min_precision=0.90,
        min_recall=0.80,
        min_top5_hit_rate=0.80,
        max_p95_latency_ms=180000.0,
    )

    passed, violations = check_quality_gates(
        cls_metrics=cls_metrics,
        ret_metrics=ret_metrics,
        ext_metrics=ext_metrics,
        lat_metrics=lat_metrics,
        config=cfg,
    )
    assert passed is True
    assert violations == []


def test_check_quality_gates_failures() -> None:
    # Low precision (80%), Low recall (70%), Low extraction (90%), Slow (200s)
    cls_metrics = ClassificationMetrics.from_counts(tp=80, fp=20, fn=30, tn=870)
    ret_metrics = RetrievalMetrics.from_ranks([1, 2, None, None, None])  # Top-5 = 40%
    ext_metrics = ExtractionMetrics(total_elements=100, successful_elements=90)
    lat_metrics = LatencyMetrics.from_list([200000.0])

    cfg = QualityGateConfig()
    passed, violations = check_quality_gates(
        cls_metrics=cls_metrics,
        ret_metrics=ret_metrics,
        ext_metrics=ext_metrics,
        lat_metrics=lat_metrics,
        config=cfg,
    )
    assert passed is False
    assert len(violations) >= 4
