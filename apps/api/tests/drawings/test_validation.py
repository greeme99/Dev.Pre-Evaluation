"""Tests for drawing file validation and quality gates (FN-003, FR-004, TC-008~TC-010)."""

from pathlib import Path

import pymupdf
import pytest

from dev_pre_review.domain.enums import DrawingType
from dev_pre_review.drawings.contracts import ValidationErrorCode
from dev_pre_review.drawings.validation import (
    MAX_DXF_BYTES,
    MAX_PDF_PAGES,
    DrawingValidator,
)


@pytest.fixture
def validator() -> DrawingValidator:
    return DrawingValidator()


def create_minimal_pdf(path: Path, page_count: int = 1, encrypt: bool = False) -> None:
    doc = pymupdf.open()
    for i in range(page_count):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), f"Test page {i + 1}")
    if encrypt:
        perm = pymupdf.PDF_PERM_PRINT
        doc.save(
            path,
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            user_pw="password",
            owner_pw="owner",
            permissions=perm,
        )
    else:
        doc.save(path)
    doc.close()


def create_minimal_dxf(path: Path) -> None:
    content = "0\nSECTION\n2\nHEADER\n0\nENDSEC\n0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n"
    path.write_text(content, encoding="ascii")


def test_rejects_unsupported_extensions(validator: DrawingValidator, tmp_path: Path) -> None:
    dwg_file = tmp_path / "drawing.dwg"
    dwg_file.write_bytes(b"AC1027\x00\x00\x00")
    report = validator.validate(dwg_file, original_name="drawing.dwg")
    assert not report.is_valid
    assert any(err.code == ValidationErrorCode.UNSUPPORTED_EXTENSION for err in report.errors)

    xls_file = tmp_path / "old.xls"
    xls_file.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    report_xls = validator.validate(xls_file, original_name="old.xls")
    assert not report_xls.is_valid
    assert any(err.code == ValidationErrorCode.UNSUPPORTED_EXTENSION for err in report_xls.errors)


def test_rejects_signature_mismatch_extension_spoofing(
    validator: DrawingValidator, tmp_path: Path
) -> None:
    # Named .pdf but contains text or DWG magic bytes
    spoofed = tmp_path / "spoofed.pdf"
    spoofed.write_bytes(b"AC1024CAD_DRAWING_BYTES")
    report = validator.validate(spoofed, original_name="spoofed.pdf")
    assert not report.is_valid
    assert any(err.code == ValidationErrorCode.SIGNATURE_MISMATCH for err in report.errors)


def test_rejects_encrypted_pdf(validator: DrawingValidator, tmp_path: Path) -> None:
    encrypted_pdf = tmp_path / "locked.pdf"
    create_minimal_pdf(encrypted_pdf, page_count=1, encrypt=True)

    report = validator.validate(encrypted_pdf, original_name="locked.pdf")
    assert not report.is_valid
    assert any(err.code == ValidationErrorCode.ENCRYPTED_FILE for err in report.errors)


def test_rejects_pdf_exceeding_page_limit(validator: DrawingValidator, tmp_path: Path) -> None:
    large_pages_pdf = tmp_path / "large_pages.pdf"
    create_minimal_pdf(large_pages_pdf, page_count=MAX_PDF_PAGES + 1)

    report = validator.validate(large_pages_pdf, original_name="large_pages.pdf")
    assert not report.is_valid
    assert any(err.code == ValidationErrorCode.PAGE_LIMIT_EXCEEDED for err in report.errors)
    assert report.page_count == MAX_PDF_PAGES + 1


def test_validates_valid_pdf_and_dxf(validator: DrawingValidator, tmp_path: Path) -> None:
    # Valid PDF
    valid_pdf = tmp_path / "valid.pdf"
    create_minimal_pdf(valid_pdf, page_count=2)
    report_pdf = validator.validate(valid_pdf, original_name="valid.pdf")
    assert report_pdf.is_valid
    assert report_pdf.drawing_type == DrawingType.PDF
    assert report_pdf.page_count == 2
    assert report_pdf.stored_file_sha256 is not None
    assert report_pdf.estimated_profile in ("vector_pdf", "scanned_pdf")

    # Valid DXF
    valid_dxf = tmp_path / "valid.dxf"
    create_minimal_dxf(valid_dxf)
    report_dxf = validator.validate(valid_dxf, original_name="valid.dxf")
    assert report_dxf.is_valid
    assert report_dxf.drawing_type == DrawingType.DXF
    assert report_dxf.stored_file_sha256 is not None
    assert report_dxf.estimated_profile == "cad_dxf"


def test_rejects_file_exceeding_size_limit(validator: DrawingValidator, tmp_path: Path) -> None:
    # Sparse file exceeding 100MB for DXF
    oversized = tmp_path / "oversized.dxf"
    with open(oversized, "wb") as f:
        f.write(b"0\nSECTION\n2\nHEADER\n0\nENDSEC\n")
        f.truncate(MAX_DXF_BYTES + 1)

    report = validator.validate(oversized, original_name="oversized.dxf")
    assert not report.is_valid
    assert any(err.code == ValidationErrorCode.FILE_TOO_LARGE for err in report.errors)
