"""Tests for Cells API routes."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi import status

from app.common.models import Cell, CellReport, People, Fund, Permission, RolePermission


@pytest.fixture
def cells_permissions(db, tenant_id, test_role):
    """Create cells permissions."""
    perms = [
        ("cells.manage", "Manage cells"),
        ("cells.reports.create", "Create cell reports"),
        ("cells.reports.update", "Update cell reports"),
        ("cells.reports.delete", "Delete cell reports"),
        ("cells.reports.approve", "Approve cell reports"),
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
def test_cell(db, tenant_id, test_org_unit, test_user, cells_permissions):
    """Create a test cell."""
    from app.cells.service import CellService

    # cells_permissions fixture already assigns permissions to test_role
    # and test_user has test_role, so test_user should have cells.manage
    cell = CellService.create_cell(
        db=db,
        creator_id=test_user.id,
        tenant_id=UUID(tenant_id),
        org_unit_id=test_org_unit.id,
        name="Test Cell",
        status="active",
    )
    return cell


@pytest.fixture
def auth_headers(db, test_user, cells_permissions, test_role):
    """Create auth headers for test user with cells permissions."""
    from app.auth.utils import create_access_token
    from app.common.models import RolePermission

    # Assign all cells permissions to test_role
    for perm in cells_permissions:
        existing = (
            db.query(RolePermission)
            .filter(
                RolePermission.role_id == test_role.id,
                RolePermission.permission_id == perm.id,
            )
            .first()
        )
        if not existing:
            role_perm = RolePermission(
                role_id=test_role.id,
                permission_id=perm.id,
            )
            db.add(role_perm)
    db.commit()

    token = create_access_token(
        {"sub": str(test_user.id), "user_id": str(test_user.id)}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_fund(db, tenant_id):
    """Create a test offering fund."""
    fund = Fund(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        name="Offering",
        is_partnership=False,
        active=True,
    )
    db.add(fund)
    db.commit()
    db.refresh(fund)
    return fund


def test_create_cell(client, test_user, test_org_unit, cells_permissions, auth_headers):
    """Test creating a cell via API."""
    response = client.post(
        "/api/v1/cells",
        json={
            "org_unit_id": str(test_org_unit.id),
            "name": "New Cell",
            "status": "active",
        },
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == "New Cell"
    assert data["status"] == "active"
    assert "id" in data


def test_get_cell(client, test_cell, auth_headers):
    """Test getting a cell via API."""
    response = client.get(
        f"/api/v1/cells/{test_cell.id}",
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == str(test_cell.id)
    assert data["name"] == test_cell.name


def test_list_cells(client, test_cell, auth_headers):
    """Test listing cells via API."""
    response = client.get(
        "/api/v1/cells",
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(c["id"] == str(test_cell.id) for c in data)


def test_update_cell(client, test_cell, auth_headers):
    """Test updating a cell via API."""
    response = client.patch(
        f"/api/v1/cells/{test_cell.id}",
        json={"name": "Updated Cell"},
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["name"] == "Updated Cell"


def test_create_cell_report(client, test_cell, auth_headers):
    """Test creating a cell report via API."""
    response = client.post(
        "/api/v1/cells/cell-reports",
        json={
            "cell_id": str(test_cell.id),
            "report_date": date.today().isoformat(),
            "attendance": 10,
            "first_timers": 2,
            "offerings_total": "50.00",
            "meeting_type": "bible_study",
        },
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["cell_id"] == str(test_cell.id)
    assert data["attendance"] == 10
    assert data["status"] == "submitted"


def test_get_cell_report(client, test_cell, test_user, db, tenant_id, auth_headers):
    """Test getting a cell report via API."""
    from app.cells.service import CellReportService

    report = CellReportService.create_report(
        db=db,
        creator_id=test_user.id,
        tenant_id=UUID(tenant_id),
        cell_id=test_cell.id,
        report_date=date.today(),
        meeting_type="bible_study",
    )

    response = client.get(
        f"/api/v1/cells/cell-reports/{report.id}",
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == str(report.id)


def test_update_cell_report(client, test_cell, test_user, db, tenant_id, auth_headers):
    """Test updating a cell report via API."""
    from app.cells.service import CellReportService

    report = CellReportService.create_report(
        db=db,
        creator_id=test_user.id,
        tenant_id=UUID(tenant_id),
        cell_id=test_cell.id,
        report_date=date.today(),
        attendance=10,
        meeting_type="bible_study",
    )

    response = client.patch(
        f"/api/v1/cells/cell-reports/{report.id}",
        json={"attendance": 15},
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["attendance"] == 15


def test_approve_cell_report(client, test_cell, test_user, db, tenant_id, auth_headers):
    """Test approving a cell report via API."""
    from app.cells.service import CellReportService

    report = CellReportService.create_report(
        db=db,
        creator_id=test_user.id,
        tenant_id=UUID(tenant_id),
        cell_id=test_cell.id,
        report_date=date.today(),
        meeting_type="bible_study",
    )

    response = client.post(
        f"/api/v1/cells/cell-reports/{report.id}/approve",
        json={"status": "approved"},
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "approved"

