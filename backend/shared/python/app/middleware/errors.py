"""Centralized error handling — AppError exception and FastAPI exception handlers."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Application-level error with HTTP status code and user-facing message.

    Usage:
        raise AppError("Invoice not found", status_code=404)
        raise AppError("File size exceeds the 10MB limit.", status_code=400)
    """

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI application."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", "unknown")
        logger.warning(
            "Application error: %s",
            exc.message,
            extra={
                "status_code": exc.status_code,
                "correlation_id": correlation_id,
                "path": request.url.path,
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"statusCode": exc.status_code, "error": exc.message},
            headers={"X-Correlation-Id": correlation_id},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", "unknown")
        # Extract the first meaningful validation error message
        errors = exc.errors()
        if errors:
            first = errors[0]
            field = " -> ".join(str(loc) for loc in first.get("loc", []) if loc != "body")
            message = first.get("msg", "Validation error")
            detail = f"{field}: {message}" if field else message
        else:
            detail = "Invalid request data."

        logger.warning(
            "Validation error: %s",
            detail,
            extra={
                "correlation_id": correlation_id,
                "path": request.url.path,
                "errors": str(errors),
            },
        )
        return JSONResponse(
            status_code=400,
            content={"statusCode": 400, "error": detail},
            headers={"X-Correlation-Id": correlation_id},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", "unknown")
        logger.error(
            "Unhandled exception: %s",
            str(exc),
            exc_info=True,
            extra={
                "correlation_id": correlation_id,
                "path": request.url.path,
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "statusCode": 500,
                "error": "An internal error occurred. Please try again.",
            },
            headers={"X-Correlation-Id": correlation_id},
        )
