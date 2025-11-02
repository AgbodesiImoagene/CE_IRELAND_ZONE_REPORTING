"""Integration tests for observability instrumentation.

Tests the full flow from database/Redis operations to metrics emission.
"""

from __future__ import annotations

import json
import logging
from unittest.mock import AsyncMock, Mock

import pytest

# Import to register database event listeners
from app.core import db_instrumentation  # noqa: F401
from app.core.redis_instrumentation import InstrumentedRedis
from app.common.models import User


class TestInstrumentationIntegration:
    """Integration tests for instrumentation end-to-end."""

    def test_database_query_to_metric_flow(self, db, caplog):
        """Test complete flow: database query -> event listener -> metric."""
        from app.core.config import settings
        from uuid import uuid4, UUID
        from app.auth.utils import hash_password

        caplog.set_level(logging.INFO)
        caplog.clear()

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

        # Check that EMF metric was logged
        log_records = [record.message for record in caplog.records]
        emf_logs = [
            log for log in log_records if "_aws" in log and "DatabaseQuery" in log
        ]

        # Should have at least one database metric
        assert len(emf_logs) > 0

        # Verify EMF format
        emf_data = json.loads(emf_logs[0])
        assert "_aws" in emf_data
        assert "CloudWatchMetrics" in emf_data["_aws"]

    @pytest.mark.asyncio
    async def test_redis_operation_to_metric_flow(self, caplog):
        """Test complete flow: Redis operation -> wrapper -> metric."""
        import redis.asyncio as aioredis

        caplog.set_level(logging.INFO)
        caplog.clear()

        # Create a real Redis client and wrap it
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value="test_value")

        instrumented = InstrumentedRedis(mock_client)

        # Perform operation
        result = await instrumented.get("test_key")
        assert result == "test_value"

        # Check that EMF metric was logged
        log_records = [record.message for record in caplog.records]
        emf_logs = [
            log for log in log_records if "_aws" in log and "RedisOperation" in log
        ]

        # Should have Redis operation metric
        assert len(emf_logs) > 0

        # Verify EMF format
        emf_data = json.loads(emf_logs[0])
        assert "_aws" in emf_data
        assert "CloudWatchMetrics" in emf_data["_aws"]

    def test_metrics_emission_format_compliance(self, caplog):
        """Test that emitted metrics comply with CloudWatch EMF format."""
        from app.core.metrics import emit_database_query

        caplog.set_level(logging.INFO)
        caplog.clear()

        emit_database_query(
            operation="SELECT",
            duration_ms=15.5,
            success=True,
        )

        log_records = [record.message for record in caplog.records]
        emf_logs = [log for log in log_records if "_aws" in log]

        assert len(emf_logs) > 0
        emf_data = json.loads(emf_logs[0])

        # Verify required EMF fields
        assert "_aws" in emf_data
        assert "CloudWatchMetrics" in emf_data["_aws"]
        assert isinstance(emf_data["_aws"]["CloudWatchMetrics"], list)
        assert len(emf_data["_aws"]["CloudWatchMetrics"]) > 0

        cloudwatch_metrics = emf_data["_aws"]["CloudWatchMetrics"][0]
        assert "Namespace" in cloudwatch_metrics
        assert "Metrics" in cloudwatch_metrics
        assert isinstance(cloudwatch_metrics["Metrics"], list)
        assert "Timestamp" in emf_data["_aws"]

        # Verify metric values are present
        assert "DatabaseQueryCount" in emf_data
        assert "DatabaseQueryDuration" in emf_data

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

    def test_metrics_namespace_configuration(self, caplog):
        """Test that metrics use correct namespace."""
        from app.core.config import settings
        from app.core.metrics import emit_database_query

        caplog.set_level(logging.INFO)
        caplog.clear()

        emit_database_query(
            operation="SELECT",
            duration_ms=10.0,
            success=True,
        )

        log_records = [record.message for record in caplog.records]
        emf_logs = [log for log in log_records if "_aws" in log]

        assert len(emf_logs) > 0
        emf_data = json.loads(emf_logs[0])

        namespace = emf_data["_aws"]["CloudWatchMetrics"][0]["Namespace"]
        # Should use tenant_name or metrics_namespace if set
        assert len(namespace) > 0

    @pytest.mark.asyncio
    async def test_redis_pipeline_full_flow(self, caplog):
        """Test complete Redis pipeline instrumentation flow."""
        caplog.set_level(logging.INFO)
        caplog.clear()

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

        # Check that pipeline metric was logged
        log_records = [record.message for record in caplog.records]
        emf_logs = [log for log in log_records if "_aws" in log and "PIPELINE" in log]

        assert len(emf_logs) > 0
        emf_data = json.loads(emf_logs[0])
        assert "RedisOperationDuration" in emf_data
