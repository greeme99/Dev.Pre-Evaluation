"""Knowledge import endpoints (API-001, API-002)."""

import tempfile
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from dev_pre_review.domain.models import KnowledgeCase
from dev_pre_review.knowledge.contracts import ImportPreview
from dev_pre_review.knowledge.excel_reader import (
    EncryptedExcelError,
    ExcelReader,
    InvalidExcelError,
)
from dev_pre_review.knowledge.importer import (
    CommitRequest,
    ImportResult,
    KnowledgeImporter,
)
from dev_pre_review.main import get_database
from dev_pre_review.storage.database import Database
from dev_pre_review.storage.files import FileStore, FileTooLargeError

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])
excel_reader = ExcelReader()


def get_importer(db: Annotated[Database, Depends(get_database)]) -> KnowledgeImporter:
    return KnowledgeImporter(db.sessions)


class CommitImportPayload(BaseModel):
    project_id: UUID
    file_sha256: str
    file_name: str
    sheet_name: str
    column_mapping: dict[str, str] = Field(default_factory=dict)
    idempotency_key: str | None = None
    preview: ImportPreview


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


@router.post("/imports/{import_id}/commit", response_model=ImportResult)
def commit_excel_import(
    import_id: UUID,
    payload: CommitImportPayload,
    importer: Annotated[KnowledgeImporter, Depends(get_importer)],
) -> ImportResult:
    req = CommitRequest(
        project_id=payload.project_id,
        preview_id=import_id,
        file_sha256=payload.file_sha256,
        file_name=payload.file_name,
        sheet_name=payload.sheet_name,
        column_mapping=payload.column_mapping,
        idempotency_key=payload.idempotency_key,
    )
    return importer.commit(req, payload.preview)


@router.get("/cases", response_model=list[KnowledgeCase])
def list_knowledge_cases(
    project_id: UUID,
    importer: Annotated[KnowledgeImporter, Depends(get_importer)],
) -> list[KnowledgeCase]:
    return importer.list_cases_for_project(project_id)
