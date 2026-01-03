"""Flexible query builder for report queries."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.common.models import (
    FinanceEntry,
    Attendance,
    CellReport,
    People,
    Service,
    Batch,
    Cell,
    OrgUnit,
)

logger = logging.getLogger(__name__)


class ReportQueryBuilder:
    """Builds SQLAlchemy queries from flexible query definitions."""

    # Entity type to model mapping
    ENTITY_MAPPING = {
        "finance_entries": FinanceEntry,
        "attendance": Attendance,
        "cell_reports": CellReport,
        "people": People,
        "services": Service,
        "batches": Batch,
        "cells": Cell,
    }

    def __init__(self, db: Session, tenant_id: UUID, user_id: UUID):
        """
        Initialize query builder.

        Args:
            db: Database session
            tenant_id: Tenant ID
            user_id: User ID for scope validation
        """
        self.db = db
        self.tenant_id = tenant_id
        self.user_id = user_id

    def build_query(
        self,
        entity_type: str,
        filters: Optional[dict[str, Any]] = None,
        aggregations: Optional[list[dict[str, Any]]] = None,
        group_by: Optional[list[str]] = None,
        order_by: Optional[list[dict[str, Any]]] = None,
        data_quality: Optional[dict[str, Any]] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> Select:
        """
        Build SQLAlchemy select statement from query definition.

        Args:
            entity_type: Entity type (e.g., "finance_entries", "attendance")
            filters: Flexible filter dictionary
            aggregations: List of aggregation configs
            group_by: List of fields to group by
            order_by: List of sort configs
            data_quality: Data quality filters (verified_status, etc.)
            limit: Result limit
            offset: Result offset

        Returns:
            SQLAlchemy Select statement
        """
        # Get base model
        if entity_type not in self.ENTITY_MAPPING:
            raise ValueError(f"Unknown entity type: {entity_type}")

        model = self.ENTITY_MAPPING[entity_type]
        stmt = select(model)

        # Apply tenant filter
        stmt = stmt.where(model.tenant_id == self.tenant_id)

        # Apply org scope restrictions
        stmt = self._apply_org_scope(stmt, model)

        # Apply filters
        if filters:
            stmt = self._apply_filters(stmt, model, filters)

        # Apply data quality filters
        if data_quality:
            stmt = self._apply_data_quality(stmt, model, data_quality)

        # Apply aggregations and grouping (must be last, after all filters)
        if aggregations or group_by:
            stmt = self._apply_aggregations(
                stmt, model, aggregations or [], group_by or []
            )

        # Apply sorting
        if order_by:
            stmt = self._apply_sorting(stmt, model, order_by, aggregations or [])

        # Apply pagination
        if limit:
            stmt = stmt.limit(limit)
        if offset:
            stmt = stmt.offset(offset)

        return stmt

    def _apply_org_scope(self, stmt: Select, model: type) -> Select:
        """
        Apply org scope restrictions based on user's assignments.

        This ensures users can only query data within their org scope.
        """
        # Get all org units the user has access to
        from app.common.models import OrgAssignment, OrgAssignmentUnit

        user_org_units = []
        assignments = self.db.execute(
            select(OrgAssignment).where(
                OrgAssignment.user_id == self.user_id,
                OrgAssignment.tenant_id == self.tenant_id,
            )
        ).scalars().all()

        for assn in assignments:
            if assn.scope_type == "self":
                user_org_units.append(assn.org_unit_id)
            elif assn.scope_type == "subtree":
                # Get all descendants
                descendants = self._get_descendants(assn.org_unit_id)
                user_org_units.extend(descendants)
            elif assn.scope_type == "custom_set":
                custom_units = self.db.execute(
                    select(OrgAssignmentUnit.org_unit_id).where(
                        OrgAssignmentUnit.assignment_id == assn.id
                    )
                ).scalars().all()
                user_org_units.extend(custom_units)

        if not user_org_units:
            # User has no org access - return empty result
            from sqlalchemy import false
            stmt = stmt.where(false())
            return stmt

        # Apply org_unit_id filter
        if hasattr(model, "org_unit_id"):
            stmt = stmt.where(model.org_unit_id.in_(user_org_units))
        elif hasattr(model, "service_id"):
            # For attendance, filter through service
            stmt = stmt.join(Service, Service.id == model.service_id).where(
                Service.org_unit_id.in_(user_org_units)
            )

        return stmt

    def _get_descendants(self, org_unit_id: UUID) -> list[UUID]:
        """Get all descendant org units."""
        descendants = [org_unit_id]
        children = self.db.execute(
            select(OrgUnit.id).where(OrgUnit.parent_id == org_unit_id)
        ).scalars().all()

        for child_id in children:
            descendants.extend(self._get_descendants(child_id))

        return descendants

    def _apply_filters(self, stmt: Select, model: type, filters: dict[str, Any]) -> Select:
        """Apply flexible filters."""
        for field, condition in filters.items():
            if not hasattr(model, field):
                logger.warning(
                    "Field %s not found on model %s, skipping",
                    field,
                    model.__name__,
                )
                continue

            field_attr = getattr(model, field)

            if isinstance(condition, list):
                # IN clause: {"org_unit_id": ["uuid1", "uuid2"]}
                # Convert string UUIDs to UUID objects if needed
                uuids = []
                for item in condition:
                    if isinstance(item, str):
                        uuids.append(UUID(item))
                    else:
                        uuids.append(item)
                stmt = stmt.where(field_attr.in_(uuids))
            elif isinstance(condition, dict):
                # Comparison operators
                if "gte" in condition:
                    value = self._convert_value(condition["gte"], field_attr)
                    stmt = stmt.where(field_attr >= value)
                if "lte" in condition:
                    value = self._convert_value(condition["lte"], field_attr)
                    stmt = stmt.where(field_attr <= value)
                if "gt" in condition:
                    value = self._convert_value(condition["gt"], field_attr)
                    stmt = stmt.where(field_attr > value)
                if "lt" in condition:
                    value = self._convert_value(condition["lt"], field_attr)
                    stmt = stmt.where(field_attr < value)
                if "is_null" in condition:
                    if condition["is_null"]:
                        stmt = stmt.where(field_attr.is_(None))
                    else:
                        stmt = stmt.where(field_attr.isnot(None))
                if "in" in condition:
                    # Alternative IN syntax
                    values = condition["in"]
                    uuids = []
                    for item in values:
                        if isinstance(item, str):
                            uuids.append(UUID(item))
                        else:
                            uuids.append(item)
                    stmt = stmt.where(field_attr.in_(uuids))
            else:
                # Exact match
                value = self._convert_value(condition, field_attr)
                stmt = stmt.where(field_attr == value)

        return stmt

    def _convert_value(self, value: Any, field_attr: Any) -> Any:
        """Convert value to appropriate type for field."""
        # Handle UUID strings
        if isinstance(value, str):
            try:
                return UUID(value)
            except (ValueError, AttributeError):
                pass

        # Handle date strings
        if isinstance(value, str) and hasattr(field_attr.property.columns[0].type, "python_type"):
            if field_attr.property.columns[0].type.python_type == date:
                return datetime.fromisoformat(value).date()
            elif field_attr.property.columns[0].type.python_type == datetime:
                return datetime.fromisoformat(value)

        return value

    def _apply_data_quality(
        self, stmt: Select, model: type, data_quality: dict[str, Any]
    ) -> Select:
        """Apply data quality filters (verified_status, etc.)."""
        # Finance entries: only verified/locked
        if model == FinanceEntry:
            verified_statuses = data_quality.get(
                "verified_status", ["verified", "reconciled", "locked"]
            )
            if verified_statuses:
                stmt = stmt.where(FinanceEntry.verified_status.in_(verified_statuses))

        # Cell reports: only approved
        if model == CellReport:
            statuses = data_quality.get("cell_report_status", ["approved"])
            if statuses:
                stmt = stmt.where(CellReport.status.in_(statuses))

        # Attendance: only approved (if we add approval status)
        # For now, attendance doesn't have status, so we accept all

        return stmt

    def _apply_aggregations(
        self,
        stmt: Select,
        model: type,
        aggregations: list[dict[str, Any]],
        group_by: list[str],
    ) -> Select:
        """Apply aggregations and grouping."""
        select_clauses = []
        group_by_clauses = []
        field_labels = {}  # Map field names to their label expressions

        # Add group_by fields to select
        for field in group_by:
            if hasattr(model, field):
                label_expr = getattr(model, field).label(field)
                select_clauses.append(label_expr)
                group_by_clauses.append(getattr(model, field))
                field_labels[field] = label_expr
            else:
                # Handle date_trunc for time-based grouping
                if field.startswith("date_trunc_"):
                    # Format: "date_trunc_week_transaction_date"
                    parts = field.split("_", 3)
                    if len(parts) == 4 and parts[0] == "date" and parts[1] == "trunc":
                        unit = parts[2]  # week, month, quarter, year
                        date_field = parts[3]
                        if hasattr(model, date_field):
                            date_attr = getattr(model, date_field)
                            label_expr = func.date_trunc(unit, date_attr).label(field)
                            select_clauses.append(label_expr)
                            group_by_clauses.append(func.date_trunc(unit, date_attr))
                            field_labels[field] = label_expr

        # Add aggregations
        for agg in aggregations:
            field_name = agg.get("field")
            func_name = agg.get("function", "count")
            alias = agg.get("alias", f"{func_name}_{field_name}")

            if func_name == "count" and (field_name is None or field_name == "id"):
                # Count all rows
                select_clauses.append(func.count().label(alias))
                continue
            elif not field_name:
                logger.warning("Missing field name for aggregation")
                continue
            elif not hasattr(model, field_name):
                logger.warning(
                    "Field %s not found on model %s", field_name, model.__name__
                )
                continue
            else:
                field_attr = getattr(model, field_name)

                if func_name == "sum":
                    select_clauses.append(func.sum(field_attr).label(alias))
                elif func_name == "count":
                    select_clauses.append(
                        func.count(field_attr).label(alias)
                    )
                elif func_name == "avg":
                    select_clauses.append(func.avg(field_attr).label(alias))
                elif func_name == "min":
                    select_clauses.append(func.min(field_attr).label(alias))
                elif func_name == "max":
                    select_clauses.append(func.max(field_attr).label(alias))
                elif func_name == "date_trunc":
                    params = agg.get("params", {})
                    unit = params.get("unit", "day")
                    label_expr = func.date_trunc(unit, field_attr).label(alias)
                    select_clauses.append(label_expr)
                    field_labels[alias] = label_expr
                else:
                    logger.warning(
                        "Unknown aggregation function: %s", func_name
                    )

        # Rebuild statement with new select clauses
        if select_clauses:
            # Extract where conditions from original statement
            # SQLAlchemy stores where conditions in stmt.whereclause
            where_conditions = stmt.whereclause if hasattr(stmt, 'whereclause') else None

            # Build new statement from model
            new_stmt = select(*select_clauses).select_from(model)

            # Reapply where conditions from original statement
            if where_conditions is not None:
                new_stmt = new_stmt.where(where_conditions)

            # Add group_by
            if group_by_clauses:
                new_stmt = new_stmt.group_by(*group_by_clauses)

            return new_stmt

        return stmt

    def _apply_sorting(
        self,
        stmt: Select,
        model: type,
        order_by: list[dict[str, Any]],
        aggregations: list[dict[str, Any]],
    ) -> Select:
        """Apply sorting."""
        order_clauses = []

        for sort_config in order_by:
            field = sort_config.get("field")
            direction = sort_config.get("direction", "asc").lower()

            # Check if it's an aggregation alias
            agg_alias = next(
                (
                    agg.get("alias")
                    for agg in aggregations
                    if agg.get("alias") == field
                ),
                None,
            )
            if agg_alias and field:
                # Use the label (field is a string, need to find in select)
                # For now, skip - sorting by alias requires different approach
                logger.warning(
                    "Sorting by aggregation alias not yet supported: %s", field
                )
            elif field and hasattr(model, field):
                # Use model field
                field_attr = getattr(model, field)
                if direction == "desc":
                    order_clauses.append(field_attr.desc())
                else:
                    order_clauses.append(field_attr.asc())
            else:
                logger.warning("Field %s not found for sorting", field)

        if order_clauses:
            stmt = stmt.order_by(*order_clauses)

        return stmt

