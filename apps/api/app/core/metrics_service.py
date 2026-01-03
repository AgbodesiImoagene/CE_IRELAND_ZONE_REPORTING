"""Centralized service for emitting business metrics.

This service provides helper methods for emitting business metrics with
consistent structure and metadata.
"""

from typing import Optional
from uuid import UUID

from app.core.otel_metrics import emit_business_metric
from app.core.business_metrics import BusinessMetric, MetricCategory


class MetricsService:
    """Centralized service for emitting business metrics."""

    @staticmethod
    def emit_user_metric(
        metric_name: str,
        tenant_id: UUID,
        user_id: Optional[UUID] = None,
        actor_id: Optional[UUID] = None,
        **extra_metadata,
    ) -> None:
        """Emit a user-related metric.

        Args:
            metric_name: Metric name from BusinessMetric enum
            tenant_id: Tenant ID
            user_id: ID of the user being acted upon (if applicable)
            actor_id: ID of the user performing the action
            **extra_metadata: Additional metadata to include
        """
        metadata = {
            "tenant_id": str(tenant_id),
        }
        if user_id:
            metadata["user_id"] = str(user_id)
        if actor_id:
            metadata["actor_id"] = str(actor_id)
        metadata.update(extra_metadata)

        emit_business_metric(
            metric_name=metric_name,
            value=1,
            category=MetricCategory.USER.value,
            **metadata,
        )

    @staticmethod
    def emit_report_metric(
        metric_name: str,
        tenant_id: UUID,
        user_id: UUID,
        report_type: Optional[str] = None,
        **extra_metadata,
    ) -> None:
        """Emit a report-related metric.

        Args:
            metric_name: Metric name from BusinessMetric enum
            tenant_id: Tenant ID
            user_id: ID of the user performing the action
            report_type: Type of report (optional)
            **extra_metadata: Additional metadata to include
        """
        metadata = {
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
        }
        if report_type:
            metadata["report_type"] = report_type
        metadata.update(extra_metadata)

        emit_business_metric(
            metric_name=metric_name,
            value=1,
            category=MetricCategory.REPORT.value,
            **metadata,
        )

    @staticmethod
    def emit_cell_metric(
        metric_name: str,
        tenant_id: UUID,
        actor_id: UUID,
        cell_id: Optional[UUID] = None,
        **extra_metadata,
    ) -> None:
        """Emit a cell-related metric.

        Args:
            metric_name: Metric name from BusinessMetric enum
            tenant_id: Tenant ID
            actor_id: ID of the user performing the action
            cell_id: ID of the cell (if applicable)
            **extra_metadata: Additional metadata to include
        """
        metadata = {
            "tenant_id": str(tenant_id),
            "actor_id": str(actor_id),
        }
        if cell_id:
            metadata["cell_id"] = str(cell_id)
        metadata.update(extra_metadata)

        emit_business_metric(
            metric_name=metric_name,
            value=1,
            category=MetricCategory.CELL.value,
            **metadata,
        )

    @staticmethod
    def emit_finance_metric(
        metric_name: str,
        tenant_id: UUID,
        actor_id: UUID,
        org_unit_id: Optional[UUID] = None,
        **extra_metadata,
    ) -> None:
        """Emit a finance-related metric.

        Args:
            metric_name: Metric name from BusinessMetric enum
            tenant_id: Tenant ID
            actor_id: ID of the user performing the action
            org_unit_id: ID of the org unit (if applicable)
            **extra_metadata: Additional metadata to include
        """
        metadata = {
            "tenant_id": str(tenant_id),
            "actor_id": str(actor_id),
        }
        if org_unit_id:
            metadata["org_unit_id"] = str(org_unit_id)
        metadata.update(extra_metadata)

        emit_business_metric(
            metric_name=metric_name,
            value=1,
            category=MetricCategory.FINANCE.value,
            **metadata,
        )

    @staticmethod
    def emit_registry_metric(
        metric_name: str,
        tenant_id: UUID,
        actor_id: UUID,
        org_unit_id: Optional[UUID] = None,
        entity_type: Optional[str] = None,
        **extra_metadata,
    ) -> None:
        """Emit a registry-related metric.

        Args:
            metric_name: Metric name from BusinessMetric enum
            tenant_id: Tenant ID
            actor_id: ID of the user performing the action
            org_unit_id: ID of the org unit (if applicable)
            entity_type: Type of entity (people, first_timers, etc.)
            **extra_metadata: Additional metadata to include
        """
        metadata = {
            "tenant_id": str(tenant_id),
            "actor_id": str(actor_id),
        }
        if org_unit_id:
            metadata["org_unit_id"] = str(org_unit_id)
        if entity_type:
            metadata["entity_type"] = entity_type
        metadata.update(extra_metadata)

        emit_business_metric(
            metric_name=metric_name,
            value=1,
            category=MetricCategory.REGISTRY.value,
            **metadata,
        )

    @staticmethod
    def emit_import_metric(
        metric_name: str,
        tenant_id: UUID,
        user_id: UUID,
        entity_type: Optional[str] = None,
        rows_processed: Optional[int] = None,
        **extra_metadata,
    ) -> None:
        """Emit an import-related metric.

        Args:
            metric_name: Metric name from BusinessMetric enum
            tenant_id: Tenant ID
            user_id: ID of the user performing the import
            entity_type: Type of entity being imported
            rows_processed: Number of rows processed (for ImportRowsProcessed)
            **extra_metadata: Additional metadata to include
        """
        metadata = {
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
        }
        if entity_type:
            metadata["entity_type"] = entity_type
        if rows_processed is not None:
            metadata["rows_processed"] = rows_processed
        metadata.update(extra_metadata)

        emit_business_metric(
            metric_name=metric_name,
            value=rows_processed if rows_processed is not None else 1,
            category=MetricCategory.IMPORT.value,
            **metadata,
        )

    @staticmethod
    def emit_iam_metric(
        metric_name: str,
        tenant_id: UUID,
        actor_id: UUID,
        **extra_metadata,
    ) -> None:
        """Emit an IAM-related metric.

        Args:
            metric_name: Metric name from BusinessMetric enum
            tenant_id: Tenant ID
            actor_id: ID of the user performing the action
            **extra_metadata: Additional metadata to include
        """
        metadata = {
            "tenant_id": str(tenant_id),
            "actor_id": str(actor_id),
        }
        metadata.update(extra_metadata)

        emit_business_metric(
            metric_name=metric_name,
            value=1,
            category=MetricCategory.IAM.value,
            **metadata,
        )

    @staticmethod
    def emit_security_metric(
        metric_name: str,
        tenant_id: UUID,
        user_id: Optional[UUID] = None,
        **extra_metadata,
    ) -> None:
        """Emit a security-related metric.

        Args:
            metric_name: Metric name from BusinessMetric enum
            tenant_id: Tenant ID
            user_id: ID of the user (if applicable)
            **extra_metadata: Additional metadata to include
        """
        metadata = {
            "tenant_id": str(tenant_id),
        }
        if user_id:
            metadata["user_id"] = str(user_id)
        metadata.update(extra_metadata)

        emit_business_metric(
            metric_name=metric_name,
            value=1,
            category=MetricCategory.SECURITY.value,
            **metadata,
        )

    @staticmethod
    def emit_data_quality_metric(
        metric_name: str,
        tenant_id: UUID,
        entity_type: Optional[str] = None,
        **extra_metadata,
    ) -> None:
        """Emit a data quality-related metric.

        Args:
            metric_name: Metric name from BusinessMetric enum
            tenant_id: Tenant ID
            entity_type: Type of entity (if applicable)
            **extra_metadata: Additional metadata to include
        """
        metadata = {
            "tenant_id": str(tenant_id),
        }
        if entity_type:
            metadata["entity_type"] = entity_type
        metadata.update(extra_metadata)

        emit_business_metric(
            metric_name=metric_name,
            value=1,
            category=MetricCategory.DATA_QUALITY.value,
            **metadata,
        )

