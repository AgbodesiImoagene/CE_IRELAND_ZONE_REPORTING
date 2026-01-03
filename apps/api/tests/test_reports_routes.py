"""Tests for reports API routes."""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.common.models import (
    FinanceEntry,
    Fund,
    OrgAssignment,
    Permission,
    RolePermission,
)
from app.reports.models import ExportJob, ReportTemplate, ReportSchedule


@pytest.fixture
def reports_permissions(db, tenant_id, test_role):
    """Create reports permissions."""
    perms = [
        ("reports.dashboards.read", "Read dashboards"),
        ("reports.query.execute", "Execute queries"),
        ("reports.exports.create", "Create exports"),
        ("reports.templates.create", "Create templates"),
        ("reports.templates.share", "Share templates"),
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
    from app.common.models import User
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
def reports_auth_headers(reports_user):
    """Create auth headers for reports user."""
    from app.auth.utils import create_access_token

    token = create_access_token(
        {"sub": str(reports_user.id), "user_id": str(reports_user.id)}
    )
    return {"Authorization": f"Bearer {token}"}


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


class TestDashboardRoutes:
    """Test dashboard endpoints."""

    def test_get_dashboard_success(
        self, client: TestClient, reports_auth_headers, test_finance_entries
    ):
        """Test getting dashboard data."""
        response = client.get(
            "/api/v1/reports/dashboards/finance",
            headers=reports_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "metadata" in data

    def test_get_dashboard_with_filters(
        self, client: TestClient, reports_auth_headers, test_finance_entries, test_org_unit
    ):
        """Test getting dashboard with filters."""
        response = client.get(
            "/api/v1/reports/dashboards/finance",
            headers=reports_auth_headers,
            params={
                "org_unit_id": str(test_org_unit.id),
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
            },
        )

        assert response.status_code == 200

    def test_get_dashboard_without_permission(
        self, client: TestClient, authenticated_user_token
    ):
        """Test that dashboard requires permission."""
        headers = {"Authorization": f"Bearer {authenticated_user_token}"}
        response = client.get(
            "/api/v1/reports/dashboards/finance",
            headers=headers,
        )

        assert response.status_code == 403


class TestQueryRoutes:
    """Test query endpoints."""

    def test_execute_query_success(
        self, client: TestClient, reports_auth_headers, test_finance_entries
    ):
        """Test executing a query."""
        query = {
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

        response = client.post(
            "/api/v1/reports/query",
            headers=reports_auth_headers,
            json=query,
        )

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "total" in data

    def test_execute_query_with_filters(
        self, client: TestClient, reports_auth_headers, test_finance_entries, test_fund
    ):
        """Test executing query with filters."""
        query = {
            "entity_type": "finance_entries",
            "filters": {"fund_id": str(test_fund.id)},
            "aggregations": [],
            "group_by": [],
            "order_by": [],
        }

        response = client.post(
            "/api/v1/reports/query",
            headers=reports_auth_headers,
            json=query,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 5

    def test_execute_query_without_permission(
        self, client: TestClient, authenticated_user_token
    ):
        """Test that query execution requires permission."""
        headers = {"Authorization": f"Bearer {authenticated_user_token}"}
        query = {
            "entity_type": "finance_entries",
            "filters": {},
        }

        response = client.post(
            "/api/v1/reports/query",
            headers=headers,
            json=query,
        )

        assert response.status_code == 403


class TestExportRoutes:
    """Test export endpoints."""

    def test_create_export_job(
        self, client: TestClient, reports_auth_headers, monkeypatch
    ):
        """Test creating an export job."""
        # Mock the queue
        class MockQueue:
            def enqueue(self, *args, **kwargs):
                pass

        monkeypatch.setattr("app.jobs.queue.exports_queue", MockQueue())

        request = {
            "query": {
                "entity_type": "finance_entries",
                "filters": {},
            },
            "format": "csv",
        }

        response = client.post(
            "/api/v1/reports/exports",
            headers=reports_auth_headers,
            json=request,
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["status"] == "pending"
        assert data["format"] == "csv"

    def test_get_export_status(
        self, client: TestClient, reports_auth_headers, reports_user, db, tenant_id
    ):
        """Test getting export job status."""
        from app.reports.service import ExportService

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

        response = client.get(
            f"/api/v1/reports/exports/{job.id}",
            headers=reports_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(job.id)
        assert data["status"] == "pending"

    def test_create_export_without_permission(
        self, client: TestClient, authenticated_user_token
    ):
        """Test that export creation requires permission."""
        headers = {"Authorization": f"Bearer {authenticated_user_token}"}
        request = {
            "query": {
                "entity_type": "finance_entries",
                "filters": {},
            },
            "format": "csv",
        }

        response = client.post(
            "/api/v1/reports/exports",
            headers=headers,
            json=request,
        )

        assert response.status_code == 403


class TestTemplateRoutes:
    """Test template endpoints."""

    def test_create_template(
        self, client: TestClient, reports_auth_headers
    ):
        """Test creating a template."""
        request = {
            "name": "Test Template",
            "description": "Test description",
            "query_definition": {
                "entity_type": "finance_entries",
                "filters": {},
                "aggregations": [
                    {"field": "amount", "function": "sum", "alias": "total"}
                ],
                "group_by": [],
                "order_by": [],
            },
            "is_shared": False,
        }

        response = client.post(
            "/api/v1/reports/templates",
            headers=reports_auth_headers,
            json=request,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Template"
        assert data["query_definition"]["entity_type"] == "finance_entries"

    def test_list_templates(
        self, client: TestClient, reports_auth_headers, reports_user, db, tenant_id
    ):
        """Test listing templates."""
        from app.reports.service import TemplateService

        # Create a template
        query_definition = {
            "entity_type": "finance_entries",
            "filters": {},
        }

        TemplateService.create_template(
            db=db,
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
            name="My Template",
            query_definition=query_definition,
        )

        response = client.get(
            "/api/v1/reports/templates",
            headers=reports_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) >= 1

    def test_get_template(
        self, client: TestClient, reports_auth_headers, reports_user, db, tenant_id
    ):
        """Test getting a template."""
        from app.reports.service import TemplateService

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

        response = client.get(
            f"/api/v1/reports/templates/{template.id}",
            headers=reports_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(template.id)
        assert data["name"] == "Test Template"

    def test_update_template(
        self, client: TestClient, reports_auth_headers, reports_user, db, tenant_id
    ):
        """Test updating a template."""
        from app.reports.service import TemplateService

        query_definition = {
            "entity_type": "finance_entries",
            "filters": {},
        }

        template = TemplateService.create_template(
            db=db,
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
            name="Original Name",
            query_definition=query_definition,
        )

        request = {
            "name": "Updated Name",
            "description": "Updated description",
            "query_definition": query_definition,
            "is_shared": False,
        }

        response = client.put(
            f"/api/v1/reports/templates/{template.id}",
            headers=reports_auth_headers,
            json=request,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"

    def test_delete_template(
        self, client: TestClient, reports_auth_headers, reports_user, db, tenant_id
    ):
        """Test deleting a template."""
        from app.reports.service import TemplateService

        query_definition = {
            "entity_type": "finance_entries",
            "filters": {},
        }

        template = TemplateService.create_template(
            db=db,
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
            name="To Delete",
            query_definition=query_definition,
        )

        response = client.delete(
            f"/api/v1/reports/templates/{template.id}",
            headers=reports_auth_headers,
        )

        assert response.status_code == 204

        # Verify it's deleted
        from sqlalchemy import select
        deleted = db.execute(
            select(ReportTemplate).where(ReportTemplate.id == template.id)
        ).scalar_one_or_none()
        assert deleted is None

    def test_execute_template(
        self, client: TestClient, reports_auth_headers, reports_user, db, tenant_id, test_finance_entries
    ):
        """Test executing a template."""
        from app.reports.service import TemplateService

        query_definition = {
            "entity_type": "finance_entries",
            "filters": {},
            "aggregations": [],
            "group_by": [],
        }

        template = TemplateService.create_template(
            db=db,
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
            name="Executable Template",
            query_definition=query_definition,
        )

        response = client.post(
            f"/api/v1/reports/templates/{template.id}/execute",
            headers=reports_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "results" in data


class TestScheduleRoutes:
    """Test schedule endpoints."""

    def test_create_schedule(
        self, client: TestClient, reports_auth_headers, reports_user, db, tenant_id
    ):
        """Test creating a schedule."""
        from app.reports.service import TemplateService

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

        request = {
            "frequency": "weekly",
            "day_of_week": 0,
            "time": "09:00:00",
            "recipients": ["recipient@test.com"],
        }

        response = client.post(
            f"/api/v1/reports/templates/{template.id}/schedule",
            headers=reports_auth_headers,
            json=request,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["frequency"] == "weekly"
        assert data["template_id"] == str(template.id)

    def test_list_schedules(
        self, client: TestClient, reports_auth_headers, reports_user, db, tenant_id
    ):
        """Test listing schedules."""
        from app.reports.service import TemplateService, ScheduleService

        # Create template and schedule
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

        ScheduleService.create_schedule(
            db=db,
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
            template_id=template.id,
            frequency="daily",
            time=time(8, 0),
            recipients=["test@example.com"],
        )

        response = client.get(
            "/api/v1/reports/schedules",
            headers=reports_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) >= 1

    def test_delete_schedule(
        self, client: TestClient, reports_auth_headers, reports_user, db, tenant_id
    ):
        """Test deleting a schedule."""
        from app.reports.service import TemplateService, ScheduleService

        # Create template and schedule
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

        schedule = ScheduleService.create_schedule(
            db=db,
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
            template_id=template.id,
            frequency="daily",
            time=time(8, 0),
            recipients=["test@example.com"],
        )

        response = client.delete(
            f"/api/v1/reports/schedules/{schedule.id}",
            headers=reports_auth_headers,
        )

        assert response.status_code == 204

        # Verify it's deleted
        from sqlalchemy import select
        deleted = db.execute(
            select(ReportSchedule).where(ReportSchedule.id == schedule.id)
        ).scalar_one_or_none()
        assert deleted is None

