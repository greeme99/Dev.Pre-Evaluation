"""Tests for DxfParser: modelspace/paperspace extraction and CAD coordinates (FN-004, TC-012)."""

from pathlib import Path

import pytest

from dev_pre_review.domain.enums import DrawingType
from dev_pre_review.drawings.contracts import DrawingDocument
from dev_pre_review.drawings.dxf_parser import DxfParser
from dev_pre_review.storage.files import StoredFile

FIXTURES_DIR = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "dxf"


def test_dxf_parser_extracts_entities_and_text_from_mechanical_dxf() -> None:
    parser = DxfParser()
    mech_path = FIXTURES_DIR / "mechanical.dxf"
    stored = StoredFile(
        path=mech_path,
        sha256="dxf_mech_sha",
        size_bytes=mech_path.stat().st_size,
        original_name="mechanical.dxf",
    )

    doc = parser.parse(stored)
    assert isinstance(doc, DrawingDocument)
    assert doc.drawing_type == DrawingType.DXF
    assert doc.unit == "mm"

    # Verify modelspace and paperspace regions are captured
    spaces = {r.page_or_sheet for r in doc.regions}
    assert "modelspace" in spaces
    assert any("Layout" in str(s) or s == "paperspace" for s in spaces)

    # Verify texts
    all_texts = [r.raw_text for r in doc.regions]
    assert any("+-0.02 mm" in t for t in all_texts)
    assert any("SUS304" in t for t in all_texts)
    assert any("Ra 0.8" in t for t in all_texts)
    assert any("기계가공도면" in t for t in all_texts)

    # Verify CAD bbox coordinates preservation
    text_regions = [r for r in doc.regions if "+-0.02 mm" in r.raw_text]
    assert len(text_regions) == 1
    tr = text_regions[0]
    assert tr.cad_bbox is not None
    assert tr.layer == "DIM"
    # insert was (10, 20)
    assert tr.cad_bbox[0] == pytest.approx(10.0)
    assert tr.cad_bbox[1] == pytest.approx(20.0)

    # Verify entity counts metadata
    counts = doc.metadata.get("entity_counts", {})
    assert counts.get("LINE", 0) >= 1
    assert counts.get("CIRCLE", 0) >= 1
    assert counts.get("ARC", 0) >= 1
    assert counts.get("LWPOLYLINE", 0) >= 1


def test_dxf_parser_extracts_electrical_dxf() -> None:
    parser = DxfParser()
    elec_path = FIXTURES_DIR / "electrical.dxf"
    stored = StoredFile(
        path=elec_path,
        sha256="dxf_elec_sha",
        size_bytes=elec_path.stat().st_size,
        original_name="electrical.dxf",
    )

    doc = parser.parse(stored)
    assert isinstance(doc, DrawingDocument)
    texts = [r.raw_text for r in doc.regions]
    assert any("220V" in t for t in texts)
    assert any("TB-01" in t for t in texts)


def test_parser_registry_returns_dxf_parser() -> None:
    from dev_pre_review.drawings.ports import get_default_registry

    reg = get_default_registry()
    parser = reg.get(DrawingType.DXF)
    assert isinstance(parser, DxfParser)
