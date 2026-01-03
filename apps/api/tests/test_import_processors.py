"""Tests for import entity processors."""

from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.common.models import (
    People,
    Service,
    FirstTimer,
    Attendance,
    Permission,
    RolePermission,
    Cell,
    CellReport,
    FinanceEntry,
    Fund,
)
from app.imports.processors import (
    PeopleProcessor,
    MembershipProcessor,
    FirstTimerProcessor,
    ServiceProcessor,
    AttendanceProcessor,
    CellProcessor,
    CellReportProcessor,
    FinanceEntryProcessor,
    get_processor,
    ProcessResult,
)


@pytest.fixture
def import_permissions(db, tenant_id, test_role):
    """Create import permissions."""
    perms = [
        ("imports.create", "Create imports"),
        ("imports.execute", "Execute imports"),
        ("registry.people.create", "Create people"),
        ("registry.firsttimers.create", "Create first timers"),
        ("registry.attendance.create", "Create attendance"),
        ("cells.manage", "Manage cells"),
        ("cells.reports.create", "Create cell reports"),
        ("finance.entries.create", "Create finance entries"),
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
def test_fund(db, tenant_id):
    """Create a test fund."""
    fund = Fund(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        name="Tithe",
        is_partnership=False,
        active=True,
    )
    db.add(fund)
    db.commit()
    db.refresh(fund)
    return fund


class TestPeopleProcessor:
    """Tests for People processor."""

    def test_process_row_create(self, db, tenant_id, test_user, test_org_unit, import_permissions):
        """Test processing a row to create a person."""
        processor = PeopleProcessor()
        row = {
            "_row_number": 1,
            "first_name": "John",
            "last_name": "Doe",
            "gender": "male",
            "email": "john@test.com",
            "phone": "1234567890",
        }
        mapping = {
            "first_name": "first_name",
            "last_name": "last_name",
            "gender": "gender",
            "email": "email",
            "phone": "phone",
        }

        result = processor.process_row(
            db=db,
            row=row,
            mapping=mapping,
            mode="create_only",
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
            org_unit_id=test_org_unit.id,
        )

        assert result.success
        assert result.entity_id is not None

        # Verify person was created
        person = db.get(People, result.entity_id)
        assert person is not None
        assert person.first_name == "John"
        assert person.last_name == "Doe"
        assert person.email == "john@test.com"

    def test_process_row_missing_required(self, db, tenant_id, test_user, test_org_unit, import_permissions):
        """Test processing a row with missing required fields."""
        processor = PeopleProcessor()
        row = {"_row_number": 1, "first_name": "John"}  # Missing last_name and gender
        mapping = {"first_name": "first_name"}

        result = processor.process_row(
            db=db,
            row=row,
            mapping=mapping,
            mode="create_only",
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
            org_unit_id=test_org_unit.id,
        )

        assert not result.success
        assert len(result.errors) > 0

    def test_process_row_update_existing(self, db, tenant_id, test_user, test_org_unit, import_permissions):
        """Test processing a row to update existing person."""
        # Create existing person
        from app.registry.service import PeopleService

        existing_person = PeopleService.create_person(
            db=db,
            creator_id=test_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            first_name="John",
            last_name="Doe",
            gender="male",
            email="john@test.com",
        )

        processor = PeopleProcessor()
        row = {
            "_row_number": 1,
            "email": "john@test.com",
            "first_name": "John Updated",
            "last_name": "Doe",
            "gender": "male",
        }
        mapping = {
            "email": "email",
            "first_name": "first_name",
            "last_name": "last_name",
            "gender": "gender",
        }

        result = processor.process_row(
            db=db,
            row=row,
            mapping=mapping,
            mode="update_existing",
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
            org_unit_id=test_org_unit.id,
        )

        assert result.success
        assert result.entity_id == existing_person.id

        # Verify person was updated
        db.refresh(existing_person)
        assert existing_person.first_name == "John Updated"


class TestFirstTimerProcessor:
    """Tests for FirstTimer processor."""

    def test_process_row_create(self, db, tenant_id, test_user, test_org_unit, import_permissions):
        """Test processing a row to create a first timer."""
        # Create a service first
        from app.registry.service import ServiceService

        service = ServiceService.create_service(
            db=db,
            creator_id=test_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            name="Sunday Service",
            service_date=date.today(),
        )

        processor = FirstTimerProcessor()
        row = {
            "_row_number": 1,
            "service_id": str(service.id),
            "source": "Friend",
            "notes": "First visit",
        }
        mapping = {
            "service_id": "service_id",
            "source": "source",
            "notes": "notes",
        }

        result = processor.process_row(
            db=db,
            row=row,
            mapping=mapping,
            mode="create_only",
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
        )

        assert result.success
        assert result.entity_id is not None

        # Verify first timer was created
        first_timer = db.get(FirstTimer, result.entity_id)
        assert first_timer is not None
        assert first_timer.source == "Friend"


class TestServiceProcessor:
    """Tests for Service processor."""

    def test_process_row_create(self, db, tenant_id, test_user, test_org_unit, import_permissions):
        """Test processing a row to create a service."""
        processor = ServiceProcessor()
        row = {
            "_row_number": 1,
            "name": "Sunday Service",
            "service_date": "2024-01-15",
            "service_time": "10:00",
        }
        mapping = {
            "name": "name",
            "service_date": "service_date",
            "service_time": "service_time",
        }

        result = processor.process_row(
            db=db,
            row=row,
            mapping=mapping,
            mode="create_only",
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
            org_unit_id=test_org_unit.id,
        )

        assert result.success
        assert result.entity_id is not None

        # Verify service was created
        service = db.get(Service, result.entity_id)
        assert service is not None
        assert service.name == "Sunday Service"


class TestAttendanceProcessor:
    """Tests for Attendance processor."""

    def test_process_row_create(self, db, tenant_id, test_user, test_org_unit, import_permissions):
        """Test processing a row to create attendance."""
        # Create a service first
        from app.registry.service import ServiceService

        service = ServiceService.create_service(
            db=db,
            creator_id=test_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            name="Sunday Service",
            service_date=date.today(),
        )

        processor = AttendanceProcessor()
        row = {
            "_row_number": 1,
            "service_id": str(service.id),
            "men_count": "50",
            "women_count": "60",
            "teens_count": "20",
            "kids_count": "30",
        }
        mapping = {
            "service_id": "service_id",
            "men_count": "men_count",
            "women_count": "women_count",
            "teens_count": "teens_count",
            "kids_count": "kids_count",
        }

        result = processor.process_row(
            db=db,
            row=row,
            mapping=mapping,
            mode="create_only",
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
        )

        assert result.success
        assert result.entity_id is not None

        # Verify attendance was created
        attendance = db.get(Attendance, result.entity_id)
        assert attendance is not None
        assert attendance.men_count == 50
        assert attendance.women_count == 60


class TestCellProcessor:
    """Tests for Cell processor."""

    def test_process_row_create(
        self, db, tenant_id, test_user, test_org_unit, import_permissions
    ):
        """Test processing a row to create a cell."""
        processor = CellProcessor()
        row = {
            "_row_number": 1,
            "name": "Alpha Cell",
            "venue": "Room 101",
            "meeting_day": "Monday",
            "meeting_time": "19:00",
            "status": "active",
        }
        mapping = {
            "name": "name",
            "venue": "venue",
            "meeting_day": "meeting_day",
            "meeting_time": "meeting_time",
            "status": "status",
        }

        result = processor.process_row(
            db=db,
            row=row,
            mapping=mapping,
            mode="create_only",
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
            org_unit_id=test_org_unit.id,
        )

        assert result.success
        assert result.entity_id is not None

        # Verify cell was created
        cell = db.get(Cell, result.entity_id)
        assert cell is not None
        assert cell.name == "Alpha Cell"
        assert cell.venue == "Room 101"
        assert cell.status == "active"

    def test_process_row_missing_required(
        self, db, tenant_id, test_user, test_org_unit, import_permissions
    ):
        """Test processing a row with missing required fields."""
        processor = CellProcessor()
        row = {"_row_number": 1}  # Missing name
        mapping = {}

        result = processor.process_row(
            db=db,
            row=row,
            mapping=mapping,
            mode="create_only",
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
            org_unit_id=test_org_unit.id,
        )

        assert not result.success
        assert len(result.errors) > 0

    def test_process_row_with_leader(
        self, db, tenant_id, test_user, test_org_unit, import_permissions
    ):
        """Test processing a row with leader reference."""
        # Create a person to be the leader
        from app.registry.service import PeopleService

        leader = PeopleService.create_person(
            db=db,
            creator_id=test_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            first_name="John",
            last_name="Leader",
            gender="male",
        )

        processor = CellProcessor()
        row = {
            "_row_number": 1,
            "name": "Beta Cell",
            "leader_id": str(leader.id),
        }
        mapping = {
            "name": "name",
            "leader_id": "leader_id",
        }

        result = processor.process_row(
            db=db,
            row=row,
            mapping=mapping,
            mode="create_only",
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
            org_unit_id=test_org_unit.id,
        )

        assert result.success
        cell = db.get(Cell, result.entity_id)
        assert cell.leader_id == leader.id


class TestCellReportProcessor:
    """Tests for CellReport processor."""

    def test_process_row_create(
        self,
        db,
        tenant_id,
        test_user,
        test_org_unit,
        import_permissions,
    ):
        """Test processing a row to create a cell report."""
        # Create a cell first
        from app.cells.service import CellService

        cell = CellService.create_cell(
            db=db,
            creator_id=test_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            name="Gamma Cell",
        )

        processor = CellReportProcessor()
        row = {
            "_row_number": 1,
            "cell_id": str(cell.id),
            "report_date": "2024-01-15",
            "attendance": "15",
            "first_timers": "2",
            "new_converts": "1",
            "offerings_total": "50.00",
            "meeting_type": "bible_study",
        }
        mapping = {
            "cell_id": "cell_id",
            "report_date": "report_date",
            "attendance": "attendance",
            "first_timers": "first_timers",
            "new_converts": "new_converts",
            "offerings_total": "offerings_total",
            "meeting_type": "meeting_type",
        }

        result = processor.process_row(
            db=db,
            row=row,
            mapping=mapping,
            mode="create_only",
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
        )

        assert result.success
        assert result.entity_id is not None

        # Verify cell report was created
        report = db.get(CellReport, result.entity_id)
        assert report is not None
        assert report.cell_id == cell.id
        assert report.attendance == 15
        assert report.first_timers == 2
        assert report.new_converts == 1
        assert float(report.offerings_total) == 50.00

    def test_process_row_missing_required(
        self, db, tenant_id, test_user, test_org_unit, import_permissions
    ):
        """Test processing a row with missing required fields."""
        processor = CellReportProcessor()
        row = {"_row_number": 1}  # Missing cell_id and report_date
        mapping = {}

        result = processor.process_row(
            db=db,
            row=row,
            mapping=mapping,
            mode="create_only",
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
        )

        assert not result.success
        assert len(result.errors) > 0


class TestFinanceEntryProcessor:
    """Tests for FinanceEntry processor."""

    def test_process_row_create(
        self,
        db,
        tenant_id,
        test_user,
        test_org_unit,
        import_permissions,
        test_fund,
    ):
        """Test processing a row to create a finance entry."""
        processor = FinanceEntryProcessor()
        row = {
            "_row_number": 1,
            "fund_id": str(test_fund.id),
            "amount": "100.50",
            "transaction_date": "2024-01-15",
            "method": "cash",
            "currency": "EUR",
            "external_giver_name": "Anonymous Donor",
        }
        mapping = {
            "fund_id": "fund_id",
            "amount": "amount",
            "transaction_date": "transaction_date",
            "method": "method",
            "currency": "currency",
            "external_giver_name": "external_giver_name",
        }

        result = processor.process_row(
            db=db,
            row=row,
            mapping=mapping,
            mode="create_only",
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
            org_unit_id=test_org_unit.id,
        )

        assert result.success
        assert result.entity_id is not None

        # Verify finance entry was created
        entry = db.get(FinanceEntry, result.entity_id)
        assert entry is not None
        assert entry.fund_id == test_fund.id
        assert float(entry.amount) == 100.50
        assert entry.external_giver_name == "Anonymous Donor"
        assert entry.method == "cash"
        assert entry.currency == "EUR"

    def test_process_row_with_person(
        self,
        db,
        tenant_id,
        test_user,
        test_org_unit,
        import_permissions,
        test_fund,
    ):
        """Test processing a row with person reference."""
        # Create a person
        from app.registry.service import PeopleService

        person = PeopleService.create_person(
            db=db,
            creator_id=test_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            first_name="Jane",
            last_name="Donor",
            gender="female",
        )

        processor = FinanceEntryProcessor()
        row = {
            "_row_number": 1,
            "fund_id": str(test_fund.id),
            "amount": "200.00",
            "transaction_date": "2024-01-15",
            "person_id": str(person.id),
            "method": "bank_transfer",
        }
        mapping = {
            "fund_id": "fund_id",
            "amount": "amount",
            "transaction_date": "transaction_date",
            "person_id": "person_id",
            "method": "method",
        }

        result = processor.process_row(
            db=db,
            row=row,
            mapping=mapping,
            mode="create_only",
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
            org_unit_id=test_org_unit.id,
        )

        assert result.success
        entry = db.get(FinanceEntry, result.entity_id)
        assert entry.person_id == person.id

    def test_process_row_missing_required(
        self,
        db,
        tenant_id,
        test_user,
        test_org_unit,
        import_permissions,
        test_fund,
    ):
        """Test processing a row with missing required fields."""
        processor = FinanceEntryProcessor()
        row = {"_row_number": 1}  # Missing fund_id, amount, transaction_date
        mapping = {}

        result = processor.process_row(
            db=db,
            row=row,
            mapping=mapping,
            mode="create_only",
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
            org_unit_id=test_org_unit.id,
        )

        assert not result.success
        assert len(result.errors) > 0

    def test_process_row_no_giver(
        self,
        db,
        tenant_id,
        test_user,
        test_org_unit,
        import_permissions,
        test_fund,
    ):
        """Test processing a row without any giver (should fail)."""
        processor = FinanceEntryProcessor()
        row = {
            "_row_number": 1,
            "fund_id": str(test_fund.id),
            "amount": "100.00",
            "transaction_date": "2024-01-15",
            # Missing person_id, cell_id, and external_giver_name
        }
        mapping = {
            "fund_id": "fund_id",
            "amount": "amount",
            "transaction_date": "transaction_date",
        }

        result = processor.process_row(
            db=db,
            row=row,
            mapping=mapping,
            mode="create_only",
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
            org_unit_id=test_org_unit.id,
        )

        assert not result.success
        # Should have error about missing giver
        assert any(
            "giver" in error.message.lower() for error in result.errors
        )


class TestGetProcessor:
    """Tests for processor registry."""

    def test_get_processor_people(self):
        """Test getting people processor."""
        processor = get_processor("people")
        assert isinstance(processor, PeopleProcessor)

    def test_get_processor_first_timers(self):
        """Test getting first timers processor."""
        processor = get_processor("first_timers")
        assert isinstance(processor, FirstTimerProcessor)

    def test_get_processor_cells(self):
        """Test getting cells processor."""
        processor = get_processor("cells")
        assert isinstance(processor, CellProcessor)

    def test_get_processor_cell_reports(self):
        """Test getting cell reports processor."""
        processor = get_processor("cell_reports")
        assert isinstance(processor, CellReportProcessor)

    def test_get_processor_finance_entries(self):
        """Test getting finance entries processor."""
        processor = get_processor("finance_entries")
        assert isinstance(processor, FinanceEntryProcessor)

    def test_get_processor_default(self):
        """Test getting default processor for unknown type."""
        processor = get_processor("unknown")
        assert isinstance(processor, PeopleProcessor)  # Defaults to People

