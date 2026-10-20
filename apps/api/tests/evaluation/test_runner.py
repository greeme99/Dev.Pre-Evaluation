"""Tests for evaluation runner and report generation."""

import hashlib
import json
from pathlib import Path

import pytest

from dev_pre_review.evaluation.report import EvaluationReport
from dev_pre_review.evaluation.runner import (
    EvaluationDatasetSplit,
    EvaluationManifest,
    EvaluationRunner,
    GoldenSample,
)


@pytest.fixture
def sample_manifest_file(tmp_path: Path) -> Path:
    # Create two synthetic fixture files
    f1 = tmp_path / "sample1.pdf"
    f1.write_bytes(b"%PDF-1.4 dummy content 1")
    hash1 = hashlib.sha256(f1.read_bytes()).hexdigest()

    f2 = tmp_path / "sample2.dxf"
    f2.write_bytes(b"0\nSECTION\n2\nHEADER\n0\nENDSEC\n0\nEOF\n")
    hash2 = hashlib.sha256(f2.read_bytes()).hexdigest()

    manifest_data = {
        "manifest_version": "1.0.0",
        "dataset_name": "TestGoldenSet",
        "description": "Synthetic golden set for evaluation unit tests",
        "samples": [
            {
                "id": "sample-001",
                "file_path": str(f1),
                "sha256": hash1,
                "split": "tuning",
                "expected_findings": [
                    {
                        "rule_code": "CL-001",
                        "status": "violation",
                        "severity": "high",
                    }
                ],
                "expected_evidence_queries": ["배관 간격"],
            },
            {
                "id": "sample-002",
                "file_path": str(f2),
                "sha256": hash2,
                "split": "final",
                "expected_findings": [],
                "expected_evidence_queries": [],
            },
        ],
    }

    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")
    return manifest_file


def test_manifest_load_and_hash_verification(sample_manifest_file: Path) -> None:
    manifest = EvaluationManifest.from_file(sample_manifest_file)
    assert manifest.dataset_name == "TestGoldenSet"
    assert len(manifest.samples) == 2

    # Verify hashes check out
    manifest.verify_integrity()


def test_manifest_hash_mismatch(sample_manifest_file: Path) -> None:
    manifest = EvaluationManifest.from_file(sample_manifest_file)
    # Corrupt first sample expected hash
    manifest.samples[0].sha256 = "0000000000000000000000000000000000000000000000000000000000000000"
    with pytest.raises(ValueError, match="Hash mismatch"):
        manifest.verify_integrity()


def test_runner_filter_split(sample_manifest_file: Path) -> None:
    manifest = EvaluationManifest.from_file(sample_manifest_file)
    tuning_samples = manifest.get_samples(EvaluationDatasetSplit.TUNING)
    final_samples = manifest.get_samples(EvaluationDatasetSplit.FINAL)

    assert len(tuning_samples) == 1
    assert tuning_samples[0].id == "sample-001"
    assert len(final_samples) == 1
    assert final_samples[0].id == "sample-002"


def test_runner_execution_and_report_generation(sample_manifest_file: Path) -> None:
    manifest = EvaluationManifest.from_file(sample_manifest_file)
    runner = EvaluationRunner(manifest=manifest)

    # Mock prediction provider that matches sample expectations perfectly
    def mock_evaluator(sample: GoldenSample) -> dict:
        return {
            "predicted_findings": sample.expected_findings,
            "retrieval_ranks": [1] * len(sample.expected_evidence_queries),
            "extraction_success": True,
            "latency_ms": 120.0,
        }

    report = runner.evaluate(
        split=EvaluationDatasetSplit.TUNING,
        eval_fn=mock_evaluator,
    )

    assert isinstance(report, EvaluationReport)
    assert report.passed is True
    assert report.violations == []
    assert report.metrics.classification.precision == 1.0
    assert report.metrics.classification.recall == 1.0
    assert report.metrics.extraction.success_rate == 1.0

    # Markdown format check
    md = report.to_markdown()
    assert "# Golden Set Evaluation Report" in md
    assert "Pass" in md
    assert "CL-001" not in md  # No raw findings dump in high-level report

    # JSON format check
    data = json.loads(report.to_json())
    assert data["passed"] is True
    assert "metrics" in data
