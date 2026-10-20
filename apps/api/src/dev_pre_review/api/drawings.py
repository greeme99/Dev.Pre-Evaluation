"""Drawing validation endpoint (API-005, FN-003, FR-004)."""

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, status

from dev_pre_review.drawings.contracts import ValidationReport
from dev_pre_review.drawings.validation import DrawingValidator
from dev_pre_review.storage.files import FileStore, FileTooLargeError

router = APIRouter(prefix="/api/drawings", tags=["drawings"])
validator = DrawingValidator()


@router.post("/validate", response_model=ValidationReport)
def validate_drawing(file: UploadFile) -> ValidationReport:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    # Use a secure temporary directory for streaming inspection
    with tempfile.TemporaryDirectory() as td:
        store = FileStore(Path(td), max_bytes=200 * 1024 * 1024)
        try:
            stored = store.save_stream(file.file, original_name=file.filename)
            return validator.validate(stored.path, original_name=file.filename)
        except FileTooLargeError as exc:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=str(exc),
            ) from exc
