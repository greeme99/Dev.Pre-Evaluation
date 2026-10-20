"""Deterministic generation and drift detection for the workflow TypeScript contract."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GENERATOR = ROOT / "scripts" / "generate_workflow_contracts.py"


def test_generator_check_detects_mutation_without_rewriting(tmp_path: Path) -> None:
    output = tmp_path / "workflow.ts"
    generated = subprocess.run(  # noqa: S603
        [sys.executable, str(GENERATOR), "--output", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert generated.returncode == 0, generated.stderr
    expected = output.read_text(encoding="utf-8")
    assert "pixel_bbox?: [number, number, number, number] | null;" in expected

    output.write_text(expected + "// deliberate drift\n", encoding="utf-8")
    stale = output.read_text(encoding="utf-8")
    checked = subprocess.run(  # noqa: S603
        [sys.executable, str(GENERATOR), "--check", "--output", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert checked.returncode != 0
    assert output.read_text(encoding="utf-8") == stale
