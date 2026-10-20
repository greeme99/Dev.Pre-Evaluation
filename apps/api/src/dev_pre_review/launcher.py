"""Application launcher managing single-instance lifecycle and local web serving.

References: TC-008, TC-033, TC-106, TC-108, plan.md.
"""

import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from pathlib import Path

from fastapi.staticfiles import StaticFiles

from dev_pre_review.main import create_app
from dev_pre_review.storage.paths import ensure_data_directories


@dataclass
class LauncherConfig:
    host: str = "127.0.0.1"
    port: int = 17841
    data_dir: Path | None = None
    static_dir: Path | None = None
    open_browser: bool = True

    def __post_init__(self) -> None:
        # Strict security constraint: Loopback only (TC-108)
        allowed = {"127.0.0.1", "localhost", "::1"}
        if self.host not in allowed:
            raise ValueError(
                f"Security violation: Only loopback binding is permitted, got '{self.host}'"
            )


def check_port_available(host: str, port: int) -> bool:
    """Checks whether the specified TCP port is available for binding."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def verify_instance_status(config: LauncherConfig) -> str:
    """Determines if the target port is free, running our app, or occupied by another process.

    Returns:
    - 'ready': Port is free to bind.
    - 'running': Same application is already running and responded to health check.
    - 'conflict': An alien process occupies the port.
    """
    if check_port_available(config.host, config.port):
        return "ready"

    health_url = f"http://{config.host}:{config.port}/health"
    try:
        req = urllib.request.Request(health_url, method="GET")
        with urllib.request.urlopen(req, timeout=1.0) as resp:  # noqa: S310
            if resp.status == 200:
                body = resp.read().decode("utf-8")
                if "ok" in body or "status" in body:
                    return "running"
    except Exception:  # noqa: S110
        pass

    return "conflict"


def run_launcher(config: LauncherConfig | None = None) -> int:
    """Entrypoint to launch or focus the local desktop web application."""
    cfg = config or LauncherConfig()
    ensure_data_directories()

    status = verify_instance_status(cfg)

    app_url = f"http://{cfg.host}:{cfg.port}"

    if status == "running":
        sys.stdout.write(
            f"Dev.Pre-Evaluation is already running at {app_url}. Focusing window...\n"
        )
        if cfg.open_browser:
            webbrowser.open(app_url)
        return 0

    if status == "conflict":
        sys.stderr.write(
            f"Error: Port {cfg.port} is occupied by another process. "
            "Please terminate it and retry.\n"
        )
        return 1

    # Status is 'ready': Launch uvicorn server
    app = create_app()

    # Mount static assets if provided (bundled React web dist)
    if cfg.static_dir and Path(cfg.static_dir).exists():
        app.mount("/", StaticFiles(directory=cfg.static_dir, html=True), name="static")

    if cfg.open_browser:

        def _open_later() -> None:
            time.sleep(1.0)
            webbrowser.open(app_url)

        threading.Thread(target=_open_later, daemon=True).start()

    import uvicorn

    uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(run_launcher())
