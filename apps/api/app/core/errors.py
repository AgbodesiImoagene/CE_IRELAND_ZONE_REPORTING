"""Error handling and exception management.

Provides global exception handlers and structured error responses
for better observability and user experience.
"""

from __future__ import annotations

import logging
import traceback
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import DatabaseError, IntegrityError

from app.core.metrics import emit_error

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base exception for API errors.

    Attributes:
        status_code: HTTP status code
        error_code: Application-specific error code
        message: Human-readable error message
        details: Optional additional error details
    """

    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ):
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ValidationAPIError(APIError):
    """Validation error with detailed field information."""

    def __init__(
        self,
        message: str = "Validation error",
        errors: list[dict[str, Any]] | None = None,
    ):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            error_code="validation_error",
            message=message,
            details={"errors": errors or []},
        )


class NotFoundError(APIError):
    """Resource not found error."""

    def __init__(self, resource: str, identifier: str | None = None):
        message = f"{resource} not found"
        if identifier:
            message += f": {identifier}"
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="not_found",
            message=message,
            details={"resource": resource, "identifier": identifier},
        )


class ConflictError(APIError):
    """Resource conflict error (e.g., duplicate entry)."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error_code="conflict",
            message=message,
            details=details or {},
        )


class UnauthorizedError(APIError):
    """Unauthorized access error."""

    def __init__(self, message: str = "Unauthorized"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="unauthorized",
            message=message,
        )


class ForbiddenError(APIError):
    """Forbidden access error."""

    def __init__(self, message: str = "Forbidden"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="forbidden",
            message=message,
        )


def format_error_response(
    error: Exception,
    request: Request,
    include_details: bool = False,
) -> dict[str, Any]:
    """Format error response with structured information.

    Args:
        error: The exception that occurred
        request: FastAPI request object
        include_details: Whether to include detailed error information

    Returns:
        Dictionary with error response structure
    """
    request_id = getattr(request.state, "request_id", None)

    if isinstance(error, APIError):
        response_data = {
            "error": {
                "code": error.error_code,
                "message": error.message,
                "request_id": request_id,
            }
        }

        if error.details or include_details:
            response_data["error"]["details"] = error.details

        return response_data

    # Handle validation errors
    if isinstance(error, (RequestValidationError, ValidationError)):
        errors = []
        if hasattr(error, "errors"):
            errors = error.errors()
        elif hasattr(error, "errors"):
            errors = error.errors

        response_data = {
            "error": {
                "code": "validation_error",
                "message": "Validation failed",
                "request_id": request_id,
                "details": {
                    "errors": [
                        {
                            "field": ".".join(str(loc) for loc in err.get("loc", [])),
                            "message": err.get("msg", "Invalid value"),
                            "type": err.get("type", "validation_error"),
                        }
                        for err in errors
                    ]
                },
            }
        }
        return response_data

    # Generic error handling
    response_data = {
        "error": {
            "code": "internal_error",
            "message": "An internal error occurred",
            "request_id": request_id,
        }
    }

    if include_details:
        response_data["error"]["details"] = {
            "type": type(error).__name__,
            "message": str(error),
        }

    return response_data


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle APIError exceptions."""
    request_id = getattr(request.state, "request_id", None)

    # Log the error
    logger.warning(
        f"API error: {exc.error_code} - {exc.message}",
        extra={
            "request_id": request_id,
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method,
        },
    )

    # Emit error metric
    emit_error(
        error_code=exc.error_code,
        status_code=exc.status_code,
        path=request.url.path,
        method=request.method,
        request_id=request_id,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=format_error_response(exc, request, include_details=True),
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle validation errors."""
    request_id = getattr(request.state, "request_id", None)

    # Log validation errors at INFO level (they're client errors, not bugs)
    logger.info(
        f"Validation error: {str(exc)}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "errors": exc.errors(),
        },
    )

    # Emit error metric
    emit_error(
        error_code="validation_error",
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        path=request.url.path,
        method=request.method,
        request_id=request_id,
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=format_error_response(exc, request, include_details=True),
    )


async def database_error_handler(request: Request, exc: DatabaseError) -> JSONResponse:
    """Handle database errors."""
    request_id = getattr(request.state, "request_id", None)

    # Log database errors
    logger.error(
        f"Database error: {str(exc)}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "exception_type": type(exc).__name__,
        },
        exc_info=True,
    )

    # Emit error metric
    emit_error(
        error_code="database_error",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        path=request.url.path,
        method=request.method,
        request_id=request_id,
    )

    # Don't expose database details in production
    include_details = (
        request.app.state.debug if hasattr(request.app.state, "debug") else False
    )

    error_message = "A database error occurred"
    if isinstance(exc, IntegrityError):
        error_message = "Database integrity constraint violated"

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "database_error",
                "message": error_message,
                "request_id": request_id,
                **(
                    {"details": {"type": type(exc).__name__, "message": str(exc)}}
                    if include_details
                    else {}
                ),
            }
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    request_id = getattr(request.state, "request_id", None)

    # Log with full traceback
    logger.error(
        f"Unhandled exception: {type(exc).__name__}: {str(exc)}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "exception_type": type(exc).__name__,
        },
        exc_info=True,
    )

    # Emit error metric
    emit_error(
        error_code="internal_error",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        path=request.url.path,
        method=request.method,
        request_id=request_id,
    )

    # Don't expose internal details in production
    include_details = (
        request.app.state.debug if hasattr(request.app.state, "debug") else False
    )

    response_data = {
        "error": {
            "code": "internal_error",
            "message": "An internal error occurred",
            "request_id": request_id,
        }
    }

    if include_details:
        response_data["error"]["details"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc().split("\n"),
        }

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response_data,
    )


def setup_error_handlers(app: FastAPI, debug: bool = False) -> None:
    """Register global exception handlers.

    Args:
        app: FastAPI application instance
        debug: Whether to include detailed error information
    """
    app.state.debug = debug

    # Register exception handlers (order matters - most specific first)
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(ValidationError, validation_error_handler)
    app.add_exception_handler(DatabaseError, database_error_handler)
    app.add_exception_handler(IntegrityError, database_error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
