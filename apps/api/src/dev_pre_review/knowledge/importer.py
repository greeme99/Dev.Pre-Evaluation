"""KnowledgeImporter: commits verified Excel mappings into persistent KnowledgeCases."""

from typing import cast
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import insert, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session, sessionmaker

from dev_pre_review.domain.models import KnowledgeCase, utc_now
from dev_pre_review.knowledge.contracts import ImportPreview
from dev_pre_review.storage.schema import import_records, knowledge_cases


class CommitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    preview_id: UUID
    file_sha256: str
    file_name: str
    sheet_name: str
    column_mapping: dict[str, str] = Field(default_factory=dict)
    idempotency_key: str | None = None


class ImportResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    project_id: UUID
    file_sha256: str
    cases_imported: int
    duplicate_count: int


class KnowledgeImporter:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def commit(self, req: CommitRequest, preview: ImportPreview) -> ImportResult:
        with self.session_factory() as session, session.begin():
            # Check duplicate by idempotency_key or (project_id, file_sha256)
            query = select(import_records).where(import_records.c.project_id == req.project_id)
            if req.idempotency_key:
                query = query.where(
                    (import_records.c.idempotency_key == req.idempotency_key)
                    | (import_records.c.file_sha256 == req.file_sha256)
                )
            else:
                query = query.where(import_records.c.file_sha256 == req.file_sha256)

            existing = session.execute(query).mappings().first()
            if existing is not None:
                return ImportResult(
                    project_id=req.project_id,
                    file_sha256=req.file_sha256,
                    cases_imported=0,
                    duplicate_count=int(existing["case_count"]),
                )

            # Locate the requested sheet in preview
            target_sheet = next((s for s in preview.sheets if s.sheet_name == req.sheet_name), None)
            if target_sheet is None or not target_sheet.sample_rows:
                # If no rows or sheet not found
                return ImportResult(
                    project_id=req.project_id,
                    file_sha256=req.file_sha256,
                    cases_imported=0,
                    duplicate_count=0,
                )

            cases_to_insert: list[KnowledgeCase] = []
            now = utc_now()

            # Find matching images for this sheet
            sheet_images = [
                img.image_id for img in preview.images if img.sheet_name == req.sheet_name
            ]

            for row_idx, row_data in enumerate(target_sheet.sample_rows):
                # Build text from mapped columns or all columns
                parts: list[str] = []
                for col_name, val in row_data.items():
                    if val is not None:
                        mapped_role = req.column_mapping.get(col_name, col_name)
                        parts.append(f"{mapped_role}: {val}")

                combined_text = " | ".join(parts)
                cell_coord = f"A{row_idx + 2}"

                case = KnowledgeCase(
                    id=uuid4(),
                    project_id=req.project_id,
                    text=combined_text,
                    table=(),
                    image_refs=tuple(sheet_images),
                    source_file_sha256=req.file_sha256,
                    source_sheet=req.sheet_name,
                    source_cell=cell_coord,
                    created_at=now,
                )
                cases_to_insert.append(case)

                session.execute(
                    insert(knowledge_cases).values(
                        id=case.id,
                        project_id=case.project_id,
                        text=case.text,
                        table_data=list(case.table),
                        image_refs=list(case.image_refs),
                        source_file_sha256=case.source_file_sha256,
                        source_sheet=case.source_sheet,
                        source_cell=case.source_cell,
                        created_at=case.created_at,
                    )
                )

            # Record import commit
            session.execute(
                insert(import_records).values(
                    id=uuid4(),
                    project_id=req.project_id,
                    file_sha256=req.file_sha256,
                    idempotency_key=req.idempotency_key,
                    sheet_name=req.sheet_name,
                    case_count=len(cases_to_insert),
                    created_at=now,
                )
            )

            return ImportResult(
                project_id=req.project_id,
                file_sha256=req.file_sha256,
                cases_imported=len(cases_to_insert),
                duplicate_count=0,
            )

    def list_cases_for_project(self, project_id: UUID) -> list[KnowledgeCase]:
        with self.session_factory() as session:
            rows = (
                session.execute(
                    select(knowledge_cases)
                    .where(knowledge_cases.c.project_id == project_id)
                    .order_by(knowledge_cases.c.created_at.asc())
                )
                .mappings()
                .all()
            )
            return [self._row_to_model(r) for r in rows]

    @staticmethod
    def _row_to_model(row: RowMapping) -> KnowledgeCase:
        return KnowledgeCase(
            id=row["id"],
            project_id=row["project_id"],
            text=str(row["text"]),
            table=tuple(tuple(r) for r in cast(list[list[str]], row["table_data"])),
            image_refs=tuple(cast(list[str], row["image_refs"])),
            source_file_sha256=str(row["source_file_sha256"]),
            source_sheet=str(row["source_sheet"]),
            source_cell=str(row["source_cell"]),
            created_at=row["created_at"],
        )
