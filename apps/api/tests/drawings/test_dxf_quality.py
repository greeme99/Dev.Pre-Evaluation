"""Tests for DxfQualityGate: XREF and font missing detection (FN-004, TC-012)."""

from pathlib import Path

from dev_pre_review.drawings.dxf_parser import DxfParser, DxfQualityGate
from dev_pre_review.storage.files import StoredFile

FIXTURES_DIR = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "dxf"


def test_dxf_quality_gate_detects_missing_xref() -> None:
    parser = DxfParser()
    gate = DxfQualityGate()

    xref_path = FIXTURES_DIR / "missing-xref.dxf"
    stored = StoredFile(
        path=xref_path,
        sha256="dxf_xref_sha",
        size_bytes=xref_path.stat().st_size,
        original_name="missing-xref.dxf",
    )

    doc = parser.parse(stored)
    report = gate.inspect(doc)

    assert report.is_blocked is True
    assert len(report.missing_xrefs) >= 1
    assert any("non_existent_assembly" in x for x in report.missing_xrefs)
    assert any("XREF" in reason for reason in report.reasons)


def test_dxf_quality_gate_passes_healthy_dxf() -> None:
    parser = DxfParser()
    gate = DxfQualityGate()

    mech_path = FIXTURES_DIR / "mechanical.dxf"
    stored = StoredFile(
        path=mech_path,
        sha256="dxf_mech_sha",
        size_bytes=mech_path.stat().st_size,
        original_name="mechanical.dxf",
    )

    doc = parser.parse(stored)
    report = gate.inspect(doc)

    assert report.is_blocked is False
    assert len(report.missing_xrefs) == 0
    assert len(report.reasons) == 0
