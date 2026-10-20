"""Tests for atomic file storage and hash-based paths."""

from pathlib import Path

import pytest

from dev_pre_review.storage.files import FileStore, FileTooLargeError


def test_stores_file_by_sha256_atomically(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    content = b"test content for hash storage"

    stored_file = store.save_bytes(content, original_name="sample.xlsx")

    assert stored_file.size_bytes == len(content)
    assert stored_file.sha256 != ""
    assert stored_file.path.exists()
    assert stored_file.path.read_bytes() == content


def test_rejects_file_exceeding_size_limit(tmp_path: Path) -> None:
    store = FileStore(tmp_path, max_bytes=10)

    with pytest.raises(FileTooLargeError):
        store.save_bytes(b"longer than 10 bytes content", original_name="huge.xlsx")
