"""OpenTelemetry metrics implementation.

This module provides OpenTelemetry-based metrics emission, replacing
the previous CloudWatch EMF format. OpenTelemetry is an open standard
that supports multiple backends (Prometheus, CloudWatch, Datadog, etc.).
"""

from __future__ import annotations

import logging
from typing import Any

from opentelemetry import metrics
from opentelemetry.metrics import Counter, Histogram, UpDownCounter, Meter

from app.core.config import settings

logger = logging.getLogger(__name__)

# Global meter instance
_meter: Meter | None = None


def get_meter() -> Meter:
    """Get or create the global OpenTelemetry meter instance."""
    global _meter
    if _meter is None:
        meter_provider = metrics.get_meter_provider()
        _meter = meter_provider.get_meter(
            name=settings.metrics_namespace or settings.tenant_name.replace(" ", "/"),
            version="1.0.0",
        )
    return _meter


# Metric instruments (lazy initialization)
_http_request_counter: Counter | None = None
_http_request_duration: Histogram | None = None
_active_requests_gauge: UpDownCounter | None = None
_db_query_counter: Counter | None = None
_db_query_duration: Histogram | None = None
_redis_operation_counter: Counter | None = None
_redis_operation_duration: Histogram | None = None
_error_counter: Counter | None = None
_business_metric_counter: Counter | None = None


def _get_http_request_counter() -> Counter:
    """Get or create HTTP request counter metric."""
    global _http_request_counter
    if _http_request_counter is None:
        meter = get_meter()
        _http_request_counter = meter.create_counter(
            name="http_requests_total",
            description="Total number of HTTP requests",
            unit="1",
        )
    return _http_request_counter


def _get_http_request_duration() -> Histogram:
    """Get or create HTTP request duration histogram."""
    global _http_request_duration
    if _http_request_duration is None:
        meter = get_meter()
        _http_request_duration = meter.create_histogram(
            name="http_request_duration_ms",
            description="HTTP request duration in milliseconds",
            unit="ms",
        )
    return _http_request_duration


def _get_active_requests_gauge() -> UpDownCounter:
    """Get or create active requests gauge metric."""
    global _active_requests_gauge
    if _active_requests_gauge is None:
        meter = get_meter()
        _active_requests_gauge = meter.create_up_down_counter(
            name="http_active_requests",
            description="Number of active HTTP requests",
            unit="1",
        )
    return _active_requests_gauge


def _get_db_query_counter() -> Counter:
    """Get or create database query counter metric."""
    global _db_query_counter
    if _db_query_counter is None:
        meter = get_meter()
        _db_query_counter = meter.create_counter(
            name="database_queries_total",
            description="Total number of database queries",
            unit="1",
        )
    return _db_query_counter


def _get_db_query_duration() -> Histogram:
    """Get or create database query duration histogram."""
    global _db_query_duration
    if _db_query_duration is None:
        meter = get_meter()
        _db_query_duration = meter.create_histogram(
            name="database_query_duration_ms",
            description="Database query duration in milliseconds",
            unit="ms",
        )
    return _db_query_duration


def _get_redis_operation_counter() -> Counter:
    """Get or create Redis operation counter metric."""
    global _redis_operation_counter
    if _redis_operation_counter is None:
        meter = get_meter()
        _redis_operation_counter = meter.create_counter(
            name="redis_operations_total",
            description="Total number of Redis operations",
            unit="1",
        )
    return _redis_operation_counter


def _get_redis_operation_duration() -> Histogram:
    """Get or create Redis operation duration histogram."""
    global _redis_operation_duration
    if _redis_operation_duration is None:
        meter = get_meter()
        _redis_operation_duration = meter.create_histogram(
            name="redis_operation_duration_ms",
            description="Redis operation duration in milliseconds",
            unit="ms",
        )
    return _redis_operation_duration


def _get_error_counter() -> Counter:
    """Get or create error counter metric."""
    global _error_counter
    if _error_counter is None:
        meter = get_meter()
        _error_counter = meter.create_counter(
            name="errors_total",
            description="Total number of errors",
            unit="1",
        )
    return _error_counter


def _get_business_metric_counter() -> Counter:
    """Get or create business metric counter."""
    global _business_metric_counter
    if _business_metric_counter is None:
        meter = get_meter()
        _business_metric_counter = meter.create_counter(
            name="business_metrics_total",
            description="Total number of business metric events",
            unit="1",
        )
    return _business_metric_counter


def _normalize_path(path: str) -> str:
    """Normalize path to reduce metric cardinality.

    Replaces UUIDs and numeric IDs with placeholders.

    Args:
        path: Original path

    Returns:
        Normalized path
    """
    import re

    # Replace UUIDs
    path = re.sub(
        r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "/{id}",
        path,
        flags=re.IGNORECASE,
    )

    # Replace numeric IDs
    path = re.sub(r"/\d+", "/{id}", path)

    return path


def emit_http_request(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    **metadata: Any,
) -> None:
    """Emit HTTP request metrics using OpenTelemetry.

    Args:
        method: HTTP method (GET, POST, etc.)
        path: Request path
        status_code: HTTP status code
        duration_ms: Request duration in milliseconds
        **metadata: Additional metadata (user_id, tenant_id, etc.)
        Note: Query parameters are NOT included to avoid exposing sensitive data.
    """
    if not settings.enable_metrics:
        return

    try:
        # Normalize path to reduce cardinality
        normalized_path = _normalize_path(path)

        # Create attributes/labels
        attributes = {
            "http.method": method,
            "http.route": normalized_path,
            "http.status_code": str(status_code),
        }

        # Add metadata as attributes if provided
        if metadata:
            for key, value in metadata.items():
                if value is not None:
                    attributes[key] = str(value)

        # Emit counter
        counter = _get_http_request_counter()
        counter.add(1, attributes=attributes)

        # Emit duration histogram
        duration_histogram = _get_http_request_duration()
        duration_histogram.record(duration_ms, attributes=attributes)

    except Exception as e:
        # Don't let metric emission failures break requests
        logger.warning(f"Failed to emit HTTP request metric: {e}", exc_info=True)


