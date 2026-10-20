import os
from pathlib import Path
from typing import Literal

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from dev_pre_review import __version__
from dev_pre_review.storage.database import Database

LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 17841

_GLOBAL_DB: Database | None = None


def get_database() -> Database:
    global _GLOBAL_DB
    if _GLOBAL_DB is None:
        db_path_env = os.environ.get("DEV_PRE_REVIEW_DB_PATH")
        if db_path_env:
            db_path = Path(db_path_env)
        else:
            db_path = Path.home() / ".dev_pre_review" / "dev_pre_review.db"
        _GLOBAL_DB = Database.from_path(db_path)
        _GLOBAL_DB.upgrade()
    return _GLOBAL_DB


def set_database(db: Database | None) -> None:
    global _GLOBAL_DB
    _GLOBAL_DB = db


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


def create_app() -> FastAPI:
    app = FastAPI(title="Dev Pre-Review", version=__version__)

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=__version__)

    from dev_pre_review.api.drawings import router as drawings_router
    from dev_pre_review.api.knowledge import router as knowledge_router
    from dev_pre_review.api.rules import router as rules_router

    app.include_router(drawings_router)
    app.include_router(knowledge_router)
    app.include_router(rules_router)

    return app


def run() -> None:
    """Run the API bound to localhost only (never 0.0.0.0)."""
    uvicorn.run(create_app(), host=LOCAL_HOST, port=LOCAL_PORT)


if __name__ == "__main__":
    run()
