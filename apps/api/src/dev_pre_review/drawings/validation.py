"""DrawingValidator: validates drawing input files against format, size, and limits."""

import hashlib
from pathlib import Path

import ezdxf
import pymupdf

from dev_pre_review.domain.enums import DrawingType
from dev_pre_review.drawings.contracts import (
    ValidationErrorCode,
    ValidationErrorDetail,
    ValidationReport,
)

MAX_XLSX_BYTES = 100 * 1024 * 1024  # 100MB
MAX_PDF_BYTES = 200 * 1024 * 1024  # 200MB
MAX_DXF_BYTES = 100 * 1024 * 1024  # 100MB
MAX_PDF_PAGES = 100

MAGIC_PDF = b"%PDF-"
MAGIC_ZIP_XLSX = b"PK\x03\x04"
MAGIC_DWG_PREFIX = b"AC10"
MAGIC_OLE_XLS = b"\xd0\xcf\x11\xe0"


class DrawingValidator:
    def __init__(self) -> None:
        pass

    def validate(self, path: Path, original_name: str) -> ValidationReport:
        errors: list[ValidationErrorDetail] = []
        name_lower = original_name.lower()

        # 1. Extension check
        if name_lower.endswith(".pdf"):
            drawing_type: DrawingType | None = DrawingType.PDF
            max_size = MAX_PDF_BYTES
        elif name_lower.endswith(".dxf"):
            drawing_type = DrawingType.DXF
            max_size = MAX_DXF_BYTES
        elif name_lower.endswith(".xlsx"):
            drawing_type = None  # Valid knowledge import file, but not CAD drawing
            max_size = MAX_XLSX_BYTES
        else:
            ext = Path(original_name).suffix
            return ValidationReport(
                is_valid=False,
                file_name=original_name,
                drawing_type=None,
                file_size=path.stat().st_size if path.exists() else 0,
                errors=[
                    ValidationErrorDetail(
                        code=ValidationErrorCode.UNSUPPORTED_EXTENSION,
                        message=f"Unsupported file extension: {ext}. Only .pdf, .dxf are accepted.",
                    )
                ],
            )

        file_size = path.stat().st_size

        # 2. Size limit check
        if file_size > max_size:
            errors.append(
                ValidationErrorDetail(
                    code=ValidationErrorCode.FILE_TOO_LARGE,
                    message=f"File size {file_size} exceeds maximum limit of {max_size} bytes.",
                )
            )

        # 3. Magic bytes signature check
        with path.open("rb") as f:
            header = f.read(1024)

        if drawing_type == DrawingType.PDF:
            if not header.startswith(MAGIC_PDF) and MAGIC_PDF not in header[:1024]:
                errors.append(
                    ValidationErrorDetail(
                        code=ValidationErrorCode.SIGNATURE_MISMATCH,
                        message="File claims to be a PDF, but does not start with %PDF- header.",
                    )
                )
        elif drawing_type == DrawingType.DXF:
            if header.startswith(MAGIC_DWG_PREFIX) or header.startswith(MAGIC_OLE_XLS):
                errors.append(
                    ValidationErrorDetail(
                        code=ValidationErrorCode.SIGNATURE_MISMATCH,
                        message="File claims to be DXF, but binary header matches DWG/XLS.",
                    )
                )

        if errors:
            return ValidationReport(
                is_valid=False,
                file_name=original_name,
                drawing_type=drawing_type,
                file_size=file_size,
                errors=errors,
            )

        # 4. Deep format validation (encryption, pages, corruption)
        page_count: int | None = None
        estimated_profile: str | None = None

        if drawing_type == DrawingType.PDF:
            try:
                doc = pymupdf.open(path)  # type: ignore[no-untyped-call]
                if doc.is_encrypted:
                    errors.append(
                        ValidationErrorDetail(
                            code=ValidationErrorCode.ENCRYPTED_FILE,
                            message="Encrypted or password-protected PDF files are not supported.",
                        )
                    )
                else:
                    page_count = doc.page_count
                    if page_count > MAX_PDF_PAGES:
                        errors.append(
                            ValidationErrorDetail(
                                code=ValidationErrorCode.PAGE_LIMIT_EXCEEDED,
                                message=f"PDF page count {page_count} exceeds max {MAX_PDF_PAGES}.",
                            )
                        )
                    else:
                        # Estimate profile: check if first page has text
                        total_text_len = 0
                        for page_idx in range(page_count):
                            p = doc.load_page(page_idx)  # type: ignore[no-untyped-call]
                            total_text_len += len(p.get_text().strip())
                            if total_text_len > 20:
                                break
                        estimated_profile = "vector_pdf" if total_text_len > 20 else "scanned_pdf"
                doc.close()  # type: ignore[no-untyped-call]
            except Exception as exc:
                errors.append(
                    ValidationErrorDetail(
                        code=ValidationErrorCode.CORRUPTED_FILE,
                        message=f"Failed to parse PDF document structure: {exc}",
                    )
                )

        elif drawing_type == DrawingType.DXF:
            try:
                ezdxf.readfile(path)  # type: ignore[attr-defined]
                estimated_profile = "cad_dxf"

            except Exception as exc:
                errors.append(
                    ValidationErrorDetail(
                        code=ValidationErrorCode.CORRUPTED_FILE,
                        message=f"Failed to parse DXF structure: {exc}",
                    )
                )

        if errors:
            return ValidationReport(
                is_valid=False,
                file_name=original_name,
                drawing_type=drawing_type,
                file_size=file_size,
                page_count=page_count,
                errors=errors,
            )

        # 5. Compute SHA-256 for valid file
        sha = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha.update(chunk)

        return ValidationReport(
            is_valid=True,
            file_name=original_name,
            drawing_type=drawing_type,
            file_size=file_size,
            page_count=page_count,
            errors=[],
            estimated_profile=estimated_profile,
            stored_file_sha256=sha.hexdigest(),
        )
