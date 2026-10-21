"""Operating-system-specific path resolution and directory management.

References: TC-105, TC-106, TC-108.
"""

import os
import sys
from pathlib import Path


def get_app_data_dir() -> Path:
    """Returns the base application data directory.

    Order of precedence:
    1. DEV_PRE_REVIEW_DATA_DIR environment variable
    2. Windows: %LOCALAPPDATA%/DevPreReview
    3. macOS: ~/Library/Application Support/DevPreReview
    4. Linux/Other: ~/.local/share/dev_pre_review
    """
    env_dir = os.environ.get("DEV_PRE_REVIEW_DATA_DIR")
    if env_dir:
        return Path(env_dir).resolve()

    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "DevPreReview"
        return Path.home() / "AppData" / "Local" / "DevPreReview"

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "DevPreReview"

    return Path.home() / ".local" / "share" / "dev_pre_review"


def get_database_path() -> Path:
    """Returns the SQLite database file path."""
    override = os.environ.get("DEV_PRE_REVIEW_DB_PATH")
    if override:
        return Path(override).resolve()
    return get_app_data_dir() / "dev_pre_review.db"


def get_artifacts_dir() -> Path:
    """Returns the directory for uploaded and rendered drawing artifacts."""
    return get_app_data_dir() / "artifacts"


def get_logs_dir() -> Path:
    """Returns the directory for diagnostic execution logs."""
    return get_app_data_dir() / "logs"


def ensure_data_directories() -> None:
    """Creates all required persistent data directories if they do not exist."""
    base = get_app_data_dir()
    base.mkdir(parents=True, exist_ok=True)
    get_artifacts_dir().mkdir(parents=True, exist_ok=True)
    get_logs_dir().mkdir(parents=True, exist_ok=True)
