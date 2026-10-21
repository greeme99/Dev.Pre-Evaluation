"""Production-path golden evaluation must never echo expected answers."""

import hashlib
import json
import sys
from pathlib import Path

from dev_pre_review.evaluation.cli import main
from dev_pre_review.evaluation.production import ProductionSampleEvaluator
from dev_pre_review.evaluation.runner import EvaluationDatasetSplit, GoldenSample

FIXTURE = Path("tests/fixtures/dxf/missing-xref.dxf")


def _sample() -> GoldenSample:
    return GoldenSample(
        id="actual-pipeline",
        file_path=str(FIXTURE),
        sha256=hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        split=EvaluationDatasetSplit.FINAL,
        expected_findings=[
            {"rule_code": "FABRICATED-EXPECTED", "status": "violation", "severity": "high"}
        ],
        expected_evidence_queries=["unsupported retrieval query"],
    )


def test_production_evaluator_uses_persisted_pipeline_output() -> None:
    result = ProductionSampleEvaluator()(_sample())

    predicted = result["predicted_findings"]
    assert result["extraction_success"] is True
    assert result["retrieval_available"] is False
    assert any(item["rule_code"] == "quality_blocked" for item in predicted)
    assert all(item["rule_code"] != "FABRICATED-EXPECTED" for item in predicted)


def test_cli_reports_real_failure_and_execution_evidence(tmp_path: Path, monkeypatch) -> None:
    sample = _sample()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": "test-1",
                "dataset_name": "non-echo-regression",
                "samples": [sample.model_dump(mode="json")],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evaluation",
            "--manifest",
            str(manifest_path),
            "--split",
            "final",
            "--format",
            "json",
            "--output",
            str(output),
        ],
    )

    assert main() == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["passed"] is False
    assert report["metrics"]["classification"]["precision"] < 1.0
    assert any("unavailable" in violation.lower() for violation in report["violations"])
    assert not any("Top-5 hit rate" in violation for violation in report["violations"])
    assert report["metrics"]["retrieval"]["available"] is False
    assert report["metrics"]["retrieval"]["top5_hit_rate"] is None
    assert report["samples"][0]["sample_id"] == "actual-pipeline"
    assert report["samples"][0]["terminal_state"] == "completed"
    assert report["evidence"]["evaluator_id"] == "production-rule-pipeline-v1"
    assert (
        report["evidence"]["manifest_sha256"]
        == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    )
    assert report["evidence"]["build_id"]
    assert report["evidence"]["environment"]
