"""Tests for reports service layer."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.common.models import (
    FinanceEntry,
    Fund,
    OrgAssignment,
    People,
    Permission,
    RolePermission,
)
from app.reports.models import ExportJob, ReportTemplate, ReportSchedule
from app.reports.service import (
    ExportService,
    ReportService,
    ScheduleService,
    TemplateService,
)


@pytest.fixture
def reports_permissions(db, tenant_id, test_role):
    """Create reports permissions."""
    perms = [
        ("reports.dashboards.read", "Read dashboards"),
        ("reports.query.execute", "Execute queries"),
        ("reports.exports.create", "Create exports"),
        ("reports.templates.create", "Create templates"),
        ("reports.schedules.create", "Create schedules"),
    ]

    created_perms = []
    for code, desc in perms:
        perm = Permission(id=uuid4(), code=code, description=desc)
        db.add(perm)
        db.flush()
        created_perms.append(perm)

        role_perm = RolePermission(role_id=test_role.id, permission_id=perm.id)
        db.add(role_perm)

    db.commit()
    return created_perms


@pytest.fixture
def reports_user(db, tenant_id, test_role, test_org_unit, reports_permissions):
    """Create a user with reports permissions."""
    from app.common.models import User, OrgAssignment
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

    assignment = OrgAssignment(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        user_id=user.id,
        org_unit_id=test_org_unit.id,
        role_id=test_role.id,
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


class TestReportService:
    """Test report service."""

    def test_execute_query(
        self, db, tenant_id, reports_user, test_finance_entries
    ):
        """Test executing a query."""
        query_request = {
            "entity_type": "finance_entries",
            "filters": {},
            "aggregations": [
                {"field": "amount", "function": "sum", "alias": "total"}
            ],
            "group_by": [],
            "order_by": [],
            "limit": 1000,
            "offset": 0,
        }

        result = ReportService.execute_query(
            db=db,
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
            query_request=query_request,
        )

        assert "results" in result
        assert "total" in result
        assert result["total"] >= 0

    def test_execute_query_with_filters(
        self, db, tenant_id, reports_user, test_finance_entries, test_fund
    ):
        """Test executing query with filters."""
        query_request = {
            "entity_type": "finance_entries",
            "filters": {"fund_id": str(test_fund.id)},
            "aggregations": [],
            "group_by": [],
            "order_by": [],
            "limit": 1000,
            "offset": 0,
        }

        result = ReportService.execute_query(
            db=db,
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
            query_request=query_request,
        )

        assert len(result["results"]) == 5

    def test_execute_query_without_permission(
        self, db, tenant_id, test_org_unit, test_fund
    ):
        """Test that query execution requires permission."""
        # Create a user with a role that has NO permissions
        # Use a separate role to avoid conflicts with reports_permissions fixture
        from app.common.models import User, Role, OrgAssignment
        from app.auth.utils import hash_password

        # Create a role with no permissions
        no_perm_role = Role(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="No Permission Role",
        )
        db.add(no_perm_role)
        db.flush()

        # Create user with this role
        user = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="noperm@test.com",
            password_hash=hash_password("testpass123"),
            is_active=True,
        )
        db.add(user)
        db.flush()

        assignment = OrgAssignment(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=user.id,
            org_unit_id=test_org_unit.id,
            role_id=no_perm_role.id,
            scope_type="self",
        )
        db.add(assignment)
        db.commit()

        query_request = {
            "entity_type": "finance_entries",
            "filters": {},
            "aggregations": [],
            "group_by": [],
            "order_by": [],
            "limit": 1000,
            "offset": 0,
        }

        with pytest.raises(ValueError, match="lacks required permission"):
            ReportService.execute_query(
                db=db,
                tenant_id=UUID(tenant_id),
                user_id=user.id,
                query_request=query_request,
            )

    def test_get_dashboard(
        self, db, tenant_id, reports_user, test_finance_entries
    ):
        """Test getting dashboard data."""
        result = ReportService.get_dashboard(
            db=db,
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
            dashboard_type="finance",
        )

        assert "results" in result
        assert "metadata" in result


class TestExportService:
    """Test export service."""

    def test_create_export_job(self, db, tenant_id, reports_user):
        """Test creating an export job."""
        query_definition = {
            "entity_type": "finance_entries",
            "filters": {},
            "aggregations": [],
            "group_by": [],
        }

        job = ExportService.create_export_job(
            db=db,
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
            format="csv",
            query_definition=query_definition,
        )

        assert job.id is not None
        assert job.status == "pending"
        assert job.format == "csv"
        assert job.query_definition == query_definition

    def test_get_export_status(self, db, tenant_id, reports_user):
        """Test getting export job status."""
        query_definition = {
            "entity_type": "finance_entries",
            "filters": {},
        }

        job = ExportService.create_export_job(
            db=db,
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
            format="csv",
            query_definition=query_definition,
        )

        retrieved = ExportService.get_export_status(
            db=db,
            export_id=job.id,
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
        )

        assert retrieved is not None
        assert retrieved.id == job.id

    def test_create_export_without_permission(
        self, db, tenant_id, test_org_unit
    ):
        """Test that export creation requires permission."""
        # Create a user with a role that has NO permissions
        # Use a separate role to avoid conflicts with reports_permissions fixture
        from app.common.models import User, Role, OrgAssignment
        from app.auth.utils import hash_password

        # Create a role with no permissions
        no_perm_role = Role(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            name="No Permission Role",
        )
        db.add(no_perm_role)
        db.flush()

        # Create user with this role
        user = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="noperm@test.com",
            password_hash=hash_password("testpass123"),
            is_active=True,
        )
        db.add(user)
        db.flush()

        assignment = OrgAssignment(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=user.id,
            org_unit_id=test_org_unit.id,
            role_id=no_perm_role.id,
            scope_type="self",
        )
        db.add(assignment)
        db.commit()

        query_definition = {
            "entity_type": "finance_entries",
            "filters": {},
        }

        with pytest.raises(ValueError, match="lacks required permission"):
            ExportService.create_export_job(
                db=db,
                tenant_id=UUID(tenant_id),
                user_id=user.id,
                format="csv",
                query_definition=query_definition,
            )


class TestTemplateService:
    """Test template service."""

    def test_create_template(self, db, tenant_id, reports_user):
        """Test creating a template."""
        query_definition = {
            "entity_type": "finance_entries",
            "filters": {},
            "aggregations": [
                {"field": "amount", "function": "sum", "alias": "total"}
            ],
            "group_by": [],
        }

        template = TemplateService.create_template(
            db=db,
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
            name="Test Template",
            query_definition=query_definition,
            description="Test description",
        )

        assert template.id is not None
        assert template.name == "Test Template"
        assert template.query_definition == query_definition

    def test_list_templates(self, db, tenant_id, reports_user):
        """Test listing templates."""
        # Create a template
        query_definition = {
            "entity_type": "finance_entries",
            "filters": {},
        }

        template = TemplateService.create_template(
            db=db,
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
            name="My Template",
            query_definition=query_definition,
        )

        templates = TemplateService.list_templates(
            db=db,
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
        )

        assert len(templates) >= 1
        assert any(t.id == template.id for t in templates)

    def test_get_template(self, db, tenant_id, reports_user):
        """Test getting a template."""
        query_definition = {
            "entity_type": "finance_entries",
            "filters": {},
        }

        template = TemplateService.create_template(
            db=db,
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
            name="Test Template",
            query_definition=query_definition,
        )

        retrieved = TemplateService.get_template(
            db=db,
            template_id=template.id,
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
        )

        assert retrieved is not None
        assert retrieved.id == template.id

    def test_get_template_access_denied(
        self, db, tenant_id, reports_user, test_user
    ):
        """Test that users can't access templates they don't own."""
        query_definition = {
            "entity_type": "finance_entries",
            "filters": {},
        }

        template = TemplateService.create_template(
            db=db,
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
            name="Private Template",
            query_definition=query_definition,
            is_shared=False,
        )

        retrieved = TemplateService.get_template(
            db=db,
            template_id=template.id,
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
        )

        assert retrieved is None


class TestScheduleService:
    """Test schedule service."""

    def test_create_schedule(self, db, tenant_id, reports_user):
        """Test creating a schedule."""
        # Create a template first
        query_definition = {
            "entity_type": "finance_entries",
            "filters": {},
        }

        template = TemplateService.create_template(
            db=db,
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
            name="Scheduled Template",
            query_definition=query_definition,
        )

        schedule = ScheduleService.create_schedule(
            db=db,
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
            template_id=template.id,
            frequency="weekly",
            time=time(9, 0),
            recipients=["recipient@test.com"],
            day_of_week=0,  # Monday
        )

        assert schedule.id is not None
        assert schedule.frequency == "weekly"
        assert schedule.template_id == template.id
        assert schedule.is_active is True

    def test_list_schedules(self, db, tenant_id, reports_user):
        """Test listing schedules."""
        # Create a template
        query_definition = {
            "entity_type": "finance_entries",
            "filters": {},
        }

        template = TemplateService.create_template(
            db=db,
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
            name="Template",
            query_definition=query_definition,
        )

        # Create a schedule
        schedule = ScheduleService.create_schedule(
            db=db,
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
            template_id=template.id,
            frequency="daily",
            time=time(8, 0),
            recipients=["test@example.com"],
        )

        schedules = ScheduleService.list_schedules(
            db=db,
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
        )

        assert len(schedules) >= 1
        assert any(s.id == schedule.id for s in schedules)

