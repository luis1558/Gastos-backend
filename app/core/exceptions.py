from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_build_error_payload(
                code="http_error",
                message=str(exc.detail),
                path=request.url.path,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_build_error_payload(
                code="validation_error",
                message="Request validation failed.",
                path=request.url.path,
                details=exc.errors(),
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_build_error_payload(
                code="internal_server_error",
                message="An unexpected error occurred.",
                path=request.url.path,
            ),
        )


def _build_error_payload(
    code: str,
    message: str,
    path: str,
    details=None,
) -> dict:
    payload = {
        "error": {
            "code": code,
            "message": message,
            "path": path,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }
    if details is not None:
        payload["error"]["details"] = details
    return payload
