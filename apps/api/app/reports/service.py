"""Reports service layer for queries, dashboards, exports, templates, and schedules."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.common.audit import create_audit_log
from app.reports.models import ExportJob, ReportTemplate, ReportSchedule
from app.reports.query_builder import ReportQueryBuilder
from app.reports.scope_validation import require_permission

logger = logging.getLogger(__name__)


def _serialize_for_json(obj: Any) -> Any:
    """
    Recursively convert UUID objects and other non-serializable types to JSON-serializable formats.
    
    Args:
        obj: Object to serialize
        
    Returns:
        JSON-serializable version of the object
    """
    if isinstance(obj, UUID):
        return str(obj)
    elif isinstance(obj, (date, datetime)):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_serialize_for_json(item) for item in obj]
    elif hasattr(obj, "__mapper__"):
        # SQLAlchemy model instance - convert to dict
        result = {}
        for column in obj.__table__.columns:
            value = getattr(obj, column.name, None)
            result[column.name] = _serialize_for_json(value)
        return result
    else:
        return obj


class ReportService:
    """Service for executing report queries."""

    @staticmethod
    def execute_query(
        db: Session,
        tenant_id: UUID,
        user_id: UUID,
        query_request: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute a flexible report query.

        Args:
            db: Database session
            tenant_id: Tenant ID
            user_id: User ID
            query_request: Query definition dictionary

        Returns:
            Dictionary with results and metadata
        """
        require_permission(db, user_id, tenant_id, "reports.query.execute")

        builder = ReportQueryBuilder(db, tenant_id, user_id)

        # Build query
        stmt = builder.build_query(
            entity_type=query_request["entity_type"],
            filters=query_request.get("filters", {}),
            aggregations=[
                agg if isinstance(agg, dict) else agg.model_dump()
                for agg in query_request.get("aggregations", [])
            ],
            group_by=query_request.get("group_by", []),
            order_by=[
                order if isinstance(order, dict) else order.model_dump()
                for order in query_request.get("order_by", [])
            ],
            data_quality=query_request.get("data_quality"),
            limit=query_request.get("limit", 1000),
            offset=query_request.get("offset", 0),
        )

        # Execute query
        results = db.execute(stmt).all()

        # Convert to dictionaries
        result_dicts = []
        for row in results:
            if hasattr(row, "_asdict"):
                # Row object from aggregation/group_by queries or SQLAlchemy 2.0 Row with model
                row_dict = row._asdict()
                # Check if Row contains a single model instance (SQLAlchemy 2.0 behavior)
                # When select(model) is executed, Row._asdict() returns {ModelClass: instance}
                if isinstance(row_dict, dict) and len(row_dict) == 1:
                    model_instance = list(row_dict.values())[0]
                    if hasattr(model_instance, "__mapper__"):
                        # Extract model instance and convert properly
                        row_dict = {}
                        for column in model_instance.__table__.columns:
                            value = getattr(model_instance, column.name, None)
                            row_dict[column.name] = _serialize_for_json(value)
                result_dicts.append(row_dict)
            elif hasattr(row, "__mapper__"):
                # SQLAlchemy model instance - convert to dict properly
                row_dict = {}
                for column in row.__table__.columns:
                    value = getattr(row, column.name, None)
                    # Serialize UUIDs, dates, etc.
                    row_dict[column.name] = _serialize_for_json(value)
                result_dicts.append(row_dict)
            elif isinstance(row, tuple):
                # Tuple result - use column keys from statement
                try:
                    # Try to get keys from the statement
                    if hasattr(stmt, "column_descriptions"):
                        keys = [desc["name"] for desc in stmt.column_descriptions]
                    elif hasattr(stmt, "selected_columns"):
                        keys = list(stmt.selected_columns.keys())
                    else:
                        keys = [f"col_{i}" for i in range(len(row))]
                    result_dicts.append(dict(zip(keys, [_serialize_for_json(v) for v in row])))
                except Exception:
                    result_dicts.append({f"col_{i}": _serialize_for_json(v) for i, v in enumerate(row)})
            else:
                # Fallback: try to convert to dict
                try:
                    result_dicts.append(_serialize_for_json(dict(row)))
                except Exception:
                    result_dicts.append({"value": _serialize_for_json(row)})

        # Get total count (without limit/offset)
        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.execute(total_stmt).scalar() or len(result_dicts)

        # Audit log - serialize UUIDs to strings for JSON compatibility
        serialized_query = _serialize_for_json(query_request)
        create_audit_log(
            db,
            user_id,
            "report.view",
            query_request["entity_type"],
            None,
            None,
            {"query": serialized_query},
        )

        return {
            "results": result_dicts,
            "total": total,
            "limit": query_request.get("limit", 1000),
            "offset": query_request.get("offset", 0),
            "metadata": {
                "entity_type": query_request["entity_type"],
                "executed_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    @staticmethod
    def get_dashboard(
        db: Session,
        tenant_id: UUID,
        user_id: UUID,
        dashboard_type: str,
        org_unit_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        group_by: Optional[str] = None,
        include_children: bool = False,
    ) -> dict[str, Any]:
        """
        Get predefined dashboard data.

        Args:
            db: Database session
            tenant_id: Tenant ID
            user_id: User ID
            dashboard_type: Type of dashboard (membership, attendance, finance, cells, overview)
            org_unit_id: Optional org unit filter
            start_date: Optional start date
            end_date: Optional end date
            group_by: Optional time grouping (day, week, month, quarter, year)
            include_children: Include child org units

        Returns:
            Dashboard data dictionary
        """
        require_permission(db, user_id, tenant_id, "reports.dashboards.read")

        # Build query based on dashboard type
        query_request = {
            "entity_type": _get_entity_type_for_dashboard(dashboard_type),
            "filters": {},
            "aggregations": [],
            "group_by": [],
        }

        if org_unit_id:
            if include_children:
                # Get all child org units
                from app.common.models import OrgUnit
                child_orgs = _get_descendant_org_units(db, org_unit_id)
                query_request["filters"]["org_unit_id"] = [org_unit_id] + child_orgs
            else:
                query_request["filters"]["org_unit_id"] = org_unit_id

        if start_date:
            date_field = _get_date_field_for_dashboard(dashboard_type)
            query_request["filters"][date_field] = {"gte": start_date.isoformat()}

        if end_date:
            date_field = _get_date_field_for_dashboard(dashboard_type)
            if date_field in query_request["filters"]:
                query_request["filters"][date_field]["lte"] = end_date.isoformat()
            else:
                query_request["filters"][date_field] = {"lte": end_date.isoformat()}

        if group_by:
            date_field = _get_date_field_for_dashboard(dashboard_type)
            query_request["group_by"].append(f"date_trunc_{group_by}_{date_field}")
            query_request["aggregations"].append({
                "field": "id",
                "function": "count",
                "alias": "count",
            })

        # Apply default aggregations based on dashboard type
        query_request["aggregations"].extend(
            _get_default_aggregations_for_dashboard(dashboard_type)
        )

        # Execute query
        return ReportService.execute_query(db, tenant_id, user_id, query_request)


class ExportService:
    """Service for managing export jobs."""

    @staticmethod
    def create_export_job(
        db: Session,
        tenant_id: UUID,
        user_id: UUID,
        format: str,
        query_definition: dict[str, Any],
        template_id: Optional[UUID] = None,
    ) -> ExportJob:
        """
        Create an export job.

        Args:
            db: Database session
            tenant_id: Tenant ID
            user_id: User ID
            format: Export format (csv, excel, pdf)
            query_definition: Query definition
            template_id: Optional template ID

        Returns:
            Created ExportJob
        """
        require_permission(db, user_id, tenant_id, "reports.exports.create")

        job = ExportJob(
            id=uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            status="pending",
            format=format,
            query_definition=query_definition,
            template_id=template_id,
        )
        db.add(job)

        # Audit log
        create_audit_log(
            db,
            user_id,
            "report.export",
            "export_jobs",
            job.id,
            None,
            {"format": format, "template_id": str(template_id) if template_id else None},
        )

        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def get_export_status(
        db: Session, export_id: UUID, tenant_id: UUID, user_id: UUID
    ) -> Optional[ExportJob]:
        """Get export job status."""
        job = db.execute(
            select(ExportJob).where(
                ExportJob.id == export_id,
                ExportJob.tenant_id == tenant_id,
                ExportJob.user_id == user_id,
            )
        ).scalar_one_or_none()

        return job


class TemplateService:
    """Service for managing report templates."""

    @staticmethod
    def create_template(
        db: Session,
        tenant_id: UUID,
        user_id: UUID,
        name: str,
        query_definition: dict[str, Any],
        description: Optional[str] = None,
        visualization_config: Optional[dict[str, Any]] = None,
        pdf_config: Optional[dict[str, Any]] = None,
        is_shared: bool = False,
        shared_with_org_units: Optional[list[UUID]] = None,
    ) -> ReportTemplate:
        """Create a report template."""
        require_permission(db, user_id, tenant_id, "reports.templates.create")

        template = ReportTemplate(
            id=uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            name=name,
            description=description,
            query_definition=query_definition,
            visualization_config=visualization_config,
            pdf_config=pdf_config,
            is_shared=is_shared,
            shared_with_org_units=shared_with_org_units,
        )
        db.add(template)

        # Audit log
        create_audit_log(
            db,
            user_id,
            "report.template.create",
            "report_templates",
            template.id,
            None,
            {"name": name, "is_shared": is_shared},
        )

        db.commit()
        db.refresh(template)
        return template

    @staticmethod
    def list_templates(
        db: Session,
        tenant_id: UUID,
        user_id: UUID,
        include_shared: bool = True,
    ) -> list[ReportTemplate]:
        """List templates accessible to user."""
        stmt = select(ReportTemplate).where(ReportTemplate.tenant_id == tenant_id)

        # User's own templates
        user_templates = select(ReportTemplate.id).where(
            ReportTemplate.user_id == user_id
        )

        if include_shared:
            # Shared templates
            shared_templates = select(ReportTemplate.id).where(
                ReportTemplate.is_shared == True
            )
            stmt = stmt.where(
                ReportTemplate.id.in_(user_templates) | ReportTemplate.id.in_(shared_templates)
            )
        else:
            stmt = stmt.where(ReportTemplate.id.in_(user_templates))

        stmt = stmt.order_by(ReportTemplate.created_at.desc())

        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def get_template(
        db: Session, template_id: UUID, tenant_id: UUID, user_id: UUID
    ) -> Optional[ReportTemplate]:
        """Get template by ID (if user has access)."""
        template = db.execute(
            select(ReportTemplate).where(
                ReportTemplate.id == template_id,
                ReportTemplate.tenant_id == tenant_id,
            )
        ).scalar_one_or_none()

        if not template:
            return None

        # Check access
        if template.user_id == user_id:
            return template
        if template.is_shared:
            return template
        if template.shared_with_org_units:
            # Check if user has access to any of the shared org units
            from app.users.scope_validation import has_org_access
            for org_unit_id in template.shared_with_org_units:
                if has_org_access(db, user_id, tenant_id, org_unit_id):
                    return template

        return None


class ScheduleService:
    """Service for managing scheduled reports."""

    @staticmethod
    def create_schedule(
        db: Session,
        tenant_id: UUID,
        user_id: UUID,
        template_id: UUID,
        frequency: str,
        time: datetime.time,
        recipients: list[str],
        day_of_week: Optional[int] = None,
        day_of_month: Optional[int] = None,
        query_overrides: Optional[dict[str, Any]] = None,
    ) -> ReportSchedule:
        """Create a scheduled report."""
        require_permission(db, user_id, tenant_id, "reports.schedules.create")

        # Calculate next_run_at
        next_run_at = _calculate_next_run(frequency, time, day_of_week, day_of_month)

        schedule = ReportSchedule(
            id=uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            template_id=template_id,
            frequency=frequency,
            day_of_week=day_of_week,
            day_of_month=day_of_month,
            time=time,
            recipients=recipients,
            query_overrides=query_overrides,
            is_active=True,
            next_run_at=next_run_at,
        )
        db.add(schedule)

        # Audit log
        create_audit_log(
            db,
            user_id,
            "report.schedule.create",
            "report_schedules",
            schedule.id,
            None,
            {"template_id": str(template_id), "frequency": frequency},
        )

        db.commit()
        db.refresh(schedule)
        return schedule

    @staticmethod
    def list_schedules(
        db: Session, tenant_id: UUID, user_id: UUID
    ) -> list[ReportSchedule]:
        """List user's schedules."""
        stmt = (
            select(ReportSchedule)
            .where(
                ReportSchedule.tenant_id == tenant_id,
                ReportSchedule.user_id == user_id,
            )
            .order_by(ReportSchedule.next_run_at)
        )

        return list(db.execute(stmt).scalars().all())


# Helper functions

def _get_entity_type_for_dashboard(dashboard_type: str) -> str:
    """Get entity type for dashboard type."""
    mapping = {
        "membership": "people",
        "attendance": "attendance",
        "finance": "finance_entries",
        "cells": "cell_reports",
        "overview": "people",  # Default for overview
    }
    return mapping.get(dashboard_type, "people")


def _get_date_field_for_dashboard(dashboard_type: str) -> str:
    """Get date field name for dashboard type."""
    mapping = {
        "membership": "created_at",  # People.created_at
        "attendance": "service_date",  # Through Service
        "finance": "transaction_date",
        "cells": "meeting_date",
        "overview": "created_at",
    }
    return mapping.get(dashboard_type, "created_at")


def _get_default_aggregations_for_dashboard(dashboard_type: str) -> list[dict[str, Any]]:
    """Get default aggregations for dashboard type."""
    if dashboard_type == "finance":
        return [
            {"field": "amount", "function": "sum", "alias": "total_amount"},
            {"field": "id", "function": "count", "alias": "entry_count"},
        ]
    elif dashboard_type == "attendance":
        return [
            {"field": "total_attendance", "function": "sum", "alias": "total"},
            {"field": "id", "function": "count", "alias": "service_count"},
        ]
    elif dashboard_type == "membership":
        return [
            {"field": "id", "function": "count", "alias": "member_count"},
        ]
    elif dashboard_type == "cells":
        return [
            {"field": "attendance_count", "function": "avg", "alias": "avg_attendance"},
            {"field": "id", "function": "count", "alias": "report_count"},
        ]
    return []


def _get_descendant_org_units(db: Session, org_unit_id: UUID) -> list[UUID]:
    """Get all descendant org unit IDs."""
    from app.common.models import OrgUnit

    descendants = []
    children = db.execute(
        select(OrgUnit.id).where(OrgUnit.parent_id == org_unit_id)
    ).scalars().all()

    for child_id in children:
        descendants.append(child_id)
        descendants.extend(_get_descendant_org_units(db, child_id))

    return descendants


def _calculate_next_run(
    frequency: str,
    time: datetime.time,
    day_of_week: Optional[int] = None,
    day_of_month: Optional[int] = None,
) -> datetime:
    """Calculate next run time for schedule."""
    now = datetime.now(timezone.utc)
    today = now.date()

    if frequency == "daily":
        next_run = datetime.combine(today, time).replace(tzinfo=timezone.utc)
        if next_run <= now:
            next_run += timedelta(days=1)

    elif frequency == "weekly":
        # Find next occurrence of day_of_week
        days_ahead = day_of_week - now.weekday()
        if days_ahead < 0 or (days_ahead == 0 and datetime.combine(today, time).replace(tzinfo=timezone.utc) <= now):
            days_ahead += 7
        next_run = datetime.combine(today + timedelta(days=days_ahead), time).replace(tzinfo=timezone.utc)

    elif frequency == "monthly":
        # Find next occurrence of day_of_month
        if day_of_month:
            next_month = today.replace(day=1) + timedelta(days=32)
            next_month = next_month.replace(day=1)
            try:
                next_run = datetime.combine(next_month.replace(day=day_of_month), time).replace(tzinfo=timezone.utc)
            except ValueError:
                # Day doesn't exist in month, use last day
                next_run = datetime.combine(next_month - timedelta(days=1), time).replace(tzinfo=timezone.utc)
        else:
            next_run = datetime.combine(today + timedelta(days=1), time).replace(tzinfo=timezone.utc)

    elif frequency == "quarterly":
        # First day of next quarter
        quarter = (now.month - 1) // 3 + 1
        if quarter == 4:
            next_quarter = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            next_quarter = datetime(now.year, quarter * 3 + 1, 1, tzinfo=timezone.utc)
        next_run = datetime.combine(next_quarter.date(), time).replace(tzinfo=timezone.utc)

    else:
        # Default to tomorrow
        next_run = datetime.combine(today + timedelta(days=1), time).replace(tzinfo=timezone.utc)

    return next_run

