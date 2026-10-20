"""Project creation and persistent drawing upload endpoints."""

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field

from dev_pre_review.domain.enums import DrawingType
from dev_pre_review.domain.models import DrawingArtifact, ReviewProject, utc_now
from dev_pre_review.drawings.validation import DrawingValidator
from dev_pre_review.main import get_database
from dev_pre_review.storage.database import Database
from dev_pre_review.storage.files import FileStore, FileTooLargeError
from dev_pre_review.storage.paths import get_artifacts_dir
from dev_pre_review.storage.repositories import DrawingRepository, ProjectRepository

router = APIRouter(prefix="/api/projects", tags=["projects"])
DbDep = Annotated[Database, Depends(get_database)]


class CreateProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)


class ProjectResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID
    name: str
    created_at: datetime


class DrawingUploadResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID
    project_id: UUID
    sha256: str
    drawing_type: DrawingType
    source_name: str


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(req: CreateProjectRequest, db: DbDep) -> ProjectResponse:
    project = ProjectRepository(db.sessions).add(ReviewProject(name=req.name, created_at=utc_now()))
    return ProjectResponse(id=project.id, name=project.name, created_at=project.created_at)


@router.post(
    "/{project_id}/drawings",
    response_model=DrawingUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_drawing(
    project_id: UUID,
    db: DbDep,
    file: Annotated[UploadFile, File()],
) -> DrawingUploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    ProjectRepository(db.sessions).get(project_id)

    try:
        with tempfile.TemporaryDirectory() as temporary_dir:
            temporary_store = FileStore(Path(temporary_dir), max_bytes=200 * 1024 * 1024)
            temporary = temporary_store.save_stream(file.file, original_name=file.filename)
            report = DrawingValidator().validate(temporary.path, file.filename)
            if not report.is_valid or report.drawing_type is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": report.errors[0].code.value
                        if report.errors
                        else "invalid_drawing"
                    },
                )

            persistent_store = FileStore(get_artifacts_dir(), max_bytes=200 * 1024 * 1024)
            with temporary.path.open("rb") as source:
                stored = persistent_store.save_stream(source, file.filename)
    except FileTooLargeError as exc:
        raise HTTPException(status_code=413, detail={"code": exc.code}) from exc

    drawing = DrawingArtifact(
        project_id=project_id,
        sha256=stored.sha256,
        drawing_type=report.drawing_type,
        source_name=file.filename,
        parser_version="1.0.0",
        created_at=utc_now(),
    )
    DrawingRepository(db.sessions).add(drawing)
    return DrawingUploadResponse(
        id=drawing.id,
        project_id=drawing.project_id,
        sha256=drawing.sha256,
        drawing_type=drawing.drawing_type,
        source_name=drawing.source_name,
    )
