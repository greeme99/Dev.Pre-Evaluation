"""Tests for launcher, single-instance verification, and data paths (TC-106, TC-108)."""

import io
import json
import socket
import sys
from pathlib import Path

import pytest

from dev_pre_review.launcher import (
    LauncherConfig,
    check_port_available,
    resolve_static_dir,
    verify_instance_status,
)
from dev_pre_review.main import get_database, set_database
from dev_pre_review.storage.paths import (
    ensure_data_directories,
    get_app_data_dir,
    get_artifacts_dir,
    get_database_path,
    get_logs_dir,
)


def test_app_data_dir_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    custom_dir = tmp_path / "custom_data"
    monkeypatch.setenv("DEV_PRE_REVIEW_DATA_DIR", str(custom_dir))

    data_dir = get_app_data_dir()
    assert data_dir == custom_dir
    assert get_database_path() == custom_dir / "dev_pre_review.db"
    assert get_artifacts_dir() == custom_dir / "artifacts"
    assert get_logs_dir() == custom_dir / "logs"


def test_database_path_uses_shared_data_dir_and_explicit_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_database(None)
    data_dir = tmp_path / "shared-data"
    monkeypatch.setenv("DEV_PRE_REVIEW_DATA_DIR", str(data_dir))
    monkeypatch.delenv("DEV_PRE_REVIEW_DB_PATH", raising=False)

    assert get_database_path() == data_dir / "dev_pre_review.db"
    database = get_database()
    assert database.engine.url.database == str((data_dir / "dev_pre_review.db").resolve())
    database.dispose()
    set_database(None)

    explicit_path = tmp_path / "operator-selected.db"
    monkeypatch.setenv("DEV_PRE_REVIEW_DB_PATH", str(explicit_path))
    assert get_database_path() == explicit_path.resolve()
    overridden_database = get_database()
    assert overridden_database.engine.url.database == str(explicit_path.resolve())
    overridden_database.dispose()
    set_database(None)


def test_ensure_data_directories(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    custom_dir = tmp_path / "app_data_test"
    monkeypatch.setenv("DEV_PRE_REVIEW_DATA_DIR", str(custom_dir))

    ensure_data_directories()
    assert (custom_dir / "artifacts").exists()
    assert (custom_dir / "logs").exists()


def test_port_availability_check() -> None:
    # Ephemeral free port test
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        _, port = s.getsockname()

    # Port should be free now that socket closed
    assert check_port_available("127.0.0.1", port) is True


def test_launcher_security_rejects_non_loopback() -> None:
    # Strictly forbid binding to 0.0.0.0 or public interfaces (TC-108)
    with pytest.raises(ValueError, match="Only loopback binding"):
        LauncherConfig(host="0.0.0.0", port=17841)

    with pytest.raises(ValueError, match="Only loopback binding"):
        LauncherConfig(host="192.168.1.100", port=17841)

    with pytest.raises(ValueError, match="Only loopback binding"):
        LauncherConfig(host="::1", port=17841)


def test_verify_instance_status_free_port() -> None:
    # Use random free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        _, free_port = s.getsockname()

    config = LauncherConfig(host="127.0.0.1", port=free_port)
    status = verify_instance_status(config)
    assert status == "ready"


def test_verify_instance_status_alien_process_conflict() -> None:
    # Occupy a port with dummy raw socket server
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    _, occupied_port = sock.getsockname()

    try:
        config = LauncherConfig(host="127.0.0.1", port=occupied_port)
        status = verify_instance_status(config)
        # Alien process without our /health token
        assert status == "conflict"
    finally:
        sock.close()


class _FakeHttpResponse:
    def __init__(self, payload: dict[str, str]) -> None:
        self.status = 200
        self._body = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def __enter__(self) -> "_FakeHttpResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body.read()


def test_verify_instance_status_requires_exact_product_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = LauncherConfig()
    monkeypatch.setattr("dev_pre_review.launcher.check_port_available", lambda *_args: False)

    monkeypatch.setattr(
        "dev_pre_review.launcher.urllib.request.urlopen",
        lambda *_args, **_kwargs: _FakeHttpResponse(
            {"product": "dev-pre-review", "status": "ok", "version": "0.1.0"}
        ),
    )
    assert verify_instance_status(config) == "running"

    monkeypatch.setattr(
        "dev_pre_review.launcher.urllib.request.urlopen",
        lambda *_args, **_kwargs: _FakeHttpResponse(
            {"product": "another-product", "status": "ok", "version": "0.1.0"}
        ),
    )
    assert verify_instance_status(config) == "conflict"


def test_resolve_static_dir_uses_frozen_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundled_static = tmp_path / "web" / "dist"
    bundled_static.mkdir(parents=True)
    (bundled_static / "index.html").write_text("<main>app</main>", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert resolve_static_dir() == bundled_static
