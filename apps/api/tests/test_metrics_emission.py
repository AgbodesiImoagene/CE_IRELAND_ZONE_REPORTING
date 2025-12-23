"""Tests for OpenTelemetry metrics emission functionality."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

from app.core.otel_metrics import (
    emit_business_metric,
    emit_database_query,
    emit_error,
    emit_http_request,
    emit_redis_operation,
)


class TestMetricsEmission:
    """Test OpenTelemetry metrics emission functions."""

    @patch("app.core.otel_metrics._get_db_query_counter")
    @patch("app.core.otel_metrics._get_db_query_duration")
    def test_emit_database_query_success(self, mock_duration, mock_counter):
        """Test that database query metrics are emitted correctly."""
        mock_counter_instance = MagicMock()
        mock_counter.return_value = mock_counter_instance
        mock_duration_instance = MagicMock()
        mock_duration.return_value = mock_duration_instance

        emit_database_query(
            operation="SELECT",
            duration_ms=25.5,
            success=True,
            table="users",
        )

        # Verify counter was called
        mock_counter_instance.add.assert_called_once()
        call_args = mock_counter_instance.add.call_args
        assert call_args[0][0] == 1  # Count
        assert call_args[1]["attributes"]["db.operation"] == "SELECT"
        assert call_args[1]["attributes"]["db.success"] == "true"
        assert call_args[1]["attributes"]["table"] == "users"

        # Verify duration histogram was called
        mock_duration_instance.record.assert_called_once()
        duration_args = mock_duration_instance.record.call_args
        assert duration_args[0][0] == 25.5
        assert duration_args[1]["attributes"]["db.operation"] == "SELECT"

    @patch("app.core.otel_metrics._get_db_query_counter")
    @patch("app.core.otel_metrics._get_db_query_duration")
    def test_emit_database_query_error(self, mock_duration, mock_counter):
        """Test that database query errors emit error metrics."""
        mock_counter_instance = MagicMock()
        mock_counter.return_value = mock_counter_instance
        mock_duration_instance = MagicMock()
        mock_duration.return_value = mock_duration_instance

        emit_database_query(
            operation="SELECT",
            duration_ms=10.0,
            success=False,
            error_type="ConnectionError",
        )

        call_args = mock_counter_instance.add.call_args
        assert call_args[1]["attributes"]["db.success"] == "false"
        assert call_args[1]["attributes"]["error_type"] == "ConnectionError"

    @patch("app.core.otel_metrics._get_redis_operation_counter")
    @patch("app.core.otel_metrics._get_redis_operation_duration")
    def test_emit_redis_operation_success(self, mock_duration, mock_counter):
        """Test that Redis operation metrics are emitted correctly."""
        mock_counter_instance = MagicMock()
        mock_counter.return_value = mock_counter_instance
        mock_duration_instance = MagicMock()
        mock_duration.return_value = mock_duration_instance

        emit_redis_operation(
            operation="GET",
            duration_ms=5.2,
            success=True,
            key="test_key",
        )

        call_args = mock_counter_instance.add.call_args
        assert call_args[0][0] == 1
        assert call_args[1]["attributes"]["redis.operation"] == "GET"
        assert call_args[1]["attributes"]["redis.success"] == "true"
        assert call_args[1]["attributes"]["key"] == "test_key"

        duration_args = mock_duration_instance.record.call_args
        assert duration_args[0][0] == 5.2

    @patch("app.core.otel_metrics._get_error_counter")
    def test_emit_error_metric(self, mock_counter):
        """Test that error metrics are emitted correctly."""
        mock_counter_instance = MagicMock()
        mock_counter.return_value = mock_counter_instance

        emit_error(
            error_code="validation_error",
            status_code=422,
            path="/api/v1/users",
            method="POST",
            user_id="user123",
        )

        call_args = mock_counter_instance.add.call_args
        assert call_args[0][0] == 1
        assert call_args[1]["attributes"]["error.code"] == "validation_error"
        assert call_args[1]["attributes"]["http.status_code"] == "422"
        assert call_args[1]["attributes"]["error.severity"] == "client_error"
        assert call_args[1]["attributes"]["user_id"] == "user123"

    @patch("app.core.otel_metrics._get_error_counter")
    def test_emit_error_server_error_severity(self, mock_counter):
        """Test that 500+ errors have server_error severity."""
        mock_counter_instance = MagicMock()
        mock_counter.return_value = mock_counter_instance

        emit_error(
            error_code="internal_error",
            status_code=500,
            path="/api/v1/users",
            method="GET",
        )

        call_args = mock_counter_instance.add.call_args
        assert call_args[1]["attributes"]["error.severity"] == "server_error"

    @patch("app.core.otel_metrics._get_business_metric_counter")
    def test_emit_business_metric(self, mock_counter):
        """Test that business metrics are emitted correctly."""
        mock_counter_instance = MagicMock()
        mock_counter.return_value = mock_counter_instance

        emit_business_metric(
            metric_name="UserSignup",
            value=1,
            category="user",
            tenant_id="tenant123",
        )

        call_args = mock_counter_instance.add.call_args
        assert call_args[0][0] == 1
        assert call_args[1]["attributes"]["metric.name"] == "UserSignup"
        assert call_args[1]["attributes"]["metric.category"] == "user"
        assert call_args[1]["attributes"]["tenant_id"] == "tenant123"

    @patch("app.core.otel_metrics._get_http_request_counter")
    @patch("app.core.otel_metrics._get_http_request_duration")
    def test_emit_http_request_metrics(self, mock_duration, mock_counter):
        """Test that HTTP request metrics are emitted correctly."""
        mock_counter_instance = MagicMock()
        mock_counter.return_value = mock_counter_instance
        mock_duration_instance = MagicMock()
        mock_duration.return_value = mock_duration_instance

        emit_http_request(
            method="GET",
            path="/api/v1/users/123",
            status_code=200,
            duration_ms=45.3,
            request_id="req123",
        )

        call_args = mock_counter_instance.add.call_args
        assert call_args[0][0] == 1
        assert call_args[1]["attributes"]["http.method"] == "GET"
        assert call_args[1]["attributes"]["http.route"] == "/api/v1/users/{id}"  # Normalized
        assert call_args[1]["attributes"]["http.status_code"] == "200"
        assert call_args[1]["attributes"]["request_id"] == "req123"

        duration_args = mock_duration_instance.record.call_args
        assert duration_args[0][0] == 45.3

    @patch("app.core.otel_metrics._get_http_request_counter")
    def test_path_normalization(self, mock_counter):
        """Test that paths are normalized to reduce cardinality."""
        mock_counter_instance = MagicMock()
        mock_counter.return_value = mock_counter_instance

        # Test UUID normalization
        emit_http_request(
            method="GET",
            path="/api/v1/users/123e4567-e89b-12d3-a456-426614174000",
            status_code=200,
            duration_ms=10.0,
        )

        call_args = mock_counter_instance.add.call_args
        # Path should be normalized
        assert call_args[1]["attributes"]["http.route"] == "/api/v1/users/{id}"

    @patch("app.core.otel_metrics.settings")
    def test_metrics_disabled_when_setting_false(self, mock_settings):
        """Test that metrics are not emitted when disabled."""
        from unittest.mock import patch

        mock_settings.enable_metrics = False

        with patch("app.core.otel_metrics._get_db_query_counter") as mock_counter:
            emit_database_query(
                operation="SELECT",
                duration_ms=10.0,
                success=True,
            )

            # Counter should not be called when metrics are disabled
            mock_counter.assert_not_called()
