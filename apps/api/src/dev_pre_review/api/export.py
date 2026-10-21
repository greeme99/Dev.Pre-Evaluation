"""Export, backup, restore and diagnostics endpoints (API-012~API-014, API-016)."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field

from dev_pre_review.export.backup import BackupService
from dev_pre_review.export.diagnostics import DiagnosticBundle
from dev_pre_review.export.findings import FindingExporter
from dev_pre_review.main import get_database
from dev_pre_review.storage.database import Database

router = APIRouter(prefix="/api", tags=["export"])

DbDep = Annotated[Database, Depends(get_database)]
MAX_BACKUP_UPLOAD_BYTES = 100 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 1024 * 1024


async def _read_bounded_backup(package: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while chunk := await package.read(UPLOAD_CHUNK_BYTES):
        total += len(chunk)
        if total > MAX_BACKUP_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail={"code": "backup_too_large", "max_bytes": MAX_BACKUP_UPLOAD_BYTES},
            )
        chunks.append(chunk)
    return b"".join(chunks)


class CreateBackupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passphrase: str = Field(min_length=8)
    include_sources: bool = False


class DiagnosticRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_codes: list[str] = Field(default_factory=list)
    step_latencies_ms: dict[str, float] = Field(default_factory=dict)


@router.get("/analyses/{job_id}/export.xlsx")
def export_findings_xlsx(
    job_id: UUID,
    db: DbDep,
) -> Response:
    exporter = FindingExporter(db.sessions)
    content = exporter.to_xlsx(job_id)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="findings_{job_id}.xlsx"'},
    )


@router.get("/analyses/{job_id}/export.csv")
def export_findings_csv(
    job_id: UUID,
    db: DbDep,
) -> Response:
    exporter = FindingExporter(db.sessions)
    content = exporter.to_csv(job_id)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="findings_{job_id}.csv"'},
    )


@router.post("/backups")
def create_backup(
    req: CreateBackupRequest,
    db: DbDep,
) -> Response:
    service = BackupService()
    pkg_bytes = service.create(
        db.sessions,
        passphrase=req.passphrase,
        include_sources=req.include_sources,
    )
    return Response(
        content=pkg_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": 'attachment; filename="backup.dprb"'},
    )


@router.post("/restores/preview")
async def preview_restore(
    package: Annotated[UploadFile, File()],
    passphrase: Annotated[str, Form()],
) -> dict[str, Any]:
    content = await _read_bounded_backup(package)
    service = BackupService()
    return service.preview(content, passphrase=passphrase)


@router.post("/restores/commit")
async def commit_restore(
    db: DbDep,
    package: Annotated[UploadFile, File()],
    passphrase: Annotated[str, Form()],
) -> dict[str, str]:
    content = await _read_bounded_backup(package)
    service = BackupService()
    service.restore(content, passphrase=passphrase, target_session_factory=db.sessions)
    return {"status": "restored"}


@router.post("/diagnostics")
def create_diagnostics(
    req: DiagnosticRequest,
) -> dict[str, Any]:
    return DiagnosticBundle.create(
        error_codes=req.error_codes,
        step_latencies_ms=req.step_latencies_ms,
    )
