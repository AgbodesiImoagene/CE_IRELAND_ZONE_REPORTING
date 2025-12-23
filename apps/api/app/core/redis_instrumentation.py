"""Redis client instrumentation wrapper.

Provides automatic metrics for Redis operations by wrapping the client.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.core.otel_metrics import emit_redis_operation

logger = logging.getLogger(__name__)


class InstrumentedRedis:
    """Wrapper around Redis client that adds automatic instrumentation."""

    def __init__(self, redis_client: Any):
        """Initialize with a Redis client.

        Args:
            redis_client: Underlying Redis client (sync or async)
        """
        self._client = redis_client
        self._is_async = hasattr(redis_client, "__aenter__")

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to underlying client."""
        # For methods we've explicitly defined, don't go through __getattr__
        # Use object.__getattribute__ to avoid recursion
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            pass

        # Get attribute from underlying client
        attr = getattr(self._client, name)

        # If it's a Redis command method, wrap it
        if callable(attr) and name.upper() in [
            "GET",
            "SET",
            "SETEX",
            "DELETE",
            "EXISTS",
            "ZADD",
            "ZCARD",
            "ZRANGE",
            "ZREMRANGEBYSCORE",
            "EXPIRE",
            "PIPELINE",
        ]:
            return self._wrap_method(name, attr)

        return attr

    def _wrap_method(self, operation: str, method: Any) -> Any:
        """Wrap a Redis method with instrumentation."""
        # Check if method is async by inspecting it
        import inspect

        if inspect.iscoroutinefunction(method):
            return self._wrap_async_method(operation, method)
        return self._wrap_sync_method(operation, method)

    def _wrap_async_method(self, operation: str, method: Any) -> Any:
        """Wrap an async Redis method."""

        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.perf_counter()
            try:
                result = await method(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000

                # Emit success metric
                emit_redis_operation(
                    operation=operation.upper(),
                    duration_ms=duration_ms,
                    success=True,
                )

                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000

                # Emit error metric
                emit_redis_operation(
                    operation=operation.upper(),
                    duration_ms=duration_ms,
                    success=False,
                    error_type=type(e).__name__,
                )

                logger.error(
                    f"Redis {operation} operation failed: {str(e)}",
                    extra={
                        "operation": operation.upper(),
                        "duration_ms": round(duration_ms, 2),
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )
                raise

        return wrapper

    def _wrap_sync_method(self, operation: str, method: Any) -> Any:
        """Wrap a sync Redis method."""

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.perf_counter()
            try:
                result = method(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000

                # Emit success metric
                emit_redis_operation(
                    operation=operation.upper(),
                    duration_ms=duration_ms,
                    success=True,
                )

                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000

                # Emit error metric
                emit_redis_operation(
                    operation=operation.upper(),
                    duration_ms=duration_ms,
                    success=False,
                    error_type=type(e).__name__,
                )

                logger.error(
                    f"Redis {operation} operation failed: {str(e)}",
                    extra={
                        "operation": operation.upper(),
                        "duration_ms": round(duration_ms, 2),
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )
                raise

        return wrapper

    # Redis commands are handled via __getattr__ wrapping

    def pipeline(self) -> Any:
        """Create a pipeline. Pipeline execution will be instrumented separately."""
        # Pipeline returns a pipeline object, which we should also wrap
        pipeline = self._client.pipeline()
        return InstrumentedRedisPipeline(pipeline)

    async def aclose(self) -> None:
        """Close async Redis client."""
        if hasattr(self._client, "aclose"):
            await self._client.aclose()

    def close(self) -> None:
        """Close sync Redis client."""
        if hasattr(self._client, "close"):
            self._client.close()


class InstrumentedRedisPipeline:
    """Wrapper for Redis pipeline with instrumentation."""

    def __init__(self, pipeline: Any):
        """Initialize with a Redis pipeline.

        Args:
            pipeline: Underlying Redis pipeline
        """
        self._pipeline = pipeline
        import inspect

        execute_method = getattr(pipeline, "execute", None)
        self._is_async = execute_method is not None and inspect.iscoroutinefunction(
            execute_method
        )

    def __getattr__(self, name: str) -> Any:
        """Delegate to underlying pipeline."""
        return getattr(self._pipeline, name)

    async def execute_async(self) -> list[Any]:
        """Execute async pipeline with instrumentation."""
        start_time = time.perf_counter()
        try:
            result = await self._pipeline.execute()
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Emit metric for pipeline execution
            emit_redis_operation(
                operation="PIPELINE",
                duration_ms=duration_ms,
                success=True,
            )

            return result
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000

            emit_redis_operation(
                operation="PIPELINE",
                duration_ms=duration_ms,
                success=False,
                error_type=type(e).__name__,
            )

            logger.error(
                f"Redis pipeline execution failed: {str(e)}",
                extra={
                    "operation": "PIPELINE",
                    "duration_ms": round(duration_ms, 2),
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise

    def execute_sync(self) -> list[Any]:
        """Execute sync pipeline with instrumentation."""
        start_time = time.perf_counter()
        try:
            result = self._pipeline.execute()
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Emit metric for pipeline execution
            emit_redis_operation(
                operation="PIPELINE",
                duration_ms=duration_ms,
                success=True,
            )

            return result
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000

            emit_redis_operation(
                operation="PIPELINE",
                duration_ms=duration_ms,
                success=False,
                error_type=type(e).__name__,
            )

            logger.error(
                f"Redis pipeline execution failed: {str(e)}",
                extra={
                    "operation": "PIPELINE",
                    "duration_ms": round(duration_ms, 2),
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise

    def __getattribute__(self, name: str) -> Any:
        """Override to intercept execute() calls."""
        if name == "execute":
            # Return appropriate execute method based on pipeline type
            if self._is_async:
                return self.execute_async
            return self.execute_sync
        return super().__getattribute__(name)
