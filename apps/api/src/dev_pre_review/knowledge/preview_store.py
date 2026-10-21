"""Persistent server-owned source files for Excel import previews."""

import shutil
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from uuid import UUID

from dev_pre_review.domain.errors import DomainError


class ImportPreviewNotFound(DomainError):
    code = "import_preview_not_found"


class ImportPreviewCapacityExceeded(DomainError):
    code = "import_preview_capacity_exceeded"


_PREVIEW_STORE_LOCK = RLock()


class ImportPreviewStore:
    def __init__(
        self,
        root: Path,
        *,
        ttl_seconds: int = 24 * 60 * 60,
        max_total_bytes: int = 500 * 1024 * 1024,
    ) -> None:
        self.root = root
        self.ttl_seconds = ttl_seconds
        self.max_total_bytes = max_total_bytes

    def save(self, preview_id: UUID, source: Path) -> Path:
        with _PREVIEW_STORE_LOCK:
            self.root.mkdir(parents=True, exist_ok=True)
            source_size = source.stat().st_size
            if source_size > self.max_total_bytes:
                raise ImportPreviewCapacityExceeded(
                    f"Preview size {source_size} exceeds capacity {self.max_total_bytes}"
                )
            self._cleanup(required_bytes=source_size)
            target = self._path(preview_id)
            temporary = self.root / f".{preview_id}.tmp"
            if target.exists():
                raise FileExistsError(target)
            try:
                with source.open("rb") as source_stream, temporary.open("xb") as target_stream:
                    shutil.copyfileobj(source_stream, target_stream)
                temporary.replace(target)
            except Exception:
                temporary.unlink(missing_ok=True)
                raise
            return target

    def resolve(self, preview_id: UUID) -> Path:
        with _PREVIEW_STORE_LOCK:
            self._cleanup()
            return self._resolve(preview_id)

    @contextmanager
    def lease(self, preview_id: UUID) -> Iterator[Path]:
        """Keep a preview available while its workbook content is being read."""
        with _PREVIEW_STORE_LOCK:
            self._cleanup()
            yield self._resolve(preview_id)

    def cleanup(self, *, now: float | None = None, required_bytes: int = 0) -> None:
        """Remove expired and oldest previews until the bounded cache has room."""
        with _PREVIEW_STORE_LOCK:
            self._cleanup(now=now, required_bytes=required_bytes)

    def _cleanup(self, *, now: float | None = None, required_bytes: int = 0) -> None:
        if not self.root.is_dir():
            return
        current_time = time.time() if now is None else now
        previews = sorted(
            self.root.glob("*.xlsx"),
            key=lambda path: path.stat().st_mtime,
        )
        retained: list[Path] = []
        for path in previews:
            if current_time - path.stat().st_mtime > self.ttl_seconds:
                path.unlink(missing_ok=True)
            else:
                retained.append(path)

        total_bytes = sum(path.stat().st_size for path in retained)
        for path in retained:
            if total_bytes + required_bytes <= self.max_total_bytes:
                break
            size = path.stat().st_size
            path.unlink(missing_ok=True)
            total_bytes -= size

    def _resolve(self, preview_id: UUID) -> Path:
        path = self._path(preview_id)
        if not path.is_file():
            raise ImportPreviewNotFound(f"Import preview {preview_id} was not found")
        return path

    def _path(self, preview_id: UUID) -> Path:
        return self.root / f"{preview_id}.xlsx"
