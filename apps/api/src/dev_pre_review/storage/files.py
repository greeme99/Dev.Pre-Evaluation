"""Atomic file storage using SHA-256 hash paths."""

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from dev_pre_review.domain.errors import DomainError
from dev_pre_review.domain.models import DrawingArtifact

# Default 100MB limit per project global constraints
DEFAULT_MAX_BYTES = 100 * 1024 * 1024


class FileStoreError(DomainError):
    code = "file_store_error"


class FileTooLargeError(FileStoreError):
    code = "file_too_large"

    def __init__(self, size_bytes: int, max_bytes: int) -> None:
        super().__init__(f"File size {size_bytes} exceeds limit of {max_bytes} bytes")
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes


class InvalidFileFormatError(FileStoreError):
    code = "invalid_file_format"


@dataclass(frozen=True)
class StoredFile:
    sha256: str
    original_name: str
    path: Path
    size_bytes: int


class FileStore:
    def __init__(self, root: Path, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
        self.root = root
        self.max_bytes = max_bytes
        self.files_dir = self.root / "files"
        self.tmp_dir = self.root / "tmp"
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def save_bytes(self, content: bytes, original_name: str) -> StoredFile:
        size = len(content)
        if size > self.max_bytes:
            raise FileTooLargeError(size, self.max_bytes)

        hasher = hashlib.sha256()
        hasher.update(content)
        sha256_hash = hasher.hexdigest()

        # Two-level prefix directory layout: files/ab/cd/<hash>.ext
        sub_dir = self.files_dir / sha256_hash[:2] / sha256_hash[2:4]
        sub_dir.mkdir(parents=True, exist_ok=True)

        suffix = Path(original_name).suffix
        target_path = sub_dir / f"{sha256_hash}{suffix}"

        if not target_path.exists():
            tmp_path = self.tmp_dir / f"upload_{os.getpid()}_{sha256_hash}.tmp"
            tmp_path.write_bytes(content)
            tmp_path.replace(target_path)

        return StoredFile(
            sha256=sha256_hash,
            original_name=original_name,
            path=target_path,
            size_bytes=size,
        )

    def save_stream(self, stream: BinaryIO, original_name: str) -> StoredFile:
        hasher = hashlib.sha256()
        tmp_path = self.tmp_dir / f"stream_{os.getpid()}_{os.urandom(8).hex()}.tmp"
        bytes_written = 0

        try:
            with open(tmp_path, "wb") as f:
                while chunk := stream.read(64 * 1024):
                    bytes_written += len(chunk)
                    if bytes_written > self.max_bytes:
                        raise FileTooLargeError(bytes_written, self.max_bytes)
                    hasher.update(chunk)
                    f.write(chunk)

            sha256_hash = hasher.hexdigest()
            sub_dir = self.files_dir / sha256_hash[:2] / sha256_hash[2:4]
            sub_dir.mkdir(parents=True, exist_ok=True)

            suffix = Path(original_name).suffix
            target_path = sub_dir / f"{sha256_hash}{suffix}"

            if not target_path.exists():
                tmp_path.replace(target_path)
            else:
                tmp_path.unlink(missing_ok=True)

            return StoredFile(
                sha256=sha256_hash,
                original_name=original_name,
                path=target_path,
                size_bytes=bytes_written,
            )
        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    def resolve(self, drawing: DrawingArtifact) -> StoredFile:
        """Resolve a persisted drawing using its content hash and original suffix."""
        path = self.files_dir / drawing.sha256[:2] / drawing.sha256[2:4]
        path = path / f"{drawing.sha256}{Path(drawing.source_name).suffix}"
        if not path.is_file():
            raise FileStoreError(f"Stored file for drawing {drawing.id} is missing")
        return StoredFile(
            sha256=drawing.sha256,
            original_name=drawing.source_name,
            path=path,
            size_bytes=path.stat().st_size,
        )
