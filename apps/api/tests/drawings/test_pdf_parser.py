"""Tests for PdfParser: vector extraction, OCR scanning, and low-res detection (FN-004, TC-011)."""

from pathlib import Path

import pytest

from dev_pre_review.domain.enums import DrawingType
from dev_pre_review.drawings.contracts import DrawingDocument
from dev_pre_review.drawings.pdf_parser import PdfParser
from dev_pre_review.models.ocr import MockOcrProvider
from dev_pre_review.storage.files import StoredFile

FIXTURES_DIR = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "pdf"


@pytest.fixture
def mock_ocr() -> MockOcrProvider:
    return MockOcrProvider(canned_text="SCANNED DRAWING HIGH RES 300DPI | TOLERANCE: 0.02 mm")


def test_pdf_parser_extracts_vector_text_and_coords() -> None:
    parser = PdfParser()
    vector_path = FIXTURES_DIR / "vector.pdf"
    stored = StoredFile(
        path=vector_path,
        sha256="0" * 64,
        size_bytes=vector_path.stat().st_size,
        original_name="vector.pdf",
    )

    doc = parser.parse(stored)
    assert isinstance(doc, DrawingDocument)
    assert doc.drawing_type == DrawingType.PDF
    assert doc.page_count == 1
    assert len(doc.regions) >= 3

    texts = [r.raw_text for r in doc.regions]
    assert any("DWG-2026-001" in t for t in texts)
    assert any("+-0.05 mm" in t for t in texts)
    assert any("SUS304" in t for t in texts)

    # Check pixel bbox and confidence
    for r in doc.regions:
        assert r.pixel_bbox is not None
        assert r.confidence == 1.0


def test_pdf_parser_uses_ocr_for_scanned_300dpi(mock_ocr: MockOcrProvider) -> None:
    parser = PdfParser(ocr_provider=mock_ocr)
    scan_path = FIXTURES_DIR / "scan-300dpi.pdf"
    stored = StoredFile(
        path=scan_path,
        sha256="1" * 64,
        size_bytes=scan_path.stat().st_size,
        original_name="scan-300dpi.pdf",
    )

    doc = parser.parse(stored)
    assert isinstance(doc, DrawingDocument)
    assert doc.metadata.get("profile") == "scanned_pdf"
    assert len(doc.regions) > 0
    assert any("SCANNED DRAWING" in r.raw_text for r in doc.regions)


def test_pdf_parser_flags_low_resolution_as_insufficient_information() -> None:
    parser = PdfParser()
    lowres_path = FIXTURES_DIR / "scan-lowres.pdf"
    stored = StoredFile(
        path=lowres_path,
        sha256="2" * 64,
        size_bytes=lowres_path.stat().st_size,
        original_name="scan-lowres.pdf",
    )

    doc = parser.parse(stored)
    assert isinstance(doc, DrawingDocument)
    assert doc.metadata.get("low_resolution") is True
    # Regions from low-res scan must have degraded confidence
    for r in doc.regions:
        assert r.confidence < 0.6


def test_parser_registry_returns_pdf_parser() -> None:
    from dev_pre_review.drawings.ports import get_default_registry

    reg = get_default_registry()
    parser = reg.get(DrawingType.PDF)
    assert isinstance(parser, PdfParser)
