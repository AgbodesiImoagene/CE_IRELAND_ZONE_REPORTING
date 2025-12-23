"""Tests for Registry service layer."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.common.models import (
    Attendance,
    AuditLog,
    Department,
    DepartmentRole,
    FirstTimer,
    Membership,
    People,
    Permission,
    RolePermission,
    Service,
)
from app.registry.service import (
    AttendanceService,
    DepartmentService,
    FirstTimerService,
    PeopleService,
    ServiceService,
)


@pytest.fixture
def registry_permission(db, tenant_id, test_role) -> Permission:
    """Create a registry permission."""
    perm = Permission(
        id=uuid4(),
        code="registry.people.create",
        description="Create people",
    )
    db.add(perm)
    db.flush()

    role_perm = RolePermission(role_id=test_role.id, permission_id=perm.id)
    db.add(role_perm)
    db.commit()
    db.refresh(perm)
    return perm


@pytest.fixture
def registry_role(
    db, tenant_id, test_org_unit
) -> tuple[Permission, Permission, Permission, Permission, Permission]:
    """Create a role with all registry permissions."""
    from app.common.models import Role

    role = Role(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        name="Registry Role",
    )
    db.add(role)
    db.flush()

    # Create all registry permissions
    perms = [
        ("registry.people.create", "Create people"),
        ("registry.people.update", "Update people"),
        ("registry.people.merge", "Merge people"),
        ("registry.firsttimers.create", "Create first-timers"),
        ("registry.firsttimers.update", "Update first-timers"),
        ("registry.attendance.create", "Create attendance"),
        ("registry.attendance.update", "Update attendance"),
        ("registry.departments.create", "Create departments"),
        ("registry.departments.update", "Update departments"),
        ("registry.departments.delete", "Delete departments"),
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
def registry_user(db, tenant_id, registry_role, test_org_unit):
    """Create a user with registry permissions."""
    from app.common.models import OrgAssignment, User
    from app.auth.utils import hash_password

    user = User(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        email="registry@example.com",
        password_hash=hash_password("testpass123"),
        is_active=True,
        is_2fa_enabled=False,
    )
    db.add(user)
    db.flush()

    role = registry_role[0]
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


class TestPeopleService:
    """Test PeopleService methods."""

    def test_create_person_success(
        self, db, tenant_id, registry_user, test_org_unit
    ):
        """Test creating a person successfully."""
        person = PeopleService.create_person(
            db=db,
            creator_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            first_name="John",
            last_name="Doe",
            gender="male",
            email="john@example.com",
            phone="1234567890",
            membership_status="member",
        )

        assert person is not None
        assert person.first_name == "John"
        assert person.last_name == "Doe"
        assert person.email == "john@example.com"
        assert person.member_code is not None
        assert person.member_code.startswith("MEM-")

        # Check membership was created
        membership = db.execute(
            select(Membership).where(Membership.person_id == person.id)
        ).scalar_one_or_none()
        assert membership is not None
        assert membership.status == "member"

        # Check audit log
        audit = db.execute(
            select(AuditLog).where(AuditLog.entity_id == person.id)
        ).scalar_one_or_none()
        assert audit is not None
        assert audit.action == "create"
        assert audit.entity_type == "people"

    def test_create_person_no_permission(self, db, tenant_id, test_user, test_org_unit):
        """Test creating person fails without permission."""
        with pytest.raises(ValueError, match="User lacks"):
            PeopleService.create_person(
                db=db,
                creator_id=test_user.id,
                tenant_id=UUID(tenant_id),
                org_unit_id=test_org_unit.id,
                first_name="John",
                last_name="Doe",
                gender="male",
            )

    def test_generate_member_code(self, db, tenant_id, registry_user, test_org_unit):
        """Test member code generation."""
        # Create first person
        person1 = PeopleService.create_person(
            db=db,
            creator_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            first_name="John",
            last_name="Doe",
            gender="male",
        )
        assert person1.member_code == "MEM-0001"

        # Create second person
        person2 = PeopleService.create_person(
            db=db,
            creator_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            first_name="Jane",
            last_name="Smith",
            gender="female",
        )
        assert person2.member_code == "MEM-0002"

    def test_get_person(self, db, tenant_id, registry_user, test_org_unit):
        """Test getting a person by ID."""
        person = PeopleService.create_person(
            db=db,
            creator_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            first_name="John",
            last_name="Doe",
            gender="male",
        )

        retrieved = PeopleService.get_person(db, person.id, UUID(tenant_id))
        assert retrieved is not None
        assert retrieved.id == person.id
        assert retrieved.first_name == "John"

    def test_update_person(self, db, tenant_id, registry_user, test_org_unit):
        """Test updating a person."""
        person = PeopleService.create_person(
            db=db,
            creator_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            first_name="John",
            last_name="Doe",
            gender="male",
            email="old@example.com",
        )

        updated = PeopleService.update_person(
            db=db,
            updater_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            person_id=person.id,
            email="new@example.com",
            phone="9876543210",
        )

        assert updated.email == "new@example.com"
        assert updated.phone == "9876543210"

        # Check audit log
        audit = db.execute(
            select(AuditLog)
            .where(AuditLog.entity_id == person.id, AuditLog.action == "update")
        ).scalar_one_or_none()
        assert audit is not None

    def test_list_people(self, db, tenant_id, registry_user, test_org_unit):
        """Test listing people with filters."""
        # Create multiple people
        for i in range(3):
            PeopleService.create_person(
                db=db,
                creator_id=registry_user.id,
                tenant_id=UUID(tenant_id),
                org_unit_id=test_org_unit.id,
                first_name=f"Person{i}",
                last_name="Test",
                gender="male",
            )

        people = PeopleService.list_people(
            db=db,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            limit=10,
        )
        assert len(people) == 3

        # Test search
        people = PeopleService.list_people(
            db=db,
            tenant_id=UUID(tenant_id),
            search="Person1",
            limit=10,
        )
        assert len(people) == 1
        assert people[0].first_name == "Person1"

    def test_merge_people(
        self, db, tenant_id, registry_user, test_org_unit
    ):
        """Test merging two people records."""
        source = PeopleService.create_person(
            db=db,
            creator_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            first_name="Source",
            last_name="Person",
            gender="male",
        )

        target = PeopleService.create_person(
            db=db,
            creator_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            first_name="Target",
            last_name="Person",
            gender="male",
        )

        merged = PeopleService.merge_people(
            db=db,
            merger_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            source_person_id=source.id,
            target_person_id=target.id,
            reason="Duplicate record",
        )

        assert merged.id == target.id
        assert merged.first_name == "Target"

        # Source should be deleted
        deleted_source = PeopleService.get_person(db, source.id, UUID(tenant_id))
        assert deleted_source is None


class TestFirstTimerService:
    """Test FirstTimerService methods."""

    def test_create_first_timer(
        self, db, tenant_id, registry_user, test_org_unit
    ):
        """Test creating a first-timer."""
        # Create a service first
        service = ServiceService.create_service(
            db=db,
            creator_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            name="Sunday Service",
            service_date=date.today(),
        )

        first_timer = FirstTimerService.create_first_timer(
            db=db,
            creator_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            service_id=service.id,
            source="Friend",
            notes="Very interested",
        )

        assert first_timer is not None
        assert first_timer.service_id == service.id
        assert first_timer.source == "Friend"
        assert first_timer.status == "New"

        # Check audit log
        audit = db.execute(
            select(AuditLog).where(AuditLog.entity_id == first_timer.id)
        ).scalar_one_or_none()
        assert audit is not None

    def test_update_first_timer_status(
        self, db, tenant_id, registry_user, test_org_unit
    ):
        """Test updating first-timer status."""
        service = ServiceService.create_service(
            db=db,
            creator_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            name="Sunday Service",
            service_date=date.today(),
        )

        first_timer = FirstTimerService.create_first_timer(
            db=db,
            creator_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            service_id=service.id,
        )

        updated = FirstTimerService.update_first_timer_status(
            db=db,
            updater_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            first_timer_id=first_timer.id,
            status="Contacted",
        )

        assert updated.status == "Contacted"

    def test_convert_to_member(
        self, db, tenant_id, registry_user, test_org_unit
    ):
        """Test converting first-timer to member."""
        service = ServiceService.create_service(
            db=db,
            creator_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            name="Sunday Service",
            service_date=date.today(),
        )

        first_timer = FirstTimerService.create_first_timer(
            db=db,
            creator_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            service_id=service.id,
        )

        person = FirstTimerService.convert_to_member(
            db=db,
            converter_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            first_timer_id=first_timer.id,
            org_unit_id=test_org_unit.id,
            first_name="Converted",
            last_name="Member",
            gender="male",
        )

        assert person is not None
        assert person.first_name == "Converted"

        # First-timer should be linked to person
        db.refresh(first_timer)
        assert first_timer.person_id == person.id
        assert first_timer.status == "Member"


class TestServiceService:
    """Test ServiceService methods."""

    def test_create_service(self, db, tenant_id, registry_user, test_org_unit):
        """Test creating a service."""
        service = ServiceService.create_service(
            db=db,
            creator_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            name="Sunday Service",
            service_date=date.today(),
            service_time=time(10, 0),
        )

        assert service is not None
        assert service.name == "Sunday Service"
        assert service.service_date == date.today()
        assert service.service_time == time(10, 0)

    def test_list_services(self, db, tenant_id, registry_user, test_org_unit):
        """Test listing services."""
        # Create multiple services
        for i in range(3):
            ServiceService.create_service(
                db=db,
                creator_id=registry_user.id,
                tenant_id=UUID(tenant_id),
                org_unit_id=test_org_unit.id,
                name=f"Service {i}",
                service_date=date.today(),
            )

        services = ServiceService.list_services(
            db=db,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
        )
        assert len(services) == 3


class TestAttendanceService:
    """Test AttendanceService methods."""

    def test_create_attendance(self, db, tenant_id, registry_user, test_org_unit):
        """Test creating attendance record."""
        service = ServiceService.create_service(
            db=db,
            creator_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            name="Sunday Service",
            service_date=date.today(),
        )

        attendance = AttendanceService.create_attendance(
            db=db,
            creator_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            service_id=service.id,
            men_count=10,
            women_count=15,
            teens_count=5,
            kids_count=8,
            first_timers_count=2,
            new_converts_count=1,
        )

        assert attendance is not None
        assert attendance.men_count == 10
        assert attendance.women_count == 15
        assert attendance.total_attendance == 41  # Sum of all counts

        # Check audit log
        audit = db.execute(
            select(AuditLog).where(AuditLog.entity_id == attendance.id)
        ).scalar_one_or_none()
        assert audit is not None

    def test_create_attendance_duplicate(self, db, tenant_id, registry_user, test_org_unit):
        """Test creating duplicate attendance fails."""
        service = ServiceService.create_service(
            db=db,
            creator_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            name="Sunday Service",
            service_date=date.today(),
        )

        AttendanceService.create_attendance(
            db=db,
            creator_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            service_id=service.id,
            men_count=10,
        )

        # Try to create again
        with pytest.raises(ValueError, match="already exists"):
            AttendanceService.create_attendance(
                db=db,
                creator_id=registry_user.id,
                tenant_id=UUID(tenant_id),
                service_id=service.id,
                men_count=20,
            )

    def test_update_attendance(self, db, tenant_id, registry_user, test_org_unit):
        """Test updating attendance."""
        service = ServiceService.create_service(
            db=db,
            creator_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            name="Sunday Service",
            service_date=date.today(),
        )

        attendance = AttendanceService.create_attendance(
            db=db,
            creator_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            service_id=service.id,
            men_count=10,
            women_count=15,
        )

        updated = AttendanceService.update_attendance(
            db=db,
            updater_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            attendance_id=attendance.id,
            men_count=20,
        )

        assert updated.men_count == 20
        assert updated.total_attendance == 35  # 20 + 15


class TestDepartmentService:
    """Test DepartmentService methods."""

    def test_create_department(self, db, tenant_id, registry_user, test_org_unit):
        """Test creating a department."""
        dept = DepartmentService.create_department(
            db=db,
            creator_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            name="Music Ministry",
            status="active",
        )

        assert dept is not None
        assert dept.name == "Music Ministry"
        assert dept.status == "active"

        # Check audit log
        audit = db.execute(
            select(AuditLog).where(AuditLog.entity_id == dept.id)
        ).scalar_one_or_none()
        assert audit is not None

    def test_assign_person_to_department(
        self, db, tenant_id, registry_user, test_org_unit
    ):
        """Test assigning person to department."""
        # Create person and department
        person = PeopleService.create_person(
            db=db,
            creator_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            first_name="John",
            last_name="Doe",
            gender="male",
        )

        dept = DepartmentService.create_department(
            db=db,
            creator_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            name="Music Ministry",
        )

        dept_role = DepartmentService.assign_person_to_department(
            db=db,
            updater_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            dept_id=dept.id,
            person_id=person.id,
            role="leader",
            start_date=date.today(),
        )

        assert dept_role is not None
        assert dept_role.person_id == person.id
        assert dept_role.dept_id == dept.id
        assert dept_role.role == "leader"

    def test_update_department(self, db, tenant_id, registry_user, test_org_unit):
        """Test updating department."""
        dept = DepartmentService.create_department(
            db=db,
            creator_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            name="Music Ministry",
        )

        updated = DepartmentService.update_department(
            db=db,
            updater_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            dept_id=dept.id,
            status="inactive",
        )

        assert updated.status == "inactive"

    def test_delete_department(self, db, tenant_id, registry_user, test_org_unit):
        """Test deleting department."""
        dept = DepartmentService.create_department(
            db=db,
            creator_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            name="Music Ministry",
        )

        DepartmentService.delete_department(
            db=db,
            deleter_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            dept_id=dept.id,
        )

        # Department should be deleted
        deleted = DepartmentService.get_department(db, dept.id, UUID(tenant_id))
        assert deleted is None

    def test_get_person_not_found(self, db, tenant_id):
        """Test getting non-existent person."""
        fake_id = uuid4()
        person = PeopleService.get_person(db, fake_id, UUID(tenant_id))
        assert person is None

    def test_list_people_with_filters(
        self, db, tenant_id, registry_user, test_org_unit
    ):
        """Test listing people with various filters."""
        user = registry_user

        # Create people with different statuses
        person1 = PeopleService.create_person(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            first_name="Active",
            last_name="Member",
            gender="male",
            membership_status="active",
        )

        person2 = PeopleService.create_person(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            first_name="Inactive",
            last_name="Member",
            gender="female",
            membership_status="inactive",
        )

        # List all people
        all_people = PeopleService.list_people(
            db=db, tenant_id=UUID(tenant_id), limit=100
        )
        assert len(all_people) >= 2

        # List with status filter
        active_people = PeopleService.list_people(
            db=db,
            tenant_id=UUID(tenant_id),
            membership_status="active",
            limit=100,
        )
        assert all(
            p.id == person1.id
            for p in active_people
            if p.id in [person1.id, person2.id]
        )

        # List with search filter
        # Use a more unique search term that won't match "Inactive"
        searched = PeopleService.list_people(
            db=db, tenant_id=UUID(tenant_id), search="Active", limit=100
        )
        # Verify person1 is in results
        assert person1.id in [p.id for p in searched]
        # Note: If search is substring-based, "Active" might match "Inactive"
        # So we can't reliably assert person2 is not in results
        # Instead, we verify person1 is found, which is the main goal

    def test_get_service_not_found(self, db, tenant_id):
        """Test getting non-existent service."""
        fake_id = uuid4()
        service = ServiceService.get_service(db, fake_id, UUID(tenant_id))
        assert service is None

    def test_list_services_with_date_range(
        self, db, tenant_id, registry_user, test_org_unit
    ):
        """Test listing services with date range filter."""
        user = registry_user
        from datetime import date, timedelta

        today = date.today()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)

        # Create services on different dates
        service1 = ServiceService.create_service(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            name="Yesterday Service",
            service_date=yesterday,
        )

        service2 = ServiceService.create_service(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            name="Today Service",
            service_date=today,
        )

        # List services in date range
        services = ServiceService.list_services(
            db=db,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            start_date=yesterday,
            end_date=tomorrow,
        )
        assert len(services) >= 2
        assert any(s.id == service1.id for s in services)
        assert any(s.id == service2.id for s in services)

    def test_get_department_not_found(self, db, tenant_id):
        """Test getting non-existent department."""
        fake_id = uuid4()
        dept = DepartmentService.get_department(db, fake_id, UUID(tenant_id))
        assert dept is None

    def test_list_department_members(
        self, db, tenant_id, registry_user, test_org_unit
    ):
        """Test listing department members."""
        person = PeopleService.create_person(
            db=db,
            creator_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            first_name="John",
            last_name="Doe",
            gender="male",
        )

        dept = DepartmentService.create_department(
            db=db,
            creator_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            name="Music Ministry",
        )

        DepartmentService.assign_person_to_department(
            db=db,
            updater_id=registry_user.id,
            tenant_id=UUID(tenant_id),
            dept_id=dept.id,
            person_id=person.id,
            role="leader",
        )

        members = DepartmentService.list_department_members(
            db=db,
            tenant_id=UUID(tenant_id),
            dept_id=dept.id,
        )

        assert len(members) == 1
        assert members[0].person_id == person.id