def increment_active_requests(**metadata: Any) -> None:
    """Increment active HTTP requests counter.

    Args:
        **metadata: Additional metadata
    """
    if not settings.enable_metrics:
        return

    try:
        attributes = {}
        if metadata:
            for key, value in metadata.items():
                if value is not None:
                    attributes[key] = str(value)

        gauge = _get_active_requests_gauge()
        gauge.add(1, attributes=attributes)

    except Exception as e:
        logger.warning(f"Failed to increment active requests metric: {e}", exc_info=True)


def decrement_active_requests(**metadata: Any) -> None:
    """Decrement active HTTP requests counter.

    Args:
        **metadata: Additional metadata
    """
    if not settings.enable_metrics:
        return

    try:
        attributes = {}
        if metadata:
            for key, value in metadata.items():
                if value is not None:
                    attributes[key] = str(value)

        gauge = _get_active_requests_gauge()
        gauge.add(-1, attributes=attributes)

    except Exception as e:
        logger.warning(f"Failed to decrement active requests metric: {e}", exc_info=True)


def emit_database_query(
    operation: str,
    duration_ms: float,
    success: bool = True,
    **metadata: Any,
) -> None:
    """Emit database query metrics using OpenTelemetry.

    Args:
        operation: Operation type (SELECT, INSERT, UPDATE, etc.)
        duration_ms: Query duration in milliseconds
        success: Whether the query succeeded
        **metadata: Additional metadata
    """
    if not settings.enable_metrics:
        return

    try:
        attributes = {
            "db.operation": operation,
            "db.success": str(success).lower(),
        }

        if metadata:
            for key, value in metadata.items():
                if value is not None:
                    attributes[key] = str(value)

        # Emit counter
        counter = _get_db_query_counter()
        counter.add(1, attributes=attributes)

        # Emit duration histogram
        duration_histogram = _get_db_query_duration()
        duration_histogram.record(duration_ms, attributes=attributes)

    except Exception as e:
        # Don't let metric emission failures break queries
        logger.warning(f"Failed to emit database query metric: {e}", exc_info=True)


def emit_redis_operation(
    operation: str,
    duration_ms: float,
    success: bool = True,
    **metadata: Any,
) -> None:
    """Emit Redis operation metrics using OpenTelemetry.

    Args:
        operation: Operation type (GET, SET, etc.)
        duration_ms: Operation duration in milliseconds
        success: Whether the operation succeeded
        **metadata: Additional metadata
    """
    if not settings.enable_metrics:
        return

    try:
        attributes = {
            "redis.operation": operation.upper(),
            "redis.success": str(success).lower(),
        }

        if metadata:
            for key, value in metadata.items():
                if value is not None:
                    attributes[key] = str(value)

        # Emit counter
        counter = _get_redis_operation_counter()
        counter.add(1, attributes=attributes)

        # Emit duration histogram
        duration_histogram = _get_redis_operation_duration()
        duration_histogram.record(duration_ms, attributes=attributes)

    except Exception as e:
        # Don't let metric emission failures break Redis operations
        logger.warning(f"Failed to emit Redis operation metric: {e}", exc_info=True)


def emit_error(
    error_code: str,
    status_code: int,
    path: str,
    method: str,
    **metadata: Any,
) -> None:
    """Emit error metrics using OpenTelemetry.

    Args:
        error_code: Application error code
        status_code: HTTP status code
        path: Request path
        method: HTTP method
        **metadata: Additional metadata
    """
    if not settings.enable_metrics:
        return

    try:
        # Normalize path to reduce cardinality
        normalized_path = _normalize_path(path)

        # Classify error severity
        if status_code >= 500:
            severity = "server_error"
        elif status_code >= 400:
            severity = "client_error"
        else:
            severity = "unknown"

        attributes = {
            "error.code": error_code,
            "http.status_code": str(status_code),
            "error.severity": severity,
            "http.method": method,
            "http.route": normalized_path,
        }

        if metadata:
            for key, value in metadata.items():
                if value is not None:
                    attributes[key] = str(value)

        counter = _get_error_counter()
        counter.add(1, attributes=attributes)

    except Exception as e:
        logger.warning(f"Failed to emit error metric: {e}", exc_info=True)


def emit_business_metric(
    metric_name: str,
    value: float,
    unit: str = "Count",
    category: str | None = None,
    **metadata: Any,
) -> None:
    """Emit business metric using OpenTelemetry.

    Args:
        metric_name: Name of the business metric
        value: Metric value
        unit: Unit of measurement (default: Count)
        category: Optional category for grouping (e.g., "user", "report")
        **metadata: Additional metadata
    """
    if not settings.enable_metrics:
        return

    try:
        attributes = {
            "metric.name": metric_name,
            "metric.unit": unit,
        }

        if category:
            attributes["metric.category"] = category

        if metadata:
            for key, meta_value in metadata.items():
                if meta_value is not None:
                    attributes[key] = str(meta_value)

        counter = _get_business_metric_counter()
        # Convert value to int for counter (counters only accept integers)
        counter.add(int(value), attributes=attributes)

    except Exception as e:
        logger.warning(f"Failed to emit business metric: {e}", exc_info=True)
