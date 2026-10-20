"""FastAPI application factory and local entry point."""

from typing import Literal

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from dev_pre_review import __version__

LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 17841


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


def create_app() -> FastAPI:
    app = FastAPI(title="Dev Pre-Review", version=__version__)

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=__version__)

    from dev_pre_review.api.knowledge import router as knowledge_router

    app.include_router(knowledge_router)

    return app


def run() -> None:
    """Run the API bound to localhost only (never 0.0.0.0)."""
    uvicorn.run(create_app(), host=LOCAL_HOST, port=LOCAL_PORT)


if __name__ == "__main__":
    run()
