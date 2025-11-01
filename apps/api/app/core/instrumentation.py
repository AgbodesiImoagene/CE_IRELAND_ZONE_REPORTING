"""Instrumentation decorators for automatic metrics and logging.

NOTE: These decorators are now OPTIONAL. Database and Redis operations
are automatically instrumented at the SQLAlchemy engine level and Redis
client level respectively (see db_instrumentation.py and redis_instrumentation.py).

These decorators are kept for backward compatibility and can be used
for function-level timing if needed (includes business logic, not just DB/Redis ops).
"""

from __future__ import annotations

import functools
import logging
import time
from typing import Any, Callable, TypeVar

from app.core.metrics import emit_database_query, emit_redis_operation

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def instrument_database_operation(
    operation: str | None = None,
    log_query: bool = False,
):
    """Decorator to instrument database operations with metrics and logging.

    Args:
        operation: Operation type (e.g., "SELECT", "INSERT"). If None, inferred
            from function name.
        log_query: Whether to log the query details (default: False)

    Example:
        @instrument_database_operation(operation="SELECT")
        def get_user(db: Session, user_id: UUID):
            return db.query(User).filter(User.id == user_id).first()
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            op = operation or func.__name__.upper()
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                success = True
                duration_ms = (time.time() - start_time) * 1000

                # Emit metrics
                emit_database_query(
                    operation=op,
                    duration_ms=duration_ms,
                    success=True,
                    function=func.__name__,
                )

                if log_query:
                    logger.debug(
                        f"Database {op} operation completed",
                        extra={
                            "operation": op,
                            "duration_ms": round(duration_ms, 2),
                            "function": func.__name__,
                            "success": True,
                        },
                    )

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                success = False

                # Emit error metrics
                emit_database_query(
                    operation=op,
                    duration_ms=duration_ms,
                    success=False,
                    function=func.__name__,
                )

                logger.error(
                    f"Database {op} operation failed: {str(e)}",
                    extra={
                        "operation": op,
                        "duration_ms": round(duration_ms, 2),
                        "function": func.__name__,
                        "success": False,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )

                raise

        return wrapper  # type: ignore[return-value]

    return decorator


def instrument_redis_operation(
    operation: str | None = None,
    log_operation: bool = False,
):
    """Decorator to instrument Redis operations with metrics and logging.

    Args:
        operation: Operation type (e.g., "GET", "SET"). If None, inferred
            from function name.
        log_operation: Whether to log the operation details (default: False)

    Example:
        @instrument_redis_operation(operation="GET")
        async def get_cached_value(key: str):
            return await redis.get(key)
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            op = operation or func.__name__.upper()
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                success = True
                duration_ms = (time.time() - start_time) * 1000

                # Emit metrics
                emit_redis_operation(
                    operation=op,
                    duration_ms=duration_ms,
                    success=True,
                    function=func.__name__,
                )

                if log_operation:
                    logger.debug(
                        f"Redis {op} operation completed",
                        extra={
                            "operation": op,
                            "duration_ms": round(duration_ms, 2),
                            "function": func.__name__,
                            "success": True,
                        },
                    )

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                success = False

                # Emit error metrics
                emit_redis_operation(
                    operation=op,
                    duration_ms=duration_ms,
                    success=False,
                    function=func.__name__,
                )

                logger.error(
                    f"Redis {op} operation failed: {str(e)}",
                    extra={
                        "operation": op,
                        "duration_ms": round(duration_ms, 2),
                        "function": func.__name__,
                        "success": False,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )

                raise

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            op = operation or func.__name__.upper()
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                success = True
                duration_ms = (time.time() - start_time) * 1000

                # Emit metrics
                emit_redis_operation(
                    operation=op,
                    duration_ms=duration_ms,
                    success=True,
                    function=func.__name__,
                )

                if log_operation:
                    logger.debug(
                        f"Redis {op} operation completed",
                        extra={
                            "operation": op,
                            "duration_ms": round(duration_ms, 2),
                            "function": func.__name__,
                            "success": True,
                        },
                    )

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                success = False

                # Emit error metrics
                emit_redis_operation(
                    operation=op,
                    duration_ms=duration_ms,
                    success=False,
                    function=func.__name__,
                )

                logger.error(
                    f"Redis {op} operation failed: {str(e)}",
                    extra={
                        "operation": op,
                        "duration_ms": round(duration_ms, 2),
                        "function": func.__name__,
                        "success": False,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )

                raise

        # Check if function is async
        import inspect

        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    return decorator


def log_execution(
    log_args: bool = False,
    log_result: bool = False,
    level: int = logging.DEBUG,
):
    """Decorator to log function execution with arguments and results.

    Args:
        log_args: Whether to log function arguments
        log_result: Whether to log function results
        level: Logging level (default: DEBUG)

    Example:
        @log_execution(log_args=True, log_result=False)
        def process_data(data: dict):
            return transform(data)
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            func_name = func.__name__
            start_time = time.time()

            if log_args:
                logger.log(
                    level,
                    f"Executing {func_name}",
                    extra={
                        "function": func_name,
                        "args": str(args) if args else None,
                        "kwargs": (
                            {k: str(v) for k, v in kwargs.items()}
                            if kwargs
                            else None
                        ),
                    },
                )
            else:
                logger.log(level, f"Executing {func_name}")

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                if log_result:
                    logger.log(
                        level,
                        f"{func_name} completed",
                        extra={
                            "function": func_name,
                            "duration_ms": round(duration_ms, 2),
                            "result": str(result)[:1000],  # Limit result size
                        },
                    )
                else:
                    logger.log(
                        level,
                        f"{func_name} completed in {duration_ms:.2f}ms",
                    )

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000

                logger.error(
                    f"{func_name} failed after {duration_ms:.2f}ms",
                    extra={
                        "function": func_name,
                        "duration_ms": round(duration_ms, 2),
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )

                raise

        return wrapper  # type: ignore[return-value]

    return decorator

