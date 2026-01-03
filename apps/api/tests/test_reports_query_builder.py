"""Tests for report query builder."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.common.models import (
    FinanceEntry,
    Fund,
    Batch,
    OrgAssignment,
    OrgUnit,
    People,
    Service,
    Attendance,
)
from app.reports.query_builder import ReportQueryBuilder


@pytest.fixture
def reports_user(db, tenant_id, test_org_unit):
    """Create a user with reports permissions."""
    from app.common.models import User, Role, Permission, RolePermission, OrgAssignment
    from app.auth.utils import hash_password

    user = User(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        email="reports@test.com",
        password_hash=hash_password("testpass123"),
        is_active=True,
    )
    db.add(user)
    db.flush()

    role = Role(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        name="Reports Role",
    )
    db.add(role)
    db.flush()

    # Create reports permissions
    perms = [
        ("reports.dashboards.read", "Read dashboards"),
        ("reports.query.execute", "Execute queries"),
        ("reports.exports.create", "Create exports"),
    ]

    for code, desc in perms:
        perm = Permission(id=uuid4(), code=code, description=desc)
        db.add(perm)
        db.flush()
        role_perm = RolePermission(role_id=role.id, permission_id=perm.id)
        db.add(role_perm)

    assignment = OrgAssignment(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        user_id=user.id,
        org_unit_id=test_org_unit.id,
        role_id=role.id,
        scope_type="self",
    )
    db.add(assignment)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_fund(db, tenant_id):
    """Create a test fund."""
    fund = Fund(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        name="Tithes",
        is_partnership=False,
        active=True,
    )
    db.add(fund)
    db.commit()
    db.refresh(fund)
    return fund


@pytest.fixture
def test_finance_entries(db, tenant_id, test_org_unit, test_fund, reports_user):
    """Create test finance entries."""
    entries = []
    for i in range(5):
        entry = FinanceEntry(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            fund_id=test_fund.id,
            amount=Decimal(f"100.{i}"),
            currency="EUR",
            method="cash",
            verified_status="verified",
            transaction_date=date(2024, 1, 1 + i),
        )
        db.add(entry)
        entries.append(entry)
    db.commit()
    return entries


class TestReportQueryBuilder:
    """Test report query builder."""

    def test_build_simple_query(
        self, db, tenant_id, reports_user, test_finance_entries
    ):
        """Test building a simple query without filters."""
        builder = ReportQueryBuilder(db, UUID(tenant_id), reports_user.id)

        stmt = builder.build_query(
            entity_type="finance_entries",
            filters={},
            aggregations=[],
            group_by=[],
            limit=10,
        )

        results = db.execute(stmt).all()
        assert len(results) == 5

    def test_build_query_with_filters(
        self, db, tenant_id, reports_user, test_finance_entries, test_fund
    ):
        """Test building query with filters."""
        builder = ReportQueryBuilder(db, UUID(tenant_id), reports_user.id)

        stmt = builder.build_query(
            entity_type="finance_entries",
            filters={"fund_id": str(test_fund.id)},
            aggregations=[],
            group_by=[],
        )

        results = db.execute(stmt).all()
        assert len(results) == 5

    def test_build_query_with_date_range(
        self, db, tenant_id, reports_user, test_finance_entries
    ):
        """Test building query with date range filter."""
        builder = ReportQueryBuilder(db, UUID(tenant_id), reports_user.id)

        stmt = builder.build_query(
            entity_type="finance_entries",
            filters={
                "transaction_date": {
                    "gte": "2024-01-02",
                    "lte": "2024-01-04",
                }
            },
            aggregations=[],
            group_by=[],
        )

        results = db.execute(stmt).all()
        assert len(results) == 3

    def test_build_query_with_aggregation(
        self, db, tenant_id, reports_user, test_finance_entries
    ):
        """Test building query with aggregation."""
        builder = ReportQueryBuilder(db, UUID(tenant_id), reports_user.id)

        stmt = builder.build_query(
            entity_type="finance_entries",
            filters={},
            aggregations=[
                {"field": "amount", "function": "sum", "alias": "total"}
            ],
            group_by=[],
        )

        results = db.execute(stmt).all()
        assert len(results) == 1
        assert float(results[0].total) > 0

    def test_build_query_with_group_by(
        self, db, tenant_id, reports_user, test_finance_entries
    ):
        """Test building query with group by."""
        builder = ReportQueryBuilder(db, UUID(tenant_id), reports_user.id)

        stmt = builder.build_query(
            entity_type="finance_entries",
            filters={},
            aggregations=[
                {"field": "amount", "function": "sum", "alias": "total"},
                {"field": "id", "function": "count", "alias": "count"},
            ],
            group_by=["fund_id"],
        )

        results = db.execute(stmt).all()
        assert len(results) == 1

    def test_build_query_with_data_quality_filter(
        self, db, tenant_id, reports_user, test_finance_entries
    ):
        """Test building query with data quality filter."""
        builder = ReportQueryBuilder(db, UUID(tenant_id), reports_user.id)

        stmt = builder.build_query(
            entity_type="finance_entries",
            filters={},
            aggregations=[],
            group_by=[],
            data_quality={"verified_status": ["verified", "locked"]},
        )

        results = db.execute(stmt).all()
        assert len(results) == 5

    def test_org_scope_restriction(
        self, db, tenant_id, reports_user, test_org_unit
    ):
        """Test that org scope restrictions are applied."""
        # Create another org unit
        other_org = OrgUnit(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Other Church",
            type="church",
        )
        db.add(other_org)
        db.commit()

        # Create entry in other org unit
        fund = Fund(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="Test Fund",
            active=True,
        )
        db.add(fund)
        db.commit()

        entry = FinanceEntry(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            org_unit_id=other_org.id,
            fund_id=fund.id,
            amount=Decimal("200.00"),
            currency="EUR",
            method="cash",
            verified_status="verified",
            transaction_date=date(2024, 1, 1),
        )
        db.add(entry)
        db.commit()

        builder = ReportQueryBuilder(db, UUID(tenant_id), reports_user.id)

        stmt = builder.build_query(
            entity_type="finance_entries",
            filters={},
            aggregations=[],
            group_by=[],
        )

        results = db.execute(stmt).all()
        # Should only see entries from test_org_unit, not other_org
        assert len(results) == 0  # No entries in test_org_unit yet

    def test_invalid_entity_type(self, db, tenant_id, reports_user):
        """Test that invalid entity type raises error."""
        builder = ReportQueryBuilder(db, UUID(tenant_id), reports_user.id)

        with pytest.raises(ValueError, match="Unknown entity type"):
            builder.build_query(
                entity_type="invalid_entity",
                filters={},
                aggregations=[],
                group_by=[],
            )

