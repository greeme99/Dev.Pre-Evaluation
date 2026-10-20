"""RFC 7807 Problem Details error handlers with Korean messages (API-003)."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from dev_pre_review.domain.errors import (
    InvalidStateTransition,
    NotFound,
    ProjectBusy,
    VersionConflict,
)
from dev_pre_review.models.consent import ConsentError


def problem_details(
    status: int,
    title: str,
    detail: str,
    error_type: str = "about:blank",
    instance: str | None = None,
) -> JSONResponse:
    content = {
        "type": error_type,
        "title": title,
        "status": status,
        "detail": detail,
    }
    if instance:
        content["instance"] = instance
    return JSONResponse(
        status_code=status,
        content=content,
        media_type="application/problem+json",
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFound)
    async def not_found_handler(request: Request, exc: NotFound) -> JSONResponse:
        return problem_details(
            status=404,
            title="리소스를 찾을 수 없음 (NotFound)",
            detail=f"{exc.entity} '{exc.entity_id}' 리소스가 존재하지 않거나 찾을 수 없습니다.",
            instance=str(request.url),
        )

    @app.exception_handler(ProjectBusy)
    async def project_busy_handler(request: Request, exc: ProjectBusy) -> JSONResponse:
        detail_msg = (
            f"프로젝트 '{exc.project_id}'에서 실행 중인 작업이 있어 요청을 수행할 수 없습니다."
        )
        return problem_details(
            status=409,
            title="프로젝트 처리 중 충돌 (ProjectBusy)",
            detail=detail_msg,
            instance=str(request.url),
        )

    @app.exception_handler(VersionConflict)
    async def version_conflict_handler(request: Request, exc: VersionConflict) -> JSONResponse:
        return problem_details(
            status=409,
            title="동시 수정 충돌 (VersionConflict)",
            detail="다른 사용자에 의해 데이터가 변경되었습니다. 최신 데이터를 새로고침하십시오.",
            instance=str(request.url),
        )

    @app.exception_handler(ConsentError)
    async def consent_error_handler(request: Request, exc: ConsentError) -> JSONResponse:
        return problem_details(
            status=403,
            title="외부 전송 동의 필요 (ConsentRequired)",
            detail=str(exc),
            instance=str(request.url),
        )

    @app.exception_handler(InvalidStateTransition)
    async def invalid_state_handler(request: Request, exc: InvalidStateTransition) -> JSONResponse:
        detail_msg = (
            f"{exc.entity}의 현재 상태 '{exc.current}'에서는 "
            f"'{exc.action}' 작업을 수행할 수 없습니다."
        )
        return problem_details(
            status=400,
            title="잘못된 상태 전이 (InvalidStateTransition)",
            detail=detail_msg,
            instance=str(request.url),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return problem_details(
            status=422,
            title="입력값 유효성 검증 실패 (ValidationError)",
            detail=str(exc.errors()),
            instance=str(request.url),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        title = "요청 처리 오류"
        if exc.status_code == 404:
            title = "요청한 경로를 찾을 수 없음 (NotFound)"
        return problem_details(
            status=exc.status_code,
            title=title,
            detail=str(exc.detail),
            instance=str(request.url),
        )
