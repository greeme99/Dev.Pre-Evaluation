"""SQLite engine, session factory and programmatic Alembic upgrade."""

from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

# apps/api/src/dev_pre_review/storage/database.py -> apps/api
_API_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = _API_ROOT / "migrations"


def _configure_sqlite(dbapi_connection: Any, _record: Any) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
    finally:
        cursor.close()


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        self.engine: Engine = create_engine(url, connect_args={"check_same_thread": False})
        event.listen(self.engine, "connect", _configure_sqlite)
        self.sessions: sessionmaker[Session] = sessionmaker(self.engine, expire_on_commit=False)

    @classmethod
    def from_path(cls, path: Path) -> "Database":
        path.parent.mkdir(parents=True, exist_ok=True)
        return cls(f"sqlite+pysqlite:///{path.resolve().as_posix()}")

    def upgrade(self, revision: str = "head") -> None:
        config = Config()
        config.set_main_option("script_location", str(MIGRATIONS_DIR))
        with self.engine.connect() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, revision)

    def dispose(self) -> None:
        self.engine.dispose()
