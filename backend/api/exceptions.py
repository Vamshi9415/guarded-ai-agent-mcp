# backend/api/exceptions.py
"""Global exception handlers and reusable HTTP helpers.

Centralising exception handling here means routers can raise plain Python
exceptions (KeyError, ValueError) and let these handlers convert them into
correct HTTP responses, rather than importing HTTPException everywhere.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def not_found(detail: str) -> HTTPException:
    """Returns a 404 Not Found exception."""
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def bad_request(detail: str) -> HTTPException:
    """Returns a 400 Bad Request exception."""
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def conflict(detail: str) -> HTTPException:
    """Returns a 409 Conflict exception."""
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def register_exception_handlers(app: FastAPI) -> None:
    """Registers global exception handlers on the app instance."""

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        body = await request.body()
        logger.warning(
            "Request validation failed %s %s errors=%s body=%s",
            request.method,
            request.url.path,
            exc.errors(),
            body.decode("utf-8", errors="replace") if body else "<empty>",
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors()},
        )

    @app.exception_handler(KeyError)
    async def key_error_handler(request: Request, exc: KeyError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc).strip("'\"")},
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred."},
        )