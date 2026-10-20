"""Drawing contracts, validation report, and document models."""

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dev_pre_review.domain.enums import DrawingType


class ValidationErrorCode(StrEnum):
    UNSUPPORTED_EXTENSION = "unsupported_extension"
    SIGNATURE_MISMATCH = "signature_mismatch"
    FILE_TOO_LARGE = "file_too_large"
    PAGE_LIMIT_EXCEEDED = "page_limit_exceeded"
    ENCRYPTED_FILE = "encrypted_file"
    CORRUPTED_FILE = "corrupted_file"


class ValidationErrorDetail(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: ValidationErrorCode
    message: str


class ValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    is_valid: bool
    file_name: str
    drawing_type: DrawingType | None = None
    file_size: int
    page_count: int | None = None
    errors: list[ValidationErrorDetail] = Field(default_factory=list)
    estimated_profile: str | None = None
    stored_file_sha256: str | None = None


class TextRegion(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    page_or_sheet: int | str
    raw_text: str
    pixel_bbox: tuple[float, float, float, float] | None = None
    cad_bbox: tuple[float, float, float, float] | None = None
    confidence: float = 1.0
    layer: str | None = None
    unit: str | None = None


class DrawingDocument(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    drawing_id: UUID
    drawing_type: DrawingType
    file_name: str
    file_sha256: str
    page_count: int
    unit: str = "mm"
    regions: list[TextRegion] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
