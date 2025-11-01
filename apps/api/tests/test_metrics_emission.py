"""Tests for metrics emission functionality."""

from __future__ import annotations

import json
import logging

from app.core.metrics import (
    emit_business_metric,
    emit_database_query,
    emit_error,
    emit_http_request,
    emit_redis_operation,
)


class TestMetricsEmission:
    """Test metrics emission functions."""

    def test_emit_database_query_success(self, caplog):
        """Test that database query metrics are emitted correctly."""
        caplog.set_level(logging.INFO)
        
        emit_database_query(
            operation="SELECT",
            duration_ms=25.5,
            success=True,
            table="users",
        )
        
        # Check that EMF log was emitted
        log_records = [record.message for record in caplog.records]
        emf_logs = [log for log in log_records if "_aws" in log]
        
        assert len(emf_logs) > 0
        emf_data = json.loads(emf_logs[0])
        
        assert "_aws" in emf_data
        assert "DatabaseQueryCount" in emf_data
        assert "DatabaseQueryDuration" in emf_data
        assert emf_data["DatabaseQueryDuration"] == 25.5

    def test_emit_database_query_error(self, caplog):
        """Test that database query errors emit error metrics."""
        caplog.set_level(logging.INFO)
        
        emit_database_query(
            operation="SELECT",
            duration_ms=10.0,
            success=False,
            error_type="ConnectionError",
        )
        
        log_records = [record.message for record in caplog.records]
        emf_logs = [log for log in log_records if "_aws" in log]
        
        assert len(emf_logs) > 0
        emf_data = json.loads(emf_logs[0])
        
        assert emf_data["Success"] == "false"

    def test_emit_redis_operation_success(self, caplog):
        """Test that Redis operation metrics are emitted correctly."""
        caplog.set_level(logging.INFO)
        
        emit_redis_operation(
            operation="GET",
            duration_ms=5.2,
            success=True,
            key="test_key",
        )
        
        log_records = [record.message for record in caplog.records]
        emf_logs = [log for log in log_records if "_aws" in log]
        
        assert len(emf_logs) > 0
        emf_data = json.loads(emf_logs[0])
        
        assert "RedisOperationCount" in emf_data
        assert "RedisOperationDuration" in emf_data
        assert emf_data["RedisOperationDuration"] == 5.2
        assert emf_data["Operation"] == "GET"

    def test_emit_error_metric(self, caplog):
        """Test that error metrics are emitted correctly."""
        caplog.set_level(logging.INFO)
        
        emit_error(
            error_code="validation_error",
            status_code=422,
            path="/api/v1/users",
            method="POST",
            user_id="user123",
        )
        
        log_records = [record.message for record in caplog.records]
        emf_logs = [log for log in log_records if "_aws" in log]
        
        assert len(emf_logs) > 0
        emf_data = json.loads(emf_logs[0])
        
        assert "ErrorCount" in emf_data
        assert emf_data["ErrorCode"] == "validation_error"
        assert emf_data["StatusCode"] == "422"
        assert emf_data["Severity"] == "client_error"

    def test_emit_error_server_error_severity(self, caplog):
        """Test that 500+ errors have server_error severity."""
        caplog.set_level(logging.INFO)
        
        emit_error(
            error_code="internal_error",
            status_code=500,
            path="/api/v1/users",
            method="GET",
        )
        
        log_records = [record.message for record in caplog.records]
        emf_logs = [log for log in log_records if "_aws" in log]
        
        assert len(emf_logs) > 0
        emf_data = json.loads(emf_logs[0])
        
        assert emf_data["Severity"] == "server_error"

    def test_emit_business_metric(self, caplog):
        """Test that business metrics are emitted correctly."""
        caplog.set_level(logging.INFO)
        
        emit_business_metric(
            metric_name="UserSignup",
            value=1,
            category="user",
            tenant_id="tenant123",
        )
        
        log_records = [record.message for record in caplog.records]
        emf_logs = [log for log in log_records if "_aws" in log]
        
        assert len(emf_logs) > 0
        emf_data = json.loads(emf_logs[0])
        
        assert "UserSignup" in emf_data
        assert emf_data["UserSignup"] == 1
        assert emf_data["Category"] == "user"

    def test_emit_http_request_metrics(self, caplog):
        """Test that HTTP request metrics are emitted correctly."""
        caplog.set_level(logging.INFO)
        
        emit_http_request(
            method="GET",
            path="/api/v1/users/123",
            status_code=200,
            duration_ms=45.3,
            request_id="req123",
        )
        
        log_records = [record.message for record in caplog.records]
        emf_logs = [log for log in log_records if "_aws" in log]
        
        assert len(emf_logs) > 0
        emf_data = json.loads(emf_logs[0])
        
        assert "RequestCount" in emf_data
        assert "RequestDuration" in emf_data
        assert emf_data["RequestDuration"] == 45.3
        assert emf_data["Method"] == "GET"
        assert emf_data["Path"] == "/api/v1/users/{id}"  # Normalized

    def test_path_normalization(self, caplog):
        """Test that paths are normalized to reduce cardinality."""
        caplog.set_level(logging.INFO)
        
        # Test UUID normalization
        emit_http_request(
            method="GET",
            path="/api/v1/users/123e4567-e89b-12d3-a456-426614174000",
            status_code=200,
            duration_ms=10.0,
        )
        
        log_records = [record.message for record in caplog.records]
        emf_logs = [log for log in log_records if "_aws" in log]
        
        assert len(emf_logs) > 0
        emf_data = json.loads(emf_logs[0])
        
        # Path should be normalized
        assert emf_data["Path"] == "/api/v1/users/{id}"
        # But original path should be in metadata
        assert "request_path" in emf_data
        assert "123e4567-e89b-12d3-a456-426614174000" in emf_data["request_path"]

    def test_metrics_disabled_when_setting_false(self, caplog):
        """Test that metrics are not emitted when disabled."""
        from app.core.config import settings
        from app.core.metrics import _emf_metrics
        
        original_setting = settings.enable_metrics
        original_metrics = _emf_metrics
        
        # Reset the global singleton to ensure fresh instance
        import app.core.metrics as metrics_module
        metrics_module._emf_metrics = None
        
        try:
            settings.enable_metrics = False
            
            caplog.set_level(logging.INFO)
            caplog.clear()
            
            emit_database_query(
                operation="SELECT",
                duration_ms=10.0,
                success=True,
            )
            
            # Should not emit any EMF logs
            log_records = [record.message for record in caplog.records]
            emf_logs = [log for log in log_records if "_aws" in log]
            assert len(emf_logs) == 0
        finally:
            settings.enable_metrics = original_setting
            metrics_module._emf_metrics = original_metrics

    def test_emf_format_structure(self, caplog):
        """Test that EMF format has correct structure."""
        caplog.set_level(logging.INFO)
        
        emit_database_query(
            operation="SELECT",
            duration_ms=20.0,
            success=True,
        )
        
        log_records = [record.message for record in caplog.records]
        emf_logs = [log for log in log_records if "_aws" in log]
        
        assert len(emf_logs) > 0
        emf_data = json.loads(emf_logs[0])
        
        # Verify EMF structure
        assert "_aws" in emf_data
        assert "CloudWatchMetrics" in emf_data["_aws"]
        assert "Namespace" in emf_data["_aws"]["CloudWatchMetrics"][0]
        assert "Metrics" in emf_data["_aws"]["CloudWatchMetrics"][0]
        assert "Timestamp" in emf_data["_aws"]

