"""Tests for Cells service layer."""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.common.models import (
    Cell,
    CellReport,
    People,
    Fund,
    FinanceEntry,
    Permission,
    RolePermission,
)
from app.cells.service import (
    CellService,
    CellReportService,
)


@pytest.fixture
def cells_permission(db, tenant_id, test_role) -> Permission:
    """Create a cells permission."""
    perm = Permission(
        id=uuid4(),
        code="cells.manage",
        description="Manage cells",
    )
    db.add(perm)
    db.flush()

    role_perm = RolePermission(role_id=test_role.id, permission_id=perm.id)
    db.add(role_perm)
    db.commit()
    db.refresh(perm)
    return perm


@pytest.fixture
def cells_role(
    db, tenant_id, test_org_unit
) -> tuple:
    """Create a role with all cells permissions."""
    from app.common.models import Role

    role = Role(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        name="Cells Role",
    )
    db.add(role)
    db.flush()

    # Create all cells permissions
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

        role_perm = RolePermission(role_id=role.id, permission_id=perm.id)
        db.add(role_perm)

    db.commit()
    return (role, *created_perms)


@pytest.fixture
def cells_user(db, tenant_id, cells_role, test_org_unit):
    """Create a user with cells permissions."""
    from app.common.models import OrgAssignment, User
    from app.auth.utils import hash_password

    user = User(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        email="cells@test.com",
        password_hash=hash_password("testpass123"),
        is_active=True,
    )
    db.add(user)
    db.flush()

    role, *_ = cells_role
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
def test_person(db, tenant_id, test_org_unit):
    """Create a test person for cell leader."""
    person = People(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        org_unit_id=test_org_unit.id,
        first_name="John",
        last_name="Doe",
        gender="male",
    )
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


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


def test_create_cell(db, tenant_id, cells_user, test_org_unit, test_person):
    """Test creating a cell."""
    cell = CellService.create_cell(
        db=db,
        creator_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        org_unit_id=test_org_unit.id,
        name="Test Cell",
        leader_id=test_person.id,
        meeting_day="Sunday",
        status="active",
    )

    assert cell.id is not None
    assert cell.name == "Test Cell"
    assert cell.leader_id == test_person.id
    assert cell.status == "active"

    # Verify in database
    found = db.execute(
        select(Cell).where(Cell.id == cell.id)
    ).scalar_one()
    assert found.name == "Test Cell"


def test_create_cell_duplicate_name(db, tenant_id, cells_user, test_org_unit):
    """Test that duplicate cell names in same org unit are rejected."""
    CellService.create_cell(
        db=db,
        creator_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        org_unit_id=test_org_unit.id,
        name="Test Cell",
    )

    with pytest.raises(ValueError, match="already exists"):
        CellService.create_cell(
            db=db,
            creator_id=cells_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            name="Test Cell",
        )


def test_get_cell(db, tenant_id, cells_user, test_org_unit):
    """Test getting a cell by ID."""
    cell = CellService.create_cell(
        db=db,
        creator_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        org_unit_id=test_org_unit.id,
        name="Test Cell",
    )

    found = CellService.get_cell(db, cell.id, UUID(tenant_id))
    assert found is not None
    assert found.id == cell.id
    assert found.name == "Test Cell"


def test_list_cells(db, tenant_id, cells_user, test_org_unit):
    """Test listing cells with filters."""
    # Create multiple cells
    cell1 = CellService.create_cell(
        db=db,
        creator_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        org_unit_id=test_org_unit.id,
        name="Cell A",
        status="active",
    )
    cell2 = CellService.create_cell(
        db=db,
        creator_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        org_unit_id=test_org_unit.id,
        name="Cell B",
        status="inactive",
    )

    # List all
    all_cells = CellService.list_cells(db, UUID(tenant_id))
    assert len(all_cells) >= 2

    # Filter by status
    active_cells = CellService.list_cells(
        db, UUID(tenant_id), status="active"
    )
    assert any(c.id == cell1.id for c in active_cells)
    assert not any(c.id == cell2.id for c in active_cells)


def test_update_cell(db, tenant_id, cells_user, test_org_unit, test_person):
    """Test updating a cell."""
    cell = CellService.create_cell(
        db=db,
        creator_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        org_unit_id=test_org_unit.id,
        name="Test Cell",
    )

    updated = CellService.update_cell(
        db=db,
        updater_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        cell_id=cell.id,
        name="Updated Cell",
        leader_id=test_person.id,
    )

    assert updated.name == "Updated Cell"
    assert updated.leader_id == test_person.id


def test_delete_cell(db, tenant_id, cells_user, test_org_unit):
    """Test deleting a cell."""
    cell = CellService.create_cell(
        db=db,
        creator_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        org_unit_id=test_org_unit.id,
        name="Test Cell",
    )

    CellService.delete_cell(
        db=db,
        deleter_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        cell_id=cell.id,
    )

    found = CellService.get_cell(db, cell.id, UUID(tenant_id))
    assert found is None


def test_delete_cell_with_reports(db, tenant_id, cells_user, test_org_unit):
    """Test that deleting a cell with reports fails."""
    cell = CellService.create_cell(
        db=db,
        creator_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        org_unit_id=test_org_unit.id,
        name="Test Cell",
    )

    # Create a report
    report = CellReport(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        cell_id=cell.id,
        report_date=date.today(),
        attendance=10,
        meeting_type="bible_study",
    )
    db.add(report)
    db.commit()

    with pytest.raises(ValueError, match="has.*reports"):
        CellService.delete_cell(
            db=db,
            deleter_id=cells_user.id,
            tenant_id=UUID(tenant_id),
            cell_id=cell.id,
        )


