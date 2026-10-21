"""Bounded retention tests for server-owned Excel import previews."""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import uuid4

from dev_pre_review.knowledge.preview_store import ImportPreviewStore


def test_resolve_removes_expired_preview(tmp_path: Path) -> None:
    source = tmp_path / "source.xlsx"
    source.write_bytes(b"preview")
    store = ImportPreviewStore(tmp_path / "previews", ttl_seconds=10)
    preview_id = uuid4()
    saved = store.save(preview_id, source)
    os.utime(saved, (1, 1))

    store.cleanup(now=20)

    assert not saved.exists()


def test_save_evicts_oldest_preview_to_enforce_total_capacity(tmp_path: Path) -> None:
    source = tmp_path / "source.xlsx"
    source.write_bytes(b"123456")
    store = ImportPreviewStore(tmp_path / "previews", ttl_seconds=10**12, max_total_bytes=10)
    oldest_id = uuid4()
    oldest = store.save(oldest_id, source)
    os.utime(oldest, (1, 1))

    newest_id = uuid4()
    newest = store.save(newest_id, source)

    assert not oldest.exists()
    assert newest.read_bytes() == b"123456"


def test_lease_prevents_concurrent_eviction_while_preview_is_read(tmp_path: Path) -> None:
    source = tmp_path / "source.xlsx"
    source.write_bytes(b"123456")
    store = ImportPreviewStore(tmp_path / "previews", max_total_bytes=6)
    leased_id = uuid4()
    leased = store.save(leased_id, source)
    started = Event()
    finished = Event()

    def save_replacement() -> None:
        started.set()
        store.save(uuid4(), source)
        finished.set()

    with ThreadPoolExecutor(max_workers=1) as executor:
        with store.lease(leased_id) as leased_path:
            future = executor.submit(save_replacement)
            assert started.wait(timeout=1)
            assert not finished.wait(timeout=0.05)
            assert leased_path.read_bytes() == b"123456"
        future.result(timeout=1)

    assert not leased.exists()
    assert sum(path.stat().st_size for path in store.root.glob("*.xlsx")) <= 6
