"""Persistent server-owned source files for Excel import previews."""

import shutil
from pathlib import Path
from uuid import UUID

from dev_pre_review.domain.errors import DomainError


class ImportPreviewNotFound(DomainError):
    code = "import_preview_not_found"


class ImportPreviewStore:
    # ponytail: preview sources are retained; add expiry only when a retention policy exists.
    def __init__(self, root: Path) -> None:
        self.root = root

    def save(self, preview_id: UUID, source: Path) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        target = self._path(preview_id)
        with source.open("rb") as source_stream, target.open("xb") as target_stream:
            shutil.copyfileobj(source_stream, target_stream)
        return target

    def resolve(self, preview_id: UUID) -> Path:
        path = self._path(preview_id)
        if not path.is_file():
            raise ImportPreviewNotFound(f"Import preview {preview_id} was not found")
        return path

    def _path(self, preview_id: UUID) -> Path:
        return self.root / f"{preview_id}.xlsx"
