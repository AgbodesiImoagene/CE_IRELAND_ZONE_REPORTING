"""Tests for Registry API routes."""

from __future__ import annotations

from datetime import date, time
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.common.models import (
    Attendance,
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
def registry_role(
    db, tenant_id, test_org_unit
):
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

    for code, desc in perms:
        perm = Permission(id=uuid4(), code=code, description=desc)
        db.add(perm)
        db.flush()

        role_perm = RolePermission(role_id=role.id, permission_id=perm.id)
        db.add(role_perm)

    db.commit()
    return role


@pytest.fixture
def registry_user(db, tenant_id, registry_role, test_org_unit):
    """Create a user with registry permissions."""
    from app.common.models import OrgAssignment, User
    from app.auth.utils import hash_password, create_access_token

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

    assignment = OrgAssignment(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        user_id=user.id,
        org_unit_id=test_org_unit.id,
        role_id=registry_role.id,
        scope_type="self",
    )
    db.add(assignment)
    db.commit()
    db.refresh(user)

    # Create token
    token = create_access_token(
        {"sub": str(user.id), "user_id": str(user.id)}
    )
    return (user, token)


class TestPeopleRoutes:
    """Test people endpoints."""

    def test_create_person_success(
        self, client: TestClient, db, registry_user, test_org_unit
    ):
        """Test creating a person via API."""
        user, token = registry_user
        response = client.post(
            "/api/v1/registry/people",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "org_unit_id": str(test_org_unit.id),
                "first_name": "John",
                "last_name": "Doe",
                "gender": "male",
                "email": "john@example.com",
                "phone": "1234567890",
                "membership_status": "member",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["first_name"] == "John"
        assert data["last_name"] == "Doe"
        assert data["email"] == "john@example.com"
        assert "member_code" in data
        assert data["membership_status"] == "member"

    def test_create_person_unauthorized(self, client: TestClient, test_org_unit):
        """Test creating person fails without auth."""
        response = client.post(
            "/api/v1/registry/people",
            json={
                "org_unit_id": str(test_org_unit.id),
                "first_name": "John",
                "last_name": "Doe",
                "gender": "male",
            },
        )
        assert response.status_code == 401

    def test_get_person(self, client: TestClient, db, registry_user, test_org_unit):
        """Test getting a person by ID."""
        user, token = registry_user
        person = PeopleService.create_person(
            db=db,
            creator_id=user.id,
            tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
            org_unit_id=test_org_unit.id,
            first_name="John",
            last_name="Doe",
            gender="male",
        )

        response = client.get(
            f"/api/v1/registry/people/{person.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(person.id)
        assert data["first_name"] == "John"

    def test_update_person(self, client: TestClient, db, registry_user, test_org_unit):
        """Test updating a person."""
        user, token = registry_user
        person = PeopleService.create_person(
            db=db,
            creator_id=user.id,
            tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
            org_unit_id=test_org_unit.id,
            first_name="John",
            last_name="Doe",
            gender="male",
            email="old@example.com",
        )

        response = client.patch(
            f"/api/v1/registry/people/{person.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": "new@example.com",
                "phone": "9876543210",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "new@example.com"
        assert data["phone"] == "9876543210"

    def test_list_people(self, client: TestClient, db, registry_user, test_org_unit):
        """Test listing people."""
        user, token = registry_user
        for i in range(3):
            PeopleService.create_person(
                db=db,
                creator_id=user.id,
                tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
                org_unit_id=test_org_unit.id,
                first_name=f"Person{i}",
                last_name="Test",
                gender="male",
            )

        response = client.get(
            "/api/v1/registry/people",
            headers={"Authorization": f"Bearer {token}"},
            params={"org_unit_id": str(test_org_unit.id)},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    def test_merge_people(self, client: TestClient, db, registry_user, test_org_unit):
        """Test merging people."""
        user, token = registry_user
        source = PeopleService.create_person(
            db=db,
            creator_id=user.id,
            tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
            org_unit_id=test_org_unit.id,
            first_name="Source",
            last_name="Person",
            gender="male",
        )

        target = PeopleService.create_person(
            db=db,
            creator_id=user.id,
            tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
            org_unit_id=test_org_unit.id,
            first_name="Target",
            last_name="Person",
            gender="male",
        )

        response = client.post(
            "/api/v1/registry/people/merge",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "source_person_id": str(source.id),
                "target_person_id": str(target.id),
                "reason": "Duplicate record",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(target.id)


class TestFirstTimerRoutes:
    """Test first-timer endpoints."""

    def test_create_first_timer(
        self, client: TestClient, db, registry_user, test_org_unit
    ):
        """Test creating a first-timer."""
        user, token = registry_user
        service = ServiceService.create_service(
            db=db,
            creator_id=user.id,
            tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
            org_unit_id=test_org_unit.id,
            name="Sunday Service",
            service_date=date.today(),
        )

        response = client.post(
            "/api/v1/registry/first-timers",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "service_id": str(service.id),
                "source": "Friend",
                "notes": "Very interested",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["source"] == "Friend"
        assert data["status"] == "New"

    def test_list_first_timers(
        self, client: TestClient, db, registry_user, test_org_unit
    ):
        """Test listing first-timers."""
        user, token = registry_user
        service = ServiceService.create_service(
            db=db,
            creator_id=user.id,
            tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
            org_unit_id=test_org_unit.id,
            name="Sunday Service",
            service_date=date.today(),
        )

        FirstTimerService.create_first_timer(
            db=db,
            creator_id=user.id,
            tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
            service_id=service.id,
        )

        response = client.get(
            "/api/v1/registry/first-timers",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_update_first_timer(
        self, client: TestClient, db, registry_user, test_org_unit
    ):
        """Test updating first-timer."""
        user, token = registry_user
        service = ServiceService.create_service(
            db=db,
            creator_id=user.id,
            tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
            org_unit_id=test_org_unit.id,
            name="Sunday Service",
            service_date=date.today(),
        )

        first_timer = FirstTimerService.create_first_timer(
            db=db,
            creator_id=user.id,
            tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
            service_id=service.id,
        )

        response = client.patch(
            f"/api/v1/registry/first-timers/{first_timer.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "status": "Contacted",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Contacted"

    def test_convert_first_timer_to_member(
        self, client: TestClient, db, registry_user, test_org_unit
    ):
        """Test converting first-timer to member."""
        user, token = registry_user
        service = ServiceService.create_service(
            db=db,
            creator_id=user.id,
            tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
            org_unit_id=test_org_unit.id,
            name="Sunday Service",
            service_date=date.today(),
        )

        first_timer = FirstTimerService.create_first_timer(
            db=db,
            creator_id=user.id,
            tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
            service_id=service.id,
        )

        response = client.post(
            f"/api/v1/registry/first-timers/{first_timer.id}/convert",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "org_unit_id": str(test_org_unit.id),
                "first_name": "Converted",
                "last_name": "Member",
                "gender": "male",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Converted"
        assert data["membership_status"] == "member"


class TestServiceRoutes:
    """Test service endpoints."""

    def test_create_service(self, client: TestClient, registry_user, test_org_unit):
        """Test creating a service."""
        user, token = registry_user
        response = client.post(
            "/api/v1/registry/services",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "org_unit_id": str(test_org_unit.id),
                "name": "Sunday Service",
                "service_date": date.today().isoformat(),
                "service_time": "10:00:00",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Sunday Service"

    def test_list_services(self, client: TestClient, db, registry_user, test_org_unit):
        """Test listing services."""
        user, token = registry_user
        for i in range(3):
            ServiceService.create_service(
                db=db,
                creator_id=user.id,
                tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
                org_unit_id=test_org_unit.id,
                name=f"Service {i}",
                service_date=date.today(),
            )

        response = client.get(
            "/api/v1/registry/services",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 3


class TestAttendanceRoutes:
    """Test attendance endpoints."""

    def test_create_attendance(
        self, client: TestClient, db, registry_user, test_org_unit
    ):
        """Test creating attendance."""
        user, token = registry_user
        service = ServiceService.create_service(
            db=db,
            creator_id=user.id,
            tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
            org_unit_id=test_org_unit.id,
            name="Sunday Service",
            service_date=date.today(),
        )

        response = client.post(
            "/api/v1/registry/attendance",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "service_id": str(service.id),
                "men_count": 10,
                "women_count": 15,
                "teens_count": 5,
                "kids_count": 8,
                "first_timers_count": 2,
                "new_converts_count": 1,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["men_count"] == 10
        assert data["women_count"] == 15
        assert data["total_attendance"] == 41

    def test_update_attendance(
        self, client: TestClient, db, registry_user, test_org_unit
    ):
        """Test updating attendance."""
        user, token = registry_user
        service = ServiceService.create_service(
            db=db,
            creator_id=user.id,
            tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
            org_unit_id=test_org_unit.id,
            name="Sunday Service",
            service_date=date.today(),
        )

        attendance = AttendanceService.create_attendance(
            db=db,
            creator_id=user.id,
            tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
            service_id=service.id,
            men_count=10,
            women_count=15,
        )

        response = client.patch(
            f"/api/v1/registry/attendance/{attendance.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "men_count": 20,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["men_count"] == 20
        assert data["total_attendance"] == 35


class TestDepartmentRoutes:
    """Test department endpoints."""

    def test_create_department(
        self, client: TestClient, registry_user, test_org_unit
    ):
        """Test creating a department."""
        user, token = registry_user
        response = client.post(
            "/api/v1/registry/departments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "org_unit_id": str(test_org_unit.id),
                "name": "Music Ministry",
                "status": "active",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Music Ministry"

    def test_list_departments(
        self, client: TestClient, db, registry_user, test_org_unit
    ):
        """Test listing departments."""
        user, token = registry_user
        for i in range(3):
            DepartmentService.create_department(
                db=db,
                creator_id=user.id,
                tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
                org_unit_id=test_org_unit.id,
                name=f"Department {i}",
            )

        response = client.get(
            "/api/v1/registry/departments",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 3

    def test_assign_person_to_department(
        self, client: TestClient, db, registry_user, test_org_unit
    ):
        """Test assigning person to department."""
        user, token = registry_user
        person = PeopleService.create_person(
            db=db,
            creator_id=user.id,
            tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
            org_unit_id=test_org_unit.id,
            first_name="John",
            last_name="Doe",
            gender="male",
        )

        dept = DepartmentService.create_department(
            db=db,
            creator_id=user.id,
            tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
            org_unit_id=test_org_unit.id,
            name="Music Ministry",
        )

        response = client.post(
            f"/api/v1/registry/departments/{dept.id}/members",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "person_id": str(person.id),
                "role": "leader",
                "start_date": date.today().isoformat(),
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["person_id"] == str(person.id)
        assert data["role"] == "leader"

    def test_delete_department(
        self, client: TestClient, db, registry_user, test_org_unit
    ):
        """Test deleting department."""
        user, token = registry_user
        dept = DepartmentService.create_department(
            db=db,
            creator_id=user.id,
            tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
            org_unit_id=test_org_unit.id,
            name="Music Ministry",
        )

        response = client.delete(
            f"/api/v1/registry/departments/{dept.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 204

        # Verify deleted
        deleted = DepartmentService.get_department(
            db, dept.id, UUID("12345678-1234-5678-1234-567812345678")
        )
        assert deleted is None

    def test_get_department_not_found(self, client: TestClient, registry_user):
        """Test getting non-existent department."""
        user, token = registry_user
        fake_id = uuid4()

        response = client.get(
            f"/api/v1/registry/departments/{fake_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    def test_update_department_not_found(
        self, client: TestClient, registry_user
    ):
        """Test updating non-existent department."""
        user, token = registry_user
        fake_id = uuid4()

        response = client.patch(
            f"/api/v1/registry/departments/{fake_id}",
            json={"name": "Updated Department"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400

    def test_delete_department_not_found(
        self, client: TestClient, registry_user
    ):
        """Test deleting non-existent department."""
        user, token = registry_user
        fake_id = uuid4()

        response = client.delete(
            f"/api/v1/registry/departments/{fake_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400

    def test_get_person_not_found(self, client: TestClient, registry_user):
        """Test getting non-existent person."""
        user, token = registry_user
        fake_id = uuid4()

        response = client.get(
            f"/api/v1/registry/people/{fake_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    def test_get_first_timer_not_found(
        self, client: TestClient, registry_user
    ):
        """Test getting non-existent first timer."""
        user, token = registry_user
        fake_id = uuid4()

        response = client.get(
            f"/api/v1/registry/first-timers/{fake_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    def test_get_service_not_found(self, client: TestClient, registry_user):
        """Test getting non-existent service."""
        user, token = registry_user
        fake_id = uuid4()

        response = client.get(
            f"/api/v1/registry/services/{fake_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    def test_get_attendance_not_found(self, client: TestClient, registry_user):
        """Test getting non-existent attendance."""
        user, token = registry_user
        fake_id = uuid4()

        response = client.get(
            f"/api/v1/registry/attendance/{fake_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    def test_list_department_members_not_found(
        self, client: TestClient, registry_user
    ):
        """Test listing members of non-existent department."""
        user, token = registry_user
        fake_id = uuid4()

        response = client.get(
            f"/api/v1/registry/departments/{fake_id}/members",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400

    def test_assign_person_to_department_not_found(
        self, client: TestClient, registry_user, test_org_unit, db, tenant_id
    ):
        """Test assigning person to non-existent department."""
        user, token = registry_user
        
        # Create a person for the test
        person = PeopleService.create_person(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            first_name="Test",
            last_name="Person",
            gender="male",
        )
        
        fake_id = uuid4()

        response = client.post(
            f"/api/v1/registry/departments/{fake_id}/members",
            json={"person_id": str(person.id), "role": "member"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400

    def test_remove_person_from_department_not_found(
        self, client: TestClient, registry_user, test_org_unit, db, tenant_id
    ):
        """Test removing person from non-existent department."""
        user, token = registry_user
        
        # Create a person for the test
        person = PeopleService.create_person(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            first_name="Test",
            last_name="Person",
            gender="male",
        )
        
        fake_id = uuid4()

        response = client.delete(
            f"/api/v1/registry/departments/{fake_id}/members/{person.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400

