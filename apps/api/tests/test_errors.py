"""Tests for error handling and exception management."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.exc import DatabaseError, IntegrityError

from app.core.errors import (
    APIError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationAPIError,
    api_error_handler,
    database_error_handler,
    format_error_response,
    generic_exception_handler,
    setup_error_handlers,
    validation_error_handler,
)


class TestAPIError:
    """Test APIError exception classes."""

    def test_api_error_creation(self):
        """Test creating a basic APIError."""
        error = APIError(
            status_code=400,
            error_code="test_error",
            message="Test error message",
            details={"key": "value"},
        )

        assert error.status_code == 400
        assert error.error_code == "test_error"
        assert error.message == "Test error message"
        assert error.details == {"key": "value"}
        assert str(error) == "Test error message"

    def test_validation_api_error(self):
        """Test ValidationAPIError."""
        error = ValidationAPIError(
            message="Validation failed",
            errors=[{"field": "email", "message": "Invalid email"}],
        )

        assert error.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert error.error_code == "validation_error"
        assert error.message == "Validation failed"
        assert "errors" in error.details

    def test_not_found_error(self):
        """Test NotFoundError."""
        error = NotFoundError("User", "123")

        assert error.status_code == status.HTTP_404_NOT_FOUND
        assert error.error_code == "not_found"
        assert "123" in error.message
        assert error.details["resource"] == "User"
        assert error.details["identifier"] == "123"

    def test_not_found_error_no_identifier(self):
        """Test NotFoundError without identifier."""
        error = NotFoundError("User")

        assert error.status_code == status.HTTP_404_NOT_FOUND
        assert error.details["identifier"] is None

    def test_conflict_error(self):
        """Test ConflictError."""
        error = ConflictError("Duplicate entry", {"field": "email"})

        assert error.status_code == status.HTTP_409_CONFLICT
        assert error.error_code == "conflict"
        assert error.message == "Duplicate entry"
        assert error.details == {"field": "email"}

    def test_unauthorized_error(self):
        """Test UnauthorizedError."""
        error = UnauthorizedError("Invalid credentials")

        assert error.status_code == status.HTTP_401_UNAUTHORIZED
        assert error.error_code == "unauthorized"
        assert error.message == "Invalid credentials"

    def test_unauthorized_error_default(self):
        """Test UnauthorizedError with default message."""
        error = UnauthorizedError()

        assert error.message == "Unauthorized"

    def test_forbidden_error(self):
        """Test ForbiddenError."""
        error = ForbiddenError("Access denied")

        assert error.status_code == status.HTTP_403_FORBIDDEN
        assert error.error_code == "forbidden"
        assert error.message == "Access denied"

    def test_forbidden_error_default(self):
        """Test ForbiddenError with default message."""
        error = ForbiddenError()

        assert error.message == "Forbidden"


class TestFormatErrorResponse:
    """Test format_error_response function."""

    def test_format_api_error(self):
        """Test formatting APIError."""
        request = Mock()
        request.state.request_id = "test-123"

        error = APIError(
            status_code=400,
            error_code="test_error",
            message="Test message",
            details={"key": "value"},
        )

        response = format_error_response(error, request)

        assert "error" in response
        assert response["error"]["code"] == "test_error"
        assert response["error"]["message"] == "Test message"
        assert response["error"]["request_id"] == "test-123"
        assert response["error"]["details"] == {"key": "value"}

    def test_format_api_error_no_details(self):
        """Test formatting APIError without details."""
        request = Mock()
        request.state.request_id = "test-123"

        error = APIError(
            status_code=400,
            error_code="test_error",
            message="Test message",
        )

        response = format_error_response(error, request, include_details=False)

        assert "error" in response
        assert "details" not in response["error"]

    def test_format_validation_error(self):
        """Test formatting validation error."""
        request = Mock()
        request.state.request_id = "test-123"

        # Create a mock validation error
        validation_error = Mock(spec=RequestValidationError)
        validation_error.errors.return_value = [
            {"loc": ("body", "email"), "msg": "Invalid email", "type": "value_error"}
        ]

        response = format_error_response(validation_error, request)

        assert "error" in response
        assert response["error"]["code"] == "validation_error"
        assert "details" in response["error"]
        assert "errors" in response["error"]["details"]

    def test_format_generic_error(self):
        """Test formatting generic error."""
        request = Mock()
        request.state.request_id = "test-123"

        error = ValueError("Something went wrong")

        response = format_error_response(error, request, include_details=False)

        assert "error" in response
        assert response["error"]["code"] == "internal_error"
        assert "details" not in response["error"]

    def test_format_generic_error_with_details(self):
        """Test formatting generic error with details."""
        request = Mock()
        request.state.request_id = "test-123"

        error = ValueError("Something went wrong")

        response = format_error_response(error, request, include_details=True)

        assert "error" in response
        assert "details" in response["error"]
        assert response["error"]["details"]["type"] == "ValueError"


class TestErrorHandlers:
    """Test error handler functions."""

    @pytest.mark.asyncio
    async def test_api_error_handler(self):
        """Test api_error_handler."""
        request = Mock(spec=Request)
        request.state.request_id = "test-123"
        request.url.path = "/api/test"
        request.method = "GET"

        error = APIError(
            status_code=400,
            error_code="test_error",
            message="Test error",
        )

        with patch("app.core.errors.emit_error") as mock_emit:
            response = await api_error_handler(request, error)

        assert response.status_code == 400
        content = response.body.decode()
        assert "test_error" in content
        mock_emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_validation_error_handler(self):
        """Test validation_error_handler."""
        request = Mock(spec=Request)
        request.state.request_id = "test-123"
        request.url.path = "/api/test"
        request.method = "POST"

        validation_error = RequestValidationError(
            errors=[{"loc": ("body", "email"), "msg": "Invalid"}]
        )

        with patch("app.core.errors.emit_error") as mock_emit:
            response = await validation_error_handler(request, validation_error)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        mock_emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_database_error_handler(self):
        """Test database_error_handler."""
        request = Mock(spec=Request)
        request.state.request_id = "test-123"
        request.url.path = "/api/test"
        request.method = "POST"
        request.app.state.debug = False

        db_error = DatabaseError("Database connection failed", None, None)

        with patch("app.core.errors.emit_error") as mock_emit:
            response = await database_error_handler(request, db_error)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        content = response.body.decode()
        assert "database_error" in content
        mock_emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_database_error_handler_integrity_error(self):
        """Test database_error_handler with IntegrityError."""
        request = Mock(spec=Request)
        request.state.request_id = "test-123"
        request.url.path = "/api/test"
        request.method = "POST"
        request.app.state.debug = False

        integrity_error = IntegrityError("Duplicate key", None, None)

        with patch("app.core.errors.emit_error") as mock_emit:
            response = await database_error_handler(request, integrity_error)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        content = response.body.decode()
        assert "integrity" in content.lower()
        mock_emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_database_error_handler_with_debug(self):
        """Test database_error_handler with debug enabled."""
        request = Mock(spec=Request)
        request.state.request_id = "test-123"
        request.url.path = "/api/test"
        request.method = "POST"
        request.app.state.debug = True

        db_error = DatabaseError("Database connection failed", None, None)

        with patch("app.core.errors.emit_error") as mock_emit:
            response = await database_error_handler(request, db_error)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        content = response.body.decode()
        assert "details" in content
        mock_emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_generic_exception_handler(self):
        """Test generic_exception_handler."""
        request = Mock(spec=Request)
        request.state.request_id = "test-123"
        request.url.path = "/api/test"
        request.method = "POST"
        request.app.state.debug = False

        error = ValueError("Unexpected error")

        with patch("app.core.errors.emit_error") as mock_emit:
            response = await generic_exception_handler(request, error)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        content = response.body.decode()
        assert "internal_error" in content
        mock_emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_generic_exception_handler_with_debug(self):
        """Test generic_exception_handler with debug enabled."""
        request = Mock(spec=Request)
        request.state.request_id = "test-123"
        request.url.path = "/api/test"
        request.method = "POST"
        request.app.state.debug = True

        error = ValueError("Unexpected error")

        with patch("app.core.errors.emit_error") as mock_emit:
            response = await generic_exception_handler(request, error)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        content = response.body.decode()
        assert "details" in content
        assert "traceback" in content
        mock_emit.assert_called_once()


class TestSetupErrorHandlers:
    """Test setup_error_handlers function."""

    def test_setup_error_handlers(self):
        """Test setting up error handlers."""
        app = FastAPI()
        setup_error_handlers(app, debug=True)

        assert hasattr(app.state, "debug")
        assert app.state.debug is True

        # Verify handlers are registered
        # FastAPI doesn't expose handlers directly, but we can verify
        # by checking that the app has exception handlers
        assert len(app.exception_handlers) > 0

    def test_setup_error_handlers_debug_false(self):
        """Test setting up error handlers with debug=False."""
        app = FastAPI()
        setup_error_handlers(app, debug=False)

        assert app.state.debug is False

