"""Tests for Excel reader: cell extraction, image anchors, and invalid file rejection."""

from pathlib import Path

import pytest

from dev_pre_review.knowledge.contracts import ImportPreview
from dev_pre_review.knowledge.excel_reader import (
    EncryptedExcelError,
    ExcelReader,
    InvalidExcelError,
)

FIXTURES_DIR = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "excel"


@pytest.fixture
def reader() -> ExcelReader:
    return ExcelReader()


def fixture_path(filename: str) -> Path:
    return FIXTURES_DIR / filename


def test_extracts_images_from_merged_and_offset_anchors(reader: ExcelReader) -> None:
    preview = reader.preview(fixture_path("merged-anchor.xlsx"))

    assert isinstance(preview, ImportPreview)
    assert len(preview.images) >= 1
    first_image = preview.images[0]
    assert first_image.anchor_cell == "D7"
    assert "용접" in first_image.context_text


def test_reads_standard_excel_sheet_and_columns(reader: ExcelReader) -> None:
    preview = reader.preview(fixture_path("standard.xlsx"))

    assert isinstance(preview, ImportPreview)
    assert len(preview.sheets) == 1
    sheet = preview.sheets[0]
    assert sheet.sheet_name == "오류사례"
    assert "오류설명" in sheet.columns
    assert "부품명" in sheet.columns
    assert sheet.row_count >= 2


def test_rejects_encrypted_or_invalid_excel(reader: ExcelReader) -> None:
    with pytest.raises((EncryptedExcelError, InvalidExcelError)):
        reader.preview(fixture_path("invalid-encrypted.xlsx"))
