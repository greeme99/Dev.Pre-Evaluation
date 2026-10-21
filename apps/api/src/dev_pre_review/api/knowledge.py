"""Knowledge import endpoints (API-001, API-002)."""

import tempfile
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field

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
from dev_pre_review.knowledge.preview_store import ImportPreviewNotFound, ImportPreviewStore
from dev_pre_review.main import get_database
from dev_pre_review.storage.database import Database
from dev_pre_review.storage.files import FileStore, FileTooLargeError
from dev_pre_review.storage.paths import get_artifacts_dir
from dev_pre_review.storage.repositories import ProjectRepository

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])
excel_reader = ExcelReader()


def get_importer(db: Annotated[Database, Depends(get_database)]) -> KnowledgeImporter:
    return KnowledgeImporter(db.sessions)


class CommitImportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    sheet_name: str
    column_mapping: dict[str, str] = Field(default_factory=dict)
    idempotency_key: str | None = None


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
            preview_id = uuid4()
            preview = excel_reader.preview(
                stored.path,
                preview_id=preview_id,
                file_name=file.filename,
            )
            ImportPreviewStore(get_artifacts_dir() / "import-previews").save(
                preview_id, stored.path
            )
            return preview
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
    db: Annotated[Database, Depends(get_database)],
    importer: Annotated[KnowledgeImporter, Depends(get_importer)],
) -> ImportResult:
    ProjectRepository(db.sessions).get(payload.project_id)
    preview_store = ImportPreviewStore(get_artifacts_dir() / "import-previews")
    try:
        source_path = preview_store.resolve(import_id)
        preview = excel_reader.preview(source_path, preview_id=import_id)
        columns, rows = excel_reader.read_rows(source_path, payload.sheet_name)
    except ImportPreviewNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidExcelError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    unknown_columns = set(payload.column_mapping) - set(columns)
    if unknown_columns:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown mapped columns: {', '.join(sorted(unknown_columns))}",
        )

    req = CommitRequest(
        project_id=payload.project_id,
        preview_id=import_id,
        file_sha256=preview.file_sha256,
        sheet_name=payload.sheet_name,
        column_mapping=payload.column_mapping,
        idempotency_key=payload.idempotency_key,
    )
    image_refs = tuple(
        image.image_id for image in preview.images if image.sheet_name == payload.sheet_name
    )
    return importer.commit(req, rows, image_refs)


@router.get("/cases", response_model=list[KnowledgeCase])
def list_knowledge_cases(
    project_id: UUID,
    importer: Annotated[KnowledgeImporter, Depends(get_importer)],
) -> list[KnowledgeCase]:
    return importer.list_cases_for_project(project_id)
