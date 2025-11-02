"""CloudWatch Embedded Metric Format (EMF) metrics helper.

EMF allows embedding metrics directly in CloudWatch Logs, which are
automatically extracted and made available as CloudWatch Metrics.
This is simpler and more efficient than using the CloudWatch SDK.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class EMFMetrics:
    """Helper class to emit CloudWatch metrics in EMF format."""

    def __init__(self, namespace: str | None = None):
        """Initialize EMF metrics emitter.

        Args:
            namespace: CloudWatch namespace for metrics.
                Defaults to service name.
        """
        if namespace:
            self.namespace = namespace
        elif settings.metrics_namespace:
            self.namespace = settings.metrics_namespace
        else:
            self.namespace = settings.tenant_name.replace(" ", "/")

    def emit_metric(
        self,
        metric_name: str,
        value: float,
        unit: str,
        dimensions: dict[str, str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Emit a single metric in EMF format.

        Args:
            metric_name: Name of the metric
            value: Metric value
            unit: Unit of measurement (Count, Milliseconds, Bytes, etc.)
            dimensions: Optional dimensions for the metric
            metadata: Optional additional metadata to include in log
        """
        # Check setting dynamically (not cached) to allow runtime changes
        if not settings.enable_metrics:
            return

        emf_log = self._build_emf_log(
            metrics=[
                {
                    "MetricName": metric_name,
                    "Unit": unit,
                }
            ],
            dimensions=dimensions,
            metadata=metadata,
        )
        emf_log[metric_name] = value

        logger.info(json.dumps(emf_log, default=str))

    def emit_metrics(
        self,
        metrics: list[dict[str, Any]],
        dimensions: dict[str, str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Emit multiple metrics in a single EMF log entry.

        Args:
            metrics: List of metric dictionaries with keys:
                MetricName, Value, Unit
            dimensions: Optional dimensions for all metrics
            metadata: Optional additional metadata to include in log
        """
        # Check setting dynamically (not cached) to allow runtime changes
        if not settings.enable_metrics:
            return

        emf_log = self._build_emf_log(
            metrics=[
                {
                    "MetricName": m["MetricName"],
                    "Unit": m["Unit"],
                }
                for m in metrics
            ],
            dimensions=dimensions,
            metadata=metadata,
        )

        # Add metric values to the log
        for metric in metrics:
            emf_log[metric["MetricName"]] = metric["Value"]

        logger.info(json.dumps(emf_log, default=str))

    def _build_emf_log(
        self,
        metrics: list[dict[str, str]],
        dimensions: dict[str, str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build EMF-formatted log entry.

        Args:
            metrics: List of metric definitions
            dimensions: Optional dimensions
            metadata: Optional metadata

        Returns:
            Dictionary ready to be JSON-serialized as EMF log
        """
        emf_log: dict[str, Any] = {
            "_aws": {
                "CloudWatchMetrics": [
                    {
                        "Namespace": self.namespace,
                        "Metrics": metrics,
                        "Dimensions": (
                            [[dim] for dim in dimensions.keys()] if dimensions else []
                        ),
                    }
                ],
                "Timestamp": int(time.time() * 1000),  # ms since epoch
            }
        }

        # Add dimensions as top-level fields
        if dimensions:
            emf_log.update(dimensions)

        # Add metadata as top-level fields
        if metadata:
            emf_log.update(metadata)

        return emf_log


# Global EMF metrics instance
_emf_metrics: EMFMetrics | None = None


def get_metrics() -> EMFMetrics:
    """Get or create the global EMF metrics instance."""
    global _emf_metrics
    if _emf_metrics is None:
        _emf_metrics = EMFMetrics()
    return _emf_metrics


# Convenience functions for common metrics
def emit_http_request(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    **metadata: Any,
) -> None:
    """Emit HTTP request metrics in EMF format.

    Args:
        method: HTTP method (GET, POST, etc.)
        path: Request path
        status_code: HTTP status code
        duration_ms: Request duration in milliseconds
        **metadata: Additional metadata (user_id, tenant_id, etc.)
    """
    metrics_instance = get_metrics()

    # Normalize path to reduce cardinality (remove IDs, etc.)
    normalized_path = _normalize_path(path)

    dimensions = {
        "Method": method,
        "Path": normalized_path,
        "StatusCode": str(status_code),
    }

    metrics_list = [
        {"MetricName": "RequestCount", "Value": 1, "Unit": "Count"},
        {
            "MetricName": "RequestDuration",
            "Value": duration_ms,
            "Unit": "Milliseconds",
        },
    ]

    metadata_with_timing = {
        "request_path": path,  # Keep original path in metadata
        **metadata,
    }

    metrics_instance.emit_metrics(
        metrics=metrics_list,
        dimensions=dimensions,
        metadata=metadata_with_timing,
    )


def emit_active_requests(count: int, **metadata: Any) -> None:
    """Emit active HTTP requests gauge metric.

    Args:
        count: Number of active requests
        **metadata: Additional metadata
    """
    metrics_instance = get_metrics()
    metrics_instance.emit_metric(
        metric_name="ActiveRequests",
        value=count,
        unit="Count",
        metadata=metadata,
    )


def emit_database_query(
    operation: str,
    duration_ms: float,
    success: bool = True,
    **metadata: Any,
) -> None:
    """Emit database query metrics.

    Args:
        operation: Operation type (SELECT, INSERT, UPDATE, etc.)
        duration_ms: Query duration in milliseconds
        success: Whether the query succeeded
        **metadata: Additional metadata
    """
    metrics_instance = get_metrics()

    dimensions = {
        "Operation": operation,
        "Success": str(success).lower(),
    }

    metrics_list = [
        {"MetricName": "DatabaseQueryCount", "Value": 1, "Unit": "Count"},
        {
            "MetricName": "DatabaseQueryDuration",
            "Value": duration_ms,
            "Unit": "Milliseconds",
        },
    ]

    metrics_instance.emit_metrics(
        metrics=metrics_list,
        dimensions=dimensions,
        metadata=metadata,
    )


def emit_redis_operation(
    operation: str,
    duration_ms: float,
    success: bool = True,
    **metadata: Any,
) -> None:
    """Emit Redis operation metrics.

    Args:
        operation: Operation type (GET, SET, etc.)
        duration_ms: Operation duration in milliseconds
        success: Whether the operation succeeded
        **metadata: Additional metadata
    """
    metrics_instance = get_metrics()

    dimensions = {
        "Operation": operation,
        "Success": str(success).lower(),
    }

    metrics_list = [
        {"MetricName": "RedisOperationCount", "Value": 1, "Unit": "Count"},
        {
            "MetricName": "RedisOperationDuration",
            "Value": duration_ms,
            "Unit": "Milliseconds",
        },
    ]

    metrics_instance.emit_metrics(
        metrics=metrics_list,
        dimensions=dimensions,
        metadata=metadata,
    )


def emit_error(
    error_code: str,
    status_code: int,
    path: str,
    method: str,
    **metadata: Any,
) -> None:
    """Emit error metrics.

    Args:
        error_code: Application error code
        status_code: HTTP status code
        path: Request path
        method: HTTP method
        **metadata: Additional metadata
    """
    metrics_instance = get_metrics()

    # Normalize path to reduce cardinality
    normalized_path = _normalize_path(path)

    # Classify error severity
    if status_code >= 500:
        severity = "server_error"
    elif status_code >= 400:
        severity = "client_error"
    else:
        severity = "unknown"

    dimensions = {
        "ErrorCode": error_code,
        "StatusCode": str(status_code),
        "Severity": severity,
        "Method": method,
        "Path": normalized_path,
    }

    metrics_list = [
        {"MetricName": "ErrorCount", "Value": 1, "Unit": "Count"},
    ]

    metadata_with_context = {
        "request_path": path,  # Keep original path in metadata
        **metadata,
    }

    metrics_instance.emit_metrics(
        metrics=metrics_list,
        dimensions=dimensions,
        metadata=metadata_with_context,
    )


def emit_business_metric(
    metric_name: str,
    value: float,
    unit: str = "Count",
    category: str | None = None,
    **metadata: Any,
) -> None:
    """Emit business metric (e.g., user signups, reports generated).

    Args:
        metric_name: Name of the business metric
        value: Metric value
        unit: Unit of measurement (default: Count)
        category: Optional category for grouping (e.g., "user", "report")
        **metadata: Additional metadata
    """
    metrics_instance = get_metrics()

    dimensions: dict[str, str] = {}
    if category:
        dimensions["Category"] = category

    metrics_instance.emit_metric(
        metric_name=metric_name,
        value=value,
        unit=unit,
        dimensions=dimensions if dimensions else None,
        metadata=metadata,
    )


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
