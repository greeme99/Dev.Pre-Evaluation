"""Domain contracts for Excel knowledge import."""

from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ExtractedImage(KnowledgeContract):
    image_id: str
    sheet_name: str
    anchor_cell: str
    context_text: str
    data_hash: str


class SheetPreview(KnowledgeContract):
    sheet_name: str
    columns: list[str]
    row_count: int
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)


class PreviewWarning(KnowledgeContract):
    code: str
    message: str
    location: str | None = None


class ImportProfile(KnowledgeContract):
    id: UUID = Field(default_factory=uuid4)
    name: str
    sheet_name: str
    column_mapping: dict[str, str] = Field(default_factory=dict)


class ImportPreview(KnowledgeContract):
    preview_id: UUID = Field(default_factory=uuid4)
    file_sha256: str
    file_name: str
    sheets: list[SheetPreview]
    images: list[ExtractedImage] = Field(default_factory=list)
    warnings: list[PreviewWarning] = Field(default_factory=list)
    suggested_profile: ImportProfile | None = None
