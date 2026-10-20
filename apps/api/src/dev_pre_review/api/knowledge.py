"""Knowledge import endpoints (API-001, API-002)."""

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, status

from dev_pre_review.knowledge.contracts import ImportPreview
from dev_pre_review.knowledge.excel_reader import (
    EncryptedExcelError,
    ExcelReader,
    InvalidExcelError,
)
from dev_pre_review.storage.files import FileStore, FileTooLargeError

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])
excel_reader = ExcelReader()


@router.post("/imports/preview", response_model=ImportPreview)
def preview_excel_import(file: UploadFile) -> ImportPreview:
    if not file.filename or not file.filename.endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .xlsx files are supported",
        )

    # Use a secure temporary directory for streaming inspection
    with tempfile.TemporaryDirectory() as td:
        store = FileStore(Path(td))
        try:
            stored = store.save_stream(file.file, original_name=file.filename)
            return excel_reader.preview(stored.path)
        except EncryptedExcelError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        except InvalidExcelError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        except FileTooLargeError as exc:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=str(exc),
            ) from exc
