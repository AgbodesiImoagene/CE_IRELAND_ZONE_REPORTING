"""Tests for Redis client instrumentation."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.core.redis_instrumentation import (
    InstrumentedRedis,
    InstrumentedRedisPipeline,
)


class TestInstrumentedRedis:
    """Test Redis client instrumentation wrapper."""

    @pytest.mark.asyncio
    async def test_get_operation_instrumented(self):
        """Test that GET operations are instrumented."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value="test_value")

        instrumented = InstrumentedRedis(mock_client)

        with patch("app.core.redis_instrumentation.emit_redis_operation") as mock_emit:
            result = await instrumented.get("test_key")

            assert result == "test_value"
            assert mock_emit.called
            call_args = mock_emit.call_args
            assert call_args[1]["operation"] == "GET"
            assert call_args[1]["success"] is True
            assert "duration_ms" in call_args[1]

    @pytest.mark.asyncio
    async def test_set_operation_instrumented(self):
        """Test that SET operations are instrumented."""
        mock_client = AsyncMock()
        mock_client.set = AsyncMock(return_value=True)

        instrumented = InstrumentedRedis(mock_client)

        with patch("app.core.redis_instrumentation.emit_redis_operation") as mock_emit:
            result = await instrumented.set("test_key", "test_value")

            assert result is True
            assert mock_emit.called
            call_args = mock_emit.call_args
            assert call_args[1]["operation"] == "SET"
            assert call_args[1]["success"] is True

    @pytest.mark.asyncio
    async def test_setex_operation_instrumented(self):
        """Test that SETEX operations are instrumented."""
        mock_client = AsyncMock()
        mock_client.setex = AsyncMock(return_value=True)

        instrumented = InstrumentedRedis(mock_client)

        with patch("app.core.redis_instrumentation.emit_redis_operation") as mock_emit:
            result = await instrumented.setex("test_key", 60, "test_value")

            assert result is True
            assert mock_emit.called
            call_args = mock_emit.call_args
            assert call_args[1]["operation"] == "SETEX"
            assert call_args[1]["success"] is True

    @pytest.mark.asyncio
    async def test_delete_operation_instrumented(self):
        """Test that DELETE operations are instrumented."""
        mock_client = AsyncMock()
        mock_client.delete = AsyncMock(return_value=1)

        instrumented = InstrumentedRedis(mock_client)

        with patch("app.core.redis_instrumentation.emit_redis_operation") as mock_emit:
            result = await instrumented.delete("test_key")

            assert result == 1
            assert mock_emit.called
            call_args = mock_emit.call_args
            assert call_args[1]["operation"] == "DELETE"
            assert call_args[1]["success"] is True

    @pytest.mark.asyncio
    async def test_exists_operation_instrumented(self):
        """Test that EXISTS operations are instrumented."""
        mock_client = AsyncMock()
        mock_client.exists = AsyncMock(return_value=1)

        instrumented = InstrumentedRedis(mock_client)

        with patch("app.core.redis_instrumentation.emit_redis_operation") as mock_emit:
            result = await instrumented.exists("test_key")

            assert result == 1
            assert mock_emit.called
            call_args = mock_emit.call_args
            assert call_args[1]["operation"] == "EXISTS"
            assert call_args[1]["success"] is True

    @pytest.mark.asyncio
    async def test_operation_duration_captured(self):
        """Test that operation duration is accurately measured."""
        import time

        mock_client = AsyncMock()

        async def slow_get(key: str):
            await asyncio.sleep(0.01)  # 10ms delay
            return "value"

        mock_client.get = slow_get

        instrumented = InstrumentedRedis(mock_client)

        with patch("app.core.redis_instrumentation.emit_redis_operation") as mock_emit:
            await instrumented.get("test_key")

            call_args = mock_emit.call_args
            duration_ms = call_args[1]["duration_ms"]
            assert duration_ms >= 10  # Should be at least 10ms
            assert isinstance(duration_ms, (int, float))

    @pytest.mark.asyncio
    async def test_error_emits_error_metric(self):
        """Test that errors emit error metrics."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=ConnectionError("Redis error"))

        instrumented = InstrumentedRedis(mock_client)

        with patch("app.core.redis_instrumentation.emit_redis_operation") as mock_emit:
            with pytest.raises(ConnectionError):
                await instrumented.get("test_key")

            assert mock_emit.called
            call_args = mock_emit.call_args
            assert call_args[1]["operation"] == "GET"
            assert call_args[1]["success"] is False
            assert "error_type" in call_args[1]

    @pytest.mark.asyncio
    async def test_pipeline_instrumented(self):
        """Test that pipeline execution is instrumented."""
        mock_client = AsyncMock()
        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value=[1, 2, 3])
        mock_pipeline.zadd = Mock(return_value=mock_pipeline)
        mock_pipeline.zcard = Mock(return_value=mock_pipeline)
        mock_pipeline.expire = Mock(return_value=mock_pipeline)
        mock_client.pipeline = Mock(return_value=mock_pipeline)

        instrumented = InstrumentedRedis(mock_client)

        with patch("app.core.redis_instrumentation.emit_redis_operation") as mock_emit:
            pipe = instrumented.pipeline()
            pipe.zadd("key", {"val": 1.0})
            pipe.zcard("key")
            pipe.expire("key", 60)
            result = await pipe.execute()

            assert result == [1, 2, 3]
            # Should emit PIPELINE metric
            pipeline_calls = [
                call
                for call in mock_emit.call_args_list
                if call[1].get("operation") == "PIPELINE"
            ]
            assert len(pipeline_calls) > 0

    @pytest.mark.asyncio
    async def test_instrumentation_uses_perf_counter(self):
        """Test that timing uses perf_counter for accuracy."""
        import time

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value="value")

        instrumented = InstrumentedRedis(mock_client)

        with patch("time.perf_counter") as mock_perf:
            mock_perf.side_effect = [1000.0, 1000.05]  # 0.05 seconds

            with patch(
                "app.core.redis_instrumentation.emit_redis_operation"
            ) as mock_emit:
                await instrumented.get("test_key")

                assert mock_perf.called
                call_args = mock_emit.call_args
                duration_ms = call_args[1]["duration_ms"]
                assert abs(duration_ms - 50.0) < 1.0  # 50ms

    def test_sync_redis_client_supported(self):
        """Test that sync Redis clients are supported."""
        import redis

        mock_client = Mock()
        mock_client.get = Mock(return_value="value")
        mock_client.__aenter__ = None  # No async context manager

        instrumented = InstrumentedRedis(mock_client)

        with patch("app.core.redis_instrumentation.emit_redis_operation") as mock_emit:
            result = instrumented.get("test_key")

            assert result == "value"
            assert mock_emit.called
            call_args = mock_emit.call_args
            assert call_args[1]["operation"] == "GET"
            assert call_args[1]["success"] is True

    @pytest.mark.asyncio
    async def test_aclose_delegates(self):
        """Test that aclose is properly delegated."""
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()

        instrumented = InstrumentedRedis(mock_client)
        await instrumented.aclose()

        mock_client.aclose.assert_called_once()

    def test_close_delegates(self):
        """Test that close is properly delegated."""
        mock_client = Mock()
        mock_client.close = Mock()

        instrumented = InstrumentedRedis(mock_client)
        instrumented.close()

        mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_zadd_zcard_zrange_instrumented(self):
        """Test that sorted set operations are instrumented."""
        mock_client = AsyncMock()
        mock_client.zadd = AsyncMock(return_value=1)
        mock_client.zcard = AsyncMock(return_value=5)
        mock_client.zrange = AsyncMock(return_value=[("item1", 1.0)])

        instrumented = InstrumentedRedis(mock_client)

        with patch("app.core.redis_instrumentation.emit_redis_operation") as mock_emit:
            await instrumented.zadd("key", {"item": 1.0})
            await instrumented.zcard("key")
            await instrumented.zrange("key", 0, -1)

            # Verify all operations were instrumented
            assert mock_emit.call_count == 3
            operations = [call[1]["operation"] for call in mock_emit.call_args_list]
            assert "ZADD" in operations
            assert "ZCARD" in operations
            assert "ZRANGE" in operations


class TestInstrumentedRedisPipeline:
    """Test Redis pipeline instrumentation."""

    @pytest.mark.asyncio
    async def test_async_pipeline_execution_instrumented(self):
        """Test that async pipeline execution is instrumented."""
        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value=[1, 2, 3])

        instrumented = InstrumentedRedisPipeline(mock_pipeline)

        with patch("app.core.redis_instrumentation.emit_redis_operation") as mock_emit:
            result = await instrumented.execute()

            assert result == [1, 2, 3]
            assert mock_emit.called
            call_args = mock_emit.call_args
            assert call_args[1]["operation"] == "PIPELINE"
            assert call_args[1]["success"] is True

    def test_sync_pipeline_execution_instrumented(self):
        """Test that sync pipeline execution is instrumented."""
        mock_pipeline = Mock()
        mock_pipeline.execute = Mock(return_value=[1, 2, 3])

        # Make execute not async
        import inspect

        original_execute = mock_pipeline.execute
        mock_pipeline.execute = lambda: [1, 2, 3]

        instrumented = InstrumentedRedisPipeline(mock_pipeline)

        with patch("app.core.redis_instrumentation.emit_redis_operation") as mock_emit:
            result = instrumented.execute()

            assert result == [1, 2, 3]
            assert mock_emit.called
            call_args = mock_emit.call_args
            assert call_args[1]["operation"] == "PIPELINE"
            assert call_args[1]["success"] is True

    @pytest.mark.asyncio
    async def test_pipeline_error_instrumented(self):
        """Test that pipeline errors emit error metrics."""
        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(side_effect=ConnectionError("Redis error"))

        instrumented = InstrumentedRedisPipeline(mock_pipeline)

        with patch("app.core.redis_instrumentation.emit_redis_operation") as mock_emit:
            with pytest.raises(ConnectionError):
                await instrumented.execute()

            assert mock_emit.called
            call_args = mock_emit.call_args
            assert call_args[1]["operation"] == "PIPELINE"
            assert call_args[1]["success"] is False
