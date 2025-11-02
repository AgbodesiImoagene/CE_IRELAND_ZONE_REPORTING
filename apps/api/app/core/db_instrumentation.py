"""SQLAlchemy database instrumentation using event listeners.

Provides accurate query-level timing metrics by hooking into
SQLAlchemy's event system at the engine level.
"""

from __future__ import annotations

import logging
import time
from contextvars import ContextVar
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.engine.interfaces import DBAPICursor

from app.core.metrics import emit_database_query

logger = logging.getLogger(__name__)

# Context variable to track query start times per thread/context
_query_start_times: ContextVar[dict[str, float]] = ContextVar(
    "query_start_times", default={}
)


def _get_operation_type(statement: str) -> str:
    """Extract SQL operation type from statement.

    Handles SQL comments (-- and /* */) by stripping them first.
    """
    if not statement:
        return "UNKNOWN"

    # Strip SQL comments
    import re

    # Remove single-line comments (-- ...)
    statement = re.sub(r"--.*$", "", statement, flags=re.MULTILINE)
    # Remove multi-line comments (/* ... */)
    statement = re.sub(r"/\*.*?\*/", "", statement, flags=re.DOTALL)

    # Get first non-empty line
    lines = [line.strip() for line in statement.split("\n")]
    first_line = ""
    for line in lines:
        if line and not line.startswith("--"):
            first_line = line.upper()
            break

    if not first_line:
        return "UNKNOWN"

    if first_line.startswith("SELECT"):
        return "SELECT"
    if first_line.startswith("INSERT"):
        return "INSERT"
    if first_line.startswith("UPDATE"):
        return "UPDATE"
    if first_line.startswith("DELETE"):
        return "DELETE"
    if first_line.startswith("CREATE"):
        return "CREATE"
    if first_line.startswith("DROP"):
        return "DROP"
    if first_line.startswith("ALTER"):
        return "ALTER"
    if first_line.startswith("SET"):
        return "SET"  # RLS SET LOCAL commands
    return "OTHER"


@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(
    conn,
    cursor: DBAPICursor,
    statement: str,
    parameters: tuple[Any, ...] | dict[str, Any] | None,
    context: Any,
    executemany: bool,
) -> None:
    """Record query start time before execution."""
    # Use perf_counter for higher precision timing
    start_time = time.perf_counter()

    # Store start time in context using cursor id as key
    cursor_id = id(cursor)
    start_times = _query_start_times.get({})
    start_times[str(cursor_id)] = start_time
    _query_start_times.set(start_times)

    # Also store statement and operation type for later
    if not hasattr(context, "_query_info"):
        context._query_info = {}
    context._query_info["statement"] = statement
    context._query_info["operation"] = _get_operation_type(statement)


@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(
    conn,
    cursor: DBAPICursor,
    statement: str,
    parameters: tuple[Any, ...] | dict[str, Any] | None,
    context: Any,
    executemany: bool,
) -> None:
    """Record query duration and emit metrics after execution."""
    cursor_id = str(id(cursor))
    start_times = _query_start_times.get({})
    start_time = start_times.pop(cursor_id, None)

    if start_time is None:
        # Start time not found, skip metric
        return

    # Calculate duration using perf_counter
    duration_ms = (time.perf_counter() - start_time) * 1000
    _query_start_times.set(start_times)

    # Get operation type
    operation = "UNKNOWN"
    if hasattr(context, "_query_info"):
        operation = context._query_info.get("operation", "UNKNOWN")
    else:
        operation = _get_operation_type(statement)

    # Emit metric for successful query
    try:
        emit_database_query(
            operation=operation,
            duration_ms=duration_ms,
            success=True,
        )
    except Exception as e:
        # Don't let metric emission failures break queries
        logger.warning(f"Failed to emit database metric: {e}", exc_info=True)


@event.listens_for(Engine, "handle_error")
def handle_error(exception_context: Any) -> None:
    """Handle database errors and emit error metrics."""
    # Get the exception and context
    exception = exception_context.original_exception
    if not exception:
        return

    # Try to get query info from context
    operation = "UNKNOWN"
    duration_ms = 0.0

    if hasattr(exception_context, "statement"):
        operation = _get_operation_type(exception_context.statement)

    # For errors, we don't have a good way to measure duration
    # since the error occurred during execution. We'll just emit
    # with a minimal duration.
    try:
        emit_database_query(
            operation=operation,
            duration_ms=duration_ms,
            success=False,
            error_type=type(exception).__name__,
        )
    except Exception as e:
        # Don't let metric emission failures break error handling
        logger.warning(f"Failed to emit database error metric: {e}", exc_info=True)


def setup_database_instrumentation(engine: Engine) -> None:
    """Setup database instrumentation for an engine.

    This is called automatically when the module is imported,
    but can be called explicitly if needed.

    Args:
        engine: SQLAlchemy engine to instrument
    """
    # The event listeners are registered at the module level,
    # so they'll automatically attach to all engines.
    # This function exists for explicit setup if needed.
    pass
