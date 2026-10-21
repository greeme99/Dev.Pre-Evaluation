"""Tests for Excel reader: cell extraction, image anchors, and invalid file rejection."""

from pathlib import Path
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

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


def test_image_ids_are_stable_when_server_reparses_preview(reader: ExcelReader) -> None:
    preview_id = uuid4()

    first = reader.preview(fixture_path("merged-anchor.xlsx"), preview_id=preview_id)
    reparsed = reader.preview(fixture_path("merged-anchor.xlsx"), preview_id=preview_id)

    assert [image.image_id for image in first.images] == [
        image.image_id for image in reparsed.images
    ]


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


def test_rejects_high_expansion_excel_archive(
    reader: ExcelReader, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unsafe = tmp_path / "high-expansion.xlsx"
    with ZipFile(unsafe, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("xl/worksheets/sheet1.xml", "A" * 20_000)
    monkeypatch.setattr("dev_pre_review.knowledge.excel_reader.MAX_COMPRESSION_RATIO", 2)
    monkeypatch.setattr("dev_pre_review.knowledge.excel_reader.RATIO_CHECK_MIN_BYTES", 1)

    with pytest.raises(InvalidExcelError, match="compression ratio"):
        reader.preview(unsafe)


def test_rejects_aggregate_expansion_from_many_small_archive_members(
    reader: ExcelReader, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unsafe = tmp_path / "aggregate-expansion.xlsx"
    with ZipFile(unsafe, "w", compression=ZIP_DEFLATED) as archive:
        for index in range(20):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", "A" * 10_000)
    monkeypatch.setattr("dev_pre_review.knowledge.excel_reader.MAX_COMPRESSION_RATIO", 2)
    monkeypatch.setattr("dev_pre_review.knowledge.excel_reader.RATIO_CHECK_MIN_BYTES", 1_000_000)

    with pytest.raises(InvalidExcelError, match="total compression ratio"):
        reader.preview(unsafe)
