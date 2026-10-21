from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal
from urllib.parse import urlsplit

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from dev_pre_review import __version__
from dev_pre_review.analysis.runtime import create_analysis_worker
from dev_pre_review.storage.database import Database
from dev_pre_review.storage.paths import (
    ensure_data_directories,
    get_artifacts_dir,
    get_database_path,
)

LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 17841
MAX_RESTORE_REQUEST_BYTES = 101 * 1024 * 1024
MAX_EXCEL_REQUEST_BYTES = 101 * 1024 * 1024
MAX_DRAWING_REQUEST_BYTES = 201 * 1024 * 1024

_GLOBAL_DB: Database | None = None


class _RequestBodyTooLarge(Exception):
    pass


class RequestBodyLimitMiddleware:
    """Reject oversized uploads before multipart parsing writes temporary data."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        max_bytes = _request_body_limit(scope)
        if max_bytes is None:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                if int(content_length) > max_bytes:
                    await self._reject(scope, receive, send)
                    return
            except ValueError:
                pass

        received = 0

        async def receive_limited() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > max_bytes:
                    raise _RequestBodyTooLarge
            return message

        try:
            await self.app(scope, receive_limited, send)
        except _RequestBodyTooLarge:
            await self._reject(scope, receive, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse(
            status_code=413,
            content={"detail": {"code": "request_body_too_large"}},
        )
        await response(scope, receive, send)


def _request_body_limit(scope: Scope) -> int | None:
    if scope["type"] != "http" or scope.get("method") != "POST":
        return None
    path = scope.get("path", "")
    if path in {"/api/restores/preview", "/api/restores/commit"}:
        return MAX_RESTORE_REQUEST_BYTES
    if path == "/api/knowledge/imports/preview":
        return MAX_EXCEL_REQUEST_BYTES
    if path == "/api/drawings/validate" or (
        path.startswith("/api/projects/") and path.endswith("/drawings")
    ):
        return MAX_DRAWING_REQUEST_BYTES
    return None


def get_database() -> Database:
    global _GLOBAL_DB
    if _GLOBAL_DB is None:
        _GLOBAL_DB = Database.from_path(get_database_path())
        _GLOBAL_DB.upgrade()
    return _GLOBAL_DB


def set_database(db: Database | None) -> None:
    global _GLOBAL_DB
    _GLOBAL_DB = db


class HealthResponse(BaseModel):
    product: Literal["dev-pre-review"]
    status: Literal["ok"]
    version: str


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        db = get_database()
        ensure_data_directories()
        worker = create_analysis_worker(db, get_artifacts_dir())
        worker.runner.resume_pending()
        worker.start()
        app.state.analysis_worker = worker
        try:
            yield
        finally:
            worker.stop()

    app = FastAPI(title="Dev Pre-Review", version=__version__, lifespan=lifespan)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "testserver"],
    )
    app.add_middleware(RequestBodyLimitMiddleware)

    @app.middleware("http")
    async def protect_local_mutations(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if origin:
                parsed = urlsplit(origin)
                if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": {"code": "untrusted_origin"}},
                    )
        return await call_next(request)

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(product="dev-pre-review", status="ok", version=__version__)

    from dev_pre_review.api.analyses import router as analyses_router
    from dev_pre_review.api.drawings import router as drawings_router
    from dev_pre_review.api.errors import register_error_handlers
    from dev_pre_review.api.export import router as export_router
    from dev_pre_review.api.knowledge import router as knowledge_router
    from dev_pre_review.api.projects import router as projects_router
    from dev_pre_review.api.rules import router as rules_router
    from dev_pre_review.api.settings import router as settings_router

    register_error_handlers(app)

    app.include_router(drawings_router)
    app.include_router(projects_router)
    app.include_router(knowledge_router)
    app.include_router(rules_router)
    app.include_router(analyses_router)
    app.include_router(settings_router)
    app.include_router(export_router)

    return app


def run() -> None:
    """Run the API bound to localhost only (never 0.0.0.0)."""
    uvicorn.run(create_app(), host=LOCAL_HOST, port=LOCAL_PORT)


if __name__ == "__main__":
    run()
