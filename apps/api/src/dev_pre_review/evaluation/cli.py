"""CLI entrypoint for running golden set evaluation and quality gate verification."""

import argparse
import hashlib
import os
import platform
import sys
from pathlib import Path

from dev_pre_review.evaluation.production import ProductionSampleEvaluator
from dev_pre_review.evaluation.report import EvaluationEvidence
from dev_pre_review.evaluation.runner import (
    EvaluationDatasetSplit,
    EvaluationManifest,
    EvaluationRunner,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Dev.Pre-Evaluation Golden Set Benchmark Runner")
    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="Path to golden set manifest.json",
    )
    parser.add_argument(
        "--split",
        choices=["tuning", "final"],
        default="tuning",
        help="Dataset split to evaluate",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path to write evaluation report",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output report format",
    )

    args = parser.parse_args()

    if not args.manifest.exists():
        sys.stderr.write(f"Error: Manifest file {args.manifest} not found.\n")
        return 2

    manifest = EvaluationManifest.from_file(args.manifest)
    try:
        manifest.verify_integrity()
    except Exception as e:
        sys.stderr.write(f"Integrity Error: {e}\n")
        return 3

    runner = EvaluationRunner(manifest=manifest)
    split_enum = EvaluationDatasetSplit(args.split)
    evaluator = ProductionSampleEvaluator()
    evidence = EvaluationEvidence(
        build_id=os.environ.get("DEV_PRE_REVIEW_BUILD_ID")
        or os.environ.get("GITHUB_SHA")
        or "local-unverified",
        environment=f"{platform.platform()}; Python {platform.python_version()}",
        evaluator_id=evaluator.evaluator_id,
        evaluator_capabilities=evaluator.capabilities,
        manifest_sha256=hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
    )
    report = runner.evaluate(split=split_enum, eval_fn=evaluator, evidence=evidence)

    formatted_output = report.to_markdown() if args.format == "markdown" else report.to_json()

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(formatted_output, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(formatted_output)

    if not report.passed:
        sys.stderr.write("FAILED: Quality gate thresholds were not met.\n")
        for v in report.violations:
            sys.stderr.write(f"  - {v}\n")
        return 1

    print("SUCCESS: All quality gates passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
