"""Integration tests for observability instrumentation.

Tests the full flow from database/Redis operations to metrics emission.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

# Import to register database event listeners
from app.core import db_instrumentation  # noqa: F401
from app.core.redis_instrumentation import InstrumentedRedis
from app.common.models import User


class TestInstrumentationIntegration:
    """Integration tests for instrumentation end-to-end."""

    @patch("app.core.db_instrumentation.emit_database_query")
    def test_database_query_to_metric_flow(self, mock_emit, db):
        """Test complete flow: database query -> event listener -> metric."""
        from app.core.config import settings
        from uuid import uuid4, UUID
        from app.auth.utils import hash_password

        # Create a user (triggers INSERT)
        user = User(
            id=uuid4(),
            tenant_id=UUID(settings.tenant_id),
            email="integration@test.com",
            password_hash=hash_password("password"),
            is_active=True,
        )
        db.add(user)
        db.commit()

        # Should have at least one database metric call
        assert mock_emit.called
        # Check that it was called with correct operation type
        call_args = mock_emit.call_args_list
        assert any(
            call[1]["operation"] == "INSERT" for call in call_args
        )

    @pytest.mark.asyncio
    @patch("app.core.redis_instrumentation.emit_redis_operation")
    async def test_redis_operation_to_metric_flow(self, mock_emit):
        """Test complete flow: Redis operation -> wrapper -> metric."""
        # Create a real Redis client and wrap it
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value="test_value")

        instrumented = InstrumentedRedis(mock_client)

        # Perform operation
        result = await instrumented.get("test_key")
        assert result == "test_value"

        # Should have Redis operation metric call
        assert mock_emit.called
        call_args = mock_emit.call_args
        assert call_args[1]["operation"] == "GET"
        assert call_args[1]["success"] is True

    @patch("app.core.otel_metrics._get_db_query_counter")
    @patch("app.core.otel_metrics._get_db_query_duration")
    def test_metrics_emission_format_compliance(self, mock_duration, mock_counter):
        """Test that emitted metrics use OpenTelemetry format."""
        from app.core.otel_metrics import emit_database_query

        mock_counter_instance = Mock()
        mock_counter.return_value = mock_counter_instance
        mock_duration_instance = Mock()
        mock_duration.return_value = mock_duration_instance

        emit_database_query(
            operation="SELECT",
            duration_ms=15.5,
            success=True,
        )

        # Verify counter was called with correct attributes
        assert mock_counter_instance.add.called
        call_args = mock_counter_instance.add.call_args
        assert call_args[0][0] == 1  # Count
        assert "attributes" in call_args[1]
        assert call_args[1]["attributes"]["db.operation"] == "SELECT"
        assert call_args[1]["attributes"]["db.success"] == "true"

        # Verify duration histogram was called
        assert mock_duration_instance.record.called
        duration_args = mock_duration_instance.record.call_args
        assert duration_args[0][0] == 15.5

    def test_operation_type_extraction(self):
        """Test that operation types are correctly extracted from SQL."""
        from app.core.db_instrumentation import _get_operation_type

        test_cases = [
            ("SELECT * FROM users", "SELECT"),
            ("INSERT INTO users VALUES (...)", "INSERT"),
            ("UPDATE users SET name = 'test'", "UPDATE"),
            ("DELETE FROM users WHERE id = 1", "DELETE"),
            ("SET LOCAL app.tenant_id = '123'", "SET"),
            ("CREATE TABLE users (...)", "CREATE"),
            ("DROP TABLE users", "DROP"),
            ("ALTER TABLE users ADD COLUMN ...", "ALTER"),
            ("-- Comment\nSELECT ...", "SELECT"),  # Single-line comment
            ("/* Comment */\nSELECT ...", "SELECT"),  # Multi-line comment
            ("select * from users", "SELECT"),  # Case insensitive
        ]

        for sql, expected_op in test_cases:
            assert _get_operation_type(sql) == expected_op, f"Failed for: {sql}"

    @patch("opentelemetry.metrics.get_meter_provider")
    def test_metrics_namespace_configuration(self, mock_get_meter_provider):
        """Test that metrics use correct namespace."""
        from app.core.config import settings
        from app.core.otel_metrics import emit_database_query

        # Reset the global meter and counters to force recreation
        from app.core import otel_metrics
        otel_metrics._meter = None
        otel_metrics._db_query_counter = None
        otel_metrics._db_query_duration = None

        # Create a mock meter provider and meter
        mock_meter_provider = Mock()
        mock_meter = Mock()
        mock_counter = Mock()
        mock_histogram = Mock()
        mock_meter.create_counter.return_value = mock_counter
        mock_meter.create_histogram.return_value = mock_histogram
        mock_meter_provider.get_meter.return_value = mock_meter
        mock_get_meter_provider.return_value = mock_meter_provider

        emit_database_query(
            operation="SELECT",
            duration_ms=10.0,
            success=True,
        )

        # Verify meter provider was used to create meter with correct name
        assert mock_meter_provider.get_meter.called
        call_args = mock_meter_provider.get_meter.call_args
        expected_name = (
            settings.metrics_namespace
            or settings.tenant_name.replace(" ", "/")
        )
        # Verify the meter was created with the correct namespace
        assert call_args.kwargs["name"] == expected_name
        assert call_args.kwargs["version"] == "1.0.0"

    @pytest.mark.asyncio
    @patch("app.core.redis_instrumentation.emit_redis_operation")
    async def test_redis_pipeline_full_flow(self, mock_emit):
        """Test complete Redis pipeline instrumentation flow."""
        # Create mock pipeline
        mock_client = AsyncMock()
        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value=[0, 5, 1, 1])
        mock_pipeline.zadd = Mock(return_value=mock_pipeline)
        mock_pipeline.zcard = Mock(return_value=mock_pipeline)
        mock_pipeline.zremrangebyscore = Mock(return_value=mock_pipeline)
        mock_pipeline.expire = Mock(return_value=mock_pipeline)
        mock_client.pipeline = Mock(return_value=mock_pipeline)

        instrumented = InstrumentedRedis(mock_client)

        # Execute pipeline
        pipe = instrumented.pipeline()
        pipe.zremrangebyscore("key", 0, 100)
        pipe.zcard("key")
        pipe.zadd("key", {"val": 1.0})
        pipe.expire("key", 60)
        result = await pipe.execute()

        assert result == [0, 5, 1, 1]

        # Should have pipeline metric call
        assert mock_emit.called
        # Check that it was called with PIPELINE operation
        call_args_list = mock_emit.call_args_list
        assert any(
            call[1]["operation"] == "PIPELINE" for call in call_args_list
        )