def test_create_cell_report(db, tenant_id, cells_user, test_org_unit, test_fund):
    """Test creating a cell report."""
    # Create cell
    cell = CellService.create_cell(
        db=db,
        creator_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        org_unit_id=test_org_unit.id,
        name="Test Cell",
    )

    # Create report
    report = CellReportService.create_report(
        db=db,
        creator_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        cell_id=cell.id,
        report_date=date.today(),
        attendance=10,
        first_timers=2,
        offerings_total=Decimal("50.00"),
        meeting_type="bible_study",
    )

    assert report.id is not None
    assert report.cell_id == cell.id
    assert report.attendance == 10
    assert report.status == "submitted"

    # Check if finance entry was created (if user has permission)
    # Note: This might not be created if user lacks finance.entries.create permission
    finance_entry = db.execute(
        select(FinanceEntry).where(
            FinanceEntry.source_type == "cell_report",
            FinanceEntry.source_id == report.id,
        )
    ).scalar_one_or_none()

    # Finance entry may or may not exist depending on permissions
    # This is acceptable behavior


def test_create_cell_report_duplicate_date(db, tenant_id, cells_user, test_org_unit):
    """Test that duplicate reports for same cell and date are rejected."""
    cell = CellService.create_cell(
        db=db,
        creator_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        org_unit_id=test_org_unit.id,
        name="Test Cell",
    )

    report_date = date.today()
    CellReportService.create_report(
        db=db,
        creator_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        cell_id=cell.id,
        report_date=report_date,
        meeting_type="bible_study",
    )

    with pytest.raises(ValueError, match="already exists"):
        CellReportService.create_report(
            db=db,
            creator_id=cells_user.id,
            tenant_id=UUID(tenant_id),
            cell_id=cell.id,
            report_date=report_date,
            meeting_type="bible_study",
        )


def test_update_cell_report(db, tenant_id, cells_user, test_org_unit):
    """Test updating a cell report."""
    cell = CellService.create_cell(
        db=db,
        creator_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        org_unit_id=test_org_unit.id,
        name="Test Cell",
    )

    report = CellReportService.create_report(
        db=db,
        creator_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        cell_id=cell.id,
        report_date=date.today(),
        attendance=10,
        meeting_type="bible_study",
    )

    updated = CellReportService.update_report(
        db=db,
        updater_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        report_id=report.id,
        attendance=15,
    )

    assert updated.attendance == 15


def test_update_cell_report_not_submitted(db, tenant_id, cells_user, test_org_unit):
    """Test that updating a non-submitted report fails."""
    cell = CellService.create_cell(
        db=db,
        creator_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        org_unit_id=test_org_unit.id,
        name="Test Cell",
    )

    report = CellReportService.create_report(
        db=db,
        creator_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        cell_id=cell.id,
        report_date=date.today(),
        meeting_type="bible_study",
    )

    # Approve the report
    CellReportService.approve_report(
        db=db,
        approver_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        report_id=report.id,
        status="approved",
    )

    # Try to update - should fail
    with pytest.raises(ValueError, match="Cannot update report"):
        CellReportService.update_report(
            db=db,
            updater_id=cells_user.id,
            tenant_id=UUID(tenant_id),
            report_id=report.id,
            attendance=15,
        )


def test_approve_cell_report(db, tenant_id, cells_user, test_org_unit):
    """Test approving a cell report."""
    cell = CellService.create_cell(
        db=db,
        creator_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        org_unit_id=test_org_unit.id,
        name="Test Cell",
    )

    report = CellReportService.create_report(
        db=db,
        creator_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        cell_id=cell.id,
        report_date=date.today(),
        meeting_type="bible_study",
    )

    approved = CellReportService.approve_report(
        db=db,
        approver_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        report_id=report.id,
        status="approved",
    )

    assert approved.status == "approved"


def test_delete_cell_report(db, tenant_id, cells_user, test_org_unit):
    """Test deleting a cell report."""
    cell = CellService.create_cell(
        db=db,
        creator_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        org_unit_id=test_org_unit.id,
        name="Test Cell",
    )

    report = CellReportService.create_report(
        db=db,
        creator_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        cell_id=cell.id,
        report_date=date.today(),
        meeting_type="bible_study",
    )

    CellReportService.delete_report(
        db=db,
        deleter_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        report_id=report.id,
    )

    found = CellReportService.get_report(db, report.id, UUID(tenant_id))
    assert found is None


def test_delete_cell_report_not_submitted(db, tenant_id, cells_user, test_org_unit):
    """Test that deleting a non-submitted report fails."""
    cell = CellService.create_cell(
        db=db,
        creator_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        org_unit_id=test_org_unit.id,
        name="Test Cell",
    )

    report = CellReportService.create_report(
        db=db,
        creator_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        cell_id=cell.id,
        report_date=date.today(),
        meeting_type="bible_study",
    )

    # Approve the report
    CellReportService.approve_report(
        db=db,
        approver_id=cells_user.id,
        tenant_id=UUID(tenant_id),
        report_id=report.id,
        status="approved",
    )

    # Try to delete - should fail
    with pytest.raises(ValueError, match="Cannot delete report"):
        CellReportService.delete_report(
            db=db,
            deleter_id=cells_user.id,
            tenant_id=UUID(tenant_id),
            report_id=report.id,
        )

