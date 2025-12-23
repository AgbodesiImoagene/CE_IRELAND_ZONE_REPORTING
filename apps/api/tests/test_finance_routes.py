"""Tests for Finance API routes."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from app.common.models import (
    Permission,
    RolePermission,
    Service,
    People,
)
from app.finance.service import (
    BatchService,
    FinanceEntryService,
    FundService,
    PartnershipArmService,
    PartnershipService,
)


@pytest.fixture
def finance_role(db, tenant_id, test_org_unit):
    """Create a role with all finance permissions."""
    from app.common.models import Role

    role = Role(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        name="Finance Role",
    )
    db.add(role)
    db.flush()

    # Create all finance permissions
    perms = [
        ("finance.funds.create", "Create funds"),
        ("finance.funds.read", "Read funds"),
        ("finance.funds.update", "Update funds"),
        ("finance.funds.delete", "Delete funds"),
        ("finance.partnership_arms.create", "Create partnership arms"),
        ("finance.partnership_arms.read", "Read partnership arms"),
        ("finance.partnership_arms.update", "Update partnership arms"),
        ("finance.partnership_arms.delete", "Delete partnership arms"),
        ("finance.batches.create", "Create batches"),
        ("finance.batches.read", "Read batches"),
        ("finance.batches.update", "Update batches"),
        ("finance.batches.delete", "Delete batches"),
        ("finance.batches.lock", "Lock batches"),
        ("finance.batches.unlock", "Unlock batches"),
        ("finance.entries.create", "Create finance entries"),
        ("finance.entries.read", "Read finance entries"),
        ("finance.entries.update", "Update finance entries"),
        ("finance.entries.delete", "Delete finance entries"),
        ("finance.verify", "Verify finance entries/batches"),
        ("finance.lookups.manage", "Manage funds and partnership arms"),
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
def finance_user(db, tenant_id, finance_role, test_org_unit):
    """Create a user with finance permissions."""
    from app.common.models import OrgAssignment, User
    from app.auth.utils import hash_password, create_access_token

    user = User(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        email="finance@example.com",
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
        role_id=finance_role.id,
        scope_type="self",
    )
    db.add(assignment)
    db.commit()
    db.refresh(user)

    # Create token
    token = create_access_token({"sub": str(user.id), "user_id": str(user.id)})
    return (user, token)


@pytest.fixture
def finance_user2(db, tenant_id, finance_role, test_org_unit):
    """Create a second user with finance permissions."""
    from app.common.models import OrgAssignment, User
    from app.auth.utils import hash_password, create_access_token

    user = User(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        email="finance2@example.com",
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
        role_id=finance_role.id,
        scope_type="self",
    )
    db.add(assignment)
    db.commit()
    db.refresh(user)

    # Create token
    token = create_access_token({"sub": str(user.id), "user_id": str(user.id)})
    return (user, token)


@pytest.fixture
def finance_user3(db, tenant_id, finance_role, test_org_unit):
    """Create a third user with finance permissions."""
    from app.common.models import OrgAssignment, User
    from app.auth.utils import hash_password, create_access_token

    user = User(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        email="finance3@example.com",
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
        role_id=finance_role.id,
        scope_type="self",
    )
    db.add(assignment)
    db.commit()
    db.refresh(user)

    # Create token
    token = create_access_token({"sub": str(user.id), "user_id": str(user.id)})
    return (user, token)


@pytest.fixture
def test_fund(db, tenant_id, finance_user):
    """Create a test fund."""
    user, token = finance_user
    fund = FundService.create_fund(
        db=db,
        creator_id=user.id,
        tenant_id=UUID(tenant_id),
        name="Tithe",
        is_partnership=False,
        active=True,
    )
    return fund


@pytest.fixture
def test_partnership_arm(db, tenant_id, finance_user):
    """Create a test partnership arm."""
    user, token = finance_user
    partnership_arm = PartnershipArmService.create_partnership_arm(
        db=db,
        creator_id=user.id,
        tenant_id=UUID(tenant_id),
        name="Rhapsody of Realities",
        active_from=date.today(),
        active=True,
    )
    return partnership_arm


@pytest.fixture
def test_service(db, tenant_id, test_org_unit, finance_user):
    """Create a test service."""
    service = Service(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        org_unit_id=test_org_unit.id,
        name="Sunday Service",
        service_date=date.today(),
        service_time=None,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


@pytest.fixture
def test_person(db, tenant_id, test_org_unit):
    """Create a test person."""
    person = People(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        org_unit_id=test_org_unit.id,
        first_name="Test",
        last_name="Person",
        gender="male",
    )
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


class TestFundRoutes:
    """Test fund API routes."""

    def test_create_fund_success(self, client: TestClient, finance_user, test_fund):
        """Test creating a fund via API."""
        user, token = finance_user
        response = client.post(
            "/api/v1/finance/funds",
            json={
                "name": "Offering",
                "is_partnership": False,
                "active": True,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Offering"
        assert data["is_partnership"] is False

    def test_list_funds(self, client: TestClient, finance_user, test_fund):
        """Test listing funds."""
        user, token = finance_user
        response = client.get(
            "/api/v1/finance/funds",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(f["id"] == str(test_fund.id) for f in data)

    def test_get_fund(self, client: TestClient, finance_user, test_fund):
        """Test getting a fund by ID."""
        user, token = finance_user
        response = client.get(
            f"/api/v1/finance/funds/{test_fund.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_fund.id)
        assert data["name"] == "Tithe"

    def test_update_fund(self, client: TestClient, finance_user, test_fund):
        """Test updating a fund."""
        user, token = finance_user
        response = client.patch(
            f"/api/v1/finance/funds/{test_fund.id}",
            json={"name": "Updated Tithe", "active": False},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Tithe"
        assert data["active"] is False

    def test_delete_fund(
        self, client: TestClient, finance_user, test_fund, db, tenant_id
    ):
        """Test deleting a fund."""
        user, token = finance_user
        # Create a new fund to delete (not used in entries)
        fund = FundService.create_fund(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            name="Temporary Fund",
            is_partnership=False,
            active=True,
        )

        response = client.delete(
            f"/api/v1/finance/funds/{fund.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 204


class TestPartnershipArmRoutes:
    """Test partnership arm API routes."""

    def test_create_partnership_arm_success(
        self, client: TestClient, finance_user
    ):
        """Test creating a partnership arm via API."""
        user, token = finance_user
        response = client.post(
            "/api/v1/finance/partnership-arms",
            json={
                "name": "Healing School",
                "active_from": date.today().isoformat(),
                "active": True,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Healing School"
        assert data["active"] is True

    def test_list_partnership_arms(
        self, client: TestClient, finance_user, test_partnership_arm
    ):
        """Test listing partnership arms."""
        user, token = finance_user
        response = client.get(
            "/api/v1/finance/partnership-arms",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(pa["id"] == str(test_partnership_arm.id) for pa in data)

    def test_get_partnership_arm(
        self, client: TestClient, finance_user, test_partnership_arm
    ):
        """Test getting a partnership arm by ID."""
        user, token = finance_user
        response = client.get(
            f"/api/v1/finance/partnership-arms/{test_partnership_arm.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_partnership_arm.id)


class TestBatchRoutes:
    """Test batch API routes."""

    def test_create_batch_success(
        self, client: TestClient, finance_user, test_org_unit, test_service
    ):
        """Test creating a batch via API."""
        user, token = finance_user
        response = client.post(
            "/api/v1/finance/batches",
            json={
                "org_unit_id": str(test_org_unit.id),
                "service_id": str(test_service.id),
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["org_unit_id"] == str(test_org_unit.id)
        assert data["service_id"] == str(test_service.id)
        assert data["status"] == "draft"

    def test_verify_batch_first_verification(
        self,
        client: TestClient,
        finance_user,
        test_org_unit,
        test_service,
        db,
        tenant_id,
    ):
        """Test first verification of a batch."""
        user, token = finance_user
        # Create batch
        batch = BatchService.create_batch(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            service_id=test_service.id,
        )

        response = client.post(
            f"/api/v1/finance/batches/{batch.id}/verify",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["verified_by_1"] == str(user.id)
        assert data["verified_by_2"] is None

    def test_verify_batch_dual_verification(
        self,
        client: TestClient,
        finance_user,
        finance_user2,
        test_org_unit,
        test_service,
        db,
        tenant_id,
    ):
        """Test dual verification of a batch."""
        user, token = finance_user
        user2, token2 = finance_user2
        # Create batch
        batch = BatchService.create_batch(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            service_id=test_service.id,
        )

        # First verification
        response1 = client.post(
            f"/api/v1/finance/batches/{batch.id}/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response1.status_code == 200

        # Second verification
        response2 = client.post(
            f"/api/v1/finance/batches/{batch.id}/verify",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert response2.status_code == 200

        data = response2.json()
        assert data["verified_by_1"] == str(user.id)
        assert data["verified_by_2"] == str(user2.id)

    def test_lock_batch_requires_dual_verification(
        self,
        client: TestClient,
        finance_user,
        finance_user2,
        finance_user3,
        test_org_unit,
        test_service,
        db,
        tenant_id,
    ):
        """Test that locking requires dual verification."""
        user, token = finance_user
        user2, token2 = finance_user2
        user3, token3 = finance_user3
        # Create batch
        batch = BatchService.create_batch(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            service_id=test_service.id,
        )

        # First verification
        client.post(
            f"/api/v1/finance/batches/{batch.id}/verify",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Second verification
        client.post(
            f"/api/v1/finance/batches/{batch.id}/verify",
            headers={"Authorization": f"Bearer {token2}"},
        )

        # Lock by third user
        response = client.post(
            f"/api/v1/finance/batches/{batch.id}/lock",
            json={},
            headers={"Authorization": f"Bearer {token3}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "locked"
        assert data["locked_by"] == str(user3.id)
        assert data["locked_at"] is not None

    def test_lock_batch_without_dual_verification_fails(
        self,
        client: TestClient,
        finance_user,
        test_org_unit,
        test_service,
        db,
        tenant_id,
    ):
        """Test that locking without dual verification fails."""
        user, token = finance_user
        # Create batch
        batch = BatchService.create_batch(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            service_id=test_service.id,
        )

        # Try to lock without verification
        response = client.post(
            f"/api/v1/finance/batches/{batch.id}/lock",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400
        assert "dual verification" in response.json()["detail"].lower()

    def test_update_locked_batch_fails(
        self,
        client: TestClient,
        finance_user,
        finance_user2,
        finance_user3,
        test_org_unit,
        test_service,
        db,
        tenant_id,
    ):
        """Test that updating a locked batch fails."""
        user, token = finance_user
        user2, token2 = finance_user2
        user3, token3 = finance_user3
        # Create and lock batch
        batch = BatchService.create_batch(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            service_id=test_service.id,
        )

        BatchService.verify_batch(
            db=db,
            verifier_id=user.id,
            tenant_id=UUID(tenant_id),
            batch_id=batch.id,
        )
        BatchService.verify_batch(
            db=db,
            verifier_id=user2.id,
            tenant_id=UUID(tenant_id),
            batch_id=batch.id,
        )
        BatchService.lock_batch(
            db=db,
            locker_id=user3.id,
            tenant_id=UUID(tenant_id),
            batch_id=batch.id,
        )

        # Try to update
        response = client.patch(
            f"/api/v1/finance/batches/{batch.id}",
            json={"service_id": str(test_service.id)},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400
        assert "locked" in response.json()["detail"].lower()


class TestFinanceEntryRoutes:
    """Test finance entry API routes."""

    def test_create_entry_success(
        self,
        client: TestClient,
        finance_user,
        test_org_unit,
        test_fund,
        test_person,
    ):
        """Test creating a finance entry via API."""
        user, token = finance_user
        response = client.post(
            "/api/v1/finance/entries",
            json={
                "org_unit_id": str(test_org_unit.id),
                "fund_id": str(test_fund.id),
                "amount": "100.00",
                "transaction_date": date.today().isoformat(),
                "person_id": str(test_person.id),
                "method": "cash",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["amount"] == "100.00"
        assert data["fund_id"] == str(test_fund.id)
        assert data["person_id"] == str(test_person.id)
        assert data["verified_status"] == "draft"

    def test_list_entries(
        self,
        client: TestClient,
        finance_user,
        test_org_unit,
        test_fund,
        test_person,
        db,
        tenant_id,
    ):
        """Test listing finance entries."""
        user, token = finance_user
        # Create an entry
        FinanceEntryService.create_entry(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            fund_id=test_fund.id,
            amount=Decimal("100.00"),
            transaction_date=date.today(),
            person_id=test_person.id,
        )

        response = client.get(
            "/api/v1/finance/entries",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_update_entry_success(
        self,
        client: TestClient,
        finance_user,
        test_org_unit,
        test_fund,
        test_person,
        db,
        tenant_id,
    ):
        """Test updating a finance entry."""
        user, token = finance_user
        # Create an entry
        entry = FinanceEntryService.create_entry(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            fund_id=test_fund.id,
            amount=Decimal("100.00"),
            transaction_date=date.today(),
            person_id=test_person.id,
        )

        response = client.patch(
            f"/api/v1/finance/entries/{entry.id}",
            json={"amount": "150.00", "comment": "Updated"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["amount"] == "150.00"
        assert data["comment"] == "Updated"

    def test_update_entry_in_locked_batch_fails(
        self,
        client: TestClient,
        finance_user,
        finance_user2,
        finance_user3,
        test_org_unit,
        test_fund,
        test_person,
        test_service,
        db,
        tenant_id,
    ):
        """Test that updating entry in locked batch fails."""
        user, token = finance_user
        user2, _ = finance_user2
        user3, _ = finance_user3
        # Create batch and entry
        batch = BatchService.create_batch(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            service_id=test_service.id,
        )

        entry = FinanceEntryService.create_entry(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            fund_id=test_fund.id,
            amount=Decimal("100.00"),
            transaction_date=date.today(),
            person_id=test_person.id,
            batch_id=batch.id,
        )

        # Verify and lock batch
        BatchService.verify_batch(
            db=db,
            verifier_id=user.id,
            tenant_id=UUID(tenant_id),
            batch_id=batch.id,
        )
        BatchService.verify_batch(
            db=db,
            verifier_id=user2.id,
            tenant_id=UUID(tenant_id),
            batch_id=batch.id,
        )
        BatchService.lock_batch(
            db=db,
            locker_id=user3.id,
            tenant_id=UUID(tenant_id),
            batch_id=batch.id,
        )

        # Try to update entry
        response = client.patch(
            f"/api/v1/finance/entries/{entry.id}",
            json={"amount": "150.00"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400
        assert "locked" in response.json()["detail"].lower()

    def test_verify_entry_success(
        self,
        client: TestClient,
        finance_user,
        test_org_unit,
        test_fund,
        test_person,
        db,
        tenant_id,
    ):
        """Test verifying a finance entry."""
        user, token = finance_user
        # Create an entry
        entry = FinanceEntryService.create_entry(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            fund_id=test_fund.id,
            amount=Decimal("100.00"),
            transaction_date=date.today(),
            person_id=test_person.id,
        )

        response = client.post(
            f"/api/v1/finance/entries/{entry.id}/verify",
            json={"verified_status": "verified"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["verified_status"] == "verified"

    def test_reconcile_entry_success(
        self,
        client: TestClient,
        finance_user,
        test_org_unit,
        test_fund,
        test_person,
        db,
        tenant_id,
    ):
        """Test reconciling a finance entry."""
        user, token = finance_user
        # Create an entry
        entry = FinanceEntryService.create_entry(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            fund_id=test_fund.id,
            amount=Decimal("100.00"),
            transaction_date=date.today(),
            person_id=test_person.id,
        )

        response = client.post(
            f"/api/v1/finance/entries/{entry.id}/reconcile",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["verified_status"] == "reconciled"


class TestPartnershipRoutes:
    """Test partnership API routes."""

    def test_create_partnership_success(
        self, client: TestClient, finance_user, test_person, test_fund
    ):
        """Test creating a partnership via API."""
        _, token = finance_user
        response = client.post(
            "/api/v1/finance/partnerships",
            json={
                "person_id": str(test_person.id),
                "fund_id": str(test_fund.id),
                "cadence": "monthly",
                "start_date": date.today().isoformat(),
                "target_amount": "1000.00",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["person_id"] == str(test_person.id)
        assert data["fund_id"] == str(test_fund.id)
        assert data["cadence"] == "monthly"
        assert data["target_amount"] == "1000.00"

    def test_get_partnership_fulfilment(
        self,
        client: TestClient,
        finance_user,
        test_org_unit,
        test_person,
        test_fund,
        db,
        tenant_id,
    ):
        """Test getting partnership fulfilment."""
        user, token = finance_user
        # Create partnership
        partnership = PartnershipService.create_partnership(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            person_id=test_person.id,
            fund_id=test_fund.id,
            cadence="monthly",
            start_date=date.today(),
            target_amount=Decimal("1000.00"),
        )

        # Create some entries
        FinanceEntryService.create_entry(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            fund_id=test_fund.id,
            amount=Decimal("300.00"),
            transaction_date=date.today(),
            person_id=test_person.id,
        )

        response = client.get(
            f"/api/v1/finance/partnerships/{partnership.id}/fulfilment",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["partnership_id"] == str(partnership.id)
        assert data["target_amount"] == "1000.00"
        assert float(data["fulfilled_amount"]) == 300.0
        assert data["entries_count"] == 1


class TestSummaryRoutes:
    """Test summary API routes."""

    def test_get_fund_summary(
        self,
        client: TestClient,
        finance_user,
        test_org_unit,
        test_fund,
        test_person,
        db,
        tenant_id,
    ):
        """Test getting fund summary."""
        user, token = finance_user
        # Create some entries
        FinanceEntryService.create_entry(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            fund_id=test_fund.id,
            amount=Decimal("100.00"),
            transaction_date=date.today(),
            person_id=test_person.id,
        )

        FinanceEntryService.create_entry(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            fund_id=test_fund.id,
            amount=Decimal("50.00"),
            transaction_date=date.today(),
            person_id=test_person.id,
        )

        response = client.get(
            f"/api/v1/finance/summaries/funds?fund_id={test_fund.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(
            r["fund_id"] == str(test_fund.id)
            and float(r["total_amount"]) == 150.0
            for r in data
        )

    def test_get_fund_summary_no_entries(
        self, client: TestClient, finance_user, test_fund
    ):
        """Test getting fund summary with no entries."""
        user, token = finance_user

        response = client.get(
            f"/api/v1/finance/summaries/funds?fund_id={test_fund.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_partnership_arm_summary(
        self,
        client: TestClient,
        finance_user,
        test_org_unit,
        test_partnership_arm,
        test_person,
        db,
        tenant_id,
    ):
        """Test getting partnership arm summary."""
        user, token = finance_user

        # Create partnership (need fund_id and start_date)
        fund = FundService.create_fund(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            name="Partnership Fund",
            is_partnership=True,
        )
        
        partnership = PartnershipService.create_partnership(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            person_id=test_person.id,
            fund_id=fund.id,
            partnership_arm_id=test_partnership_arm.id,
            target_amount=Decimal("1000.00"),
            cadence="monthly",
            start_date=date.today(),
        )

        # Create entry (fund_id is required)
        FinanceEntryService.create_entry(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            fund_id=fund.id,
            partnership_arm_id=test_partnership_arm.id,
            amount=Decimal("100.00"),
            transaction_date=date.today(),
            person_id=test_person.id,
        )

        response = client.get(
            f"/api/v1/finance/summaries/partnership-arms?partnership_arm_id={test_partnership_arm.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_fund_not_found(self, client: TestClient, finance_user):
        """Test getting non-existent fund."""
        user, token = finance_user
        fake_id = uuid4()

        response = client.get(
            f"/api/v1/finance/funds/{fake_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    def test_update_fund_not_found(self, client: TestClient, finance_user):
        """Test updating non-existent fund."""
        user, token = finance_user
        fake_id = uuid4()

        response = client.patch(
            f"/api/v1/finance/funds/{fake_id}",
            json={"name": "Updated Fund"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400

    def test_delete_fund_not_found(self, client: TestClient, finance_user):
        """Test deleting non-existent fund."""
        user, token = finance_user
        fake_id = uuid4()

        response = client.delete(
            f"/api/v1/finance/funds/{fake_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400

    def test_get_partnership_arm_not_found(
        self, client: TestClient, finance_user
    ):
        """Test getting non-existent partnership arm."""
        user, token = finance_user
        fake_id = uuid4()

        response = client.get(
            f"/api/v1/finance/partnership-arms/{fake_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    def test_get_batch_not_found(self, client: TestClient, finance_user):
        """Test getting non-existent batch."""
        user, token = finance_user
        fake_id = uuid4()

        response = client.get(
            f"/api/v1/finance/batches/{fake_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    def test_get_entry_not_found(self, client: TestClient, finance_user):
        """Test getting non-existent entry."""
        user, token = finance_user
        fake_id = uuid4()

        response = client.get(
            f"/api/v1/finance/entries/{fake_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    def test_get_partnership_not_found(self, client: TestClient, finance_user):
        """Test getting non-existent partnership."""
        user, token = finance_user
        fake_id = uuid4()

        response = client.get(
            f"/api/v1/finance/partnerships/{fake_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    def test_get_service_summary(
        self,
        client: TestClient,
        finance_user,
        test_org_unit,
        test_fund,
        test_service,
        test_person,
        db,
        tenant_id,
    ):
        """Test getting service summary."""
        user, token = finance_user

        # Create entry with service
        FinanceEntryService.create_entry(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            fund_id=test_fund.id,
            service_id=test_service.id,
            amount=Decimal("50.00"),
            transaction_date=date.today(),
            person_id=test_person.id,
        )

        response = client.get(
            f"/api/v1/finance/summaries/by-service?service_id={test_service.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_org_unit_summary(
        self,
        client: TestClient,
        finance_user,
        test_org_unit,
        test_fund,
        test_person,
        db,
        tenant_id,
    ):
        """Test getting org unit summary."""
        user, token = finance_user

        # Create entry
        FinanceEntryService.create_entry(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            fund_id=test_fund.id,
            amount=Decimal("75.00"),
            transaction_date=date.today(),
            person_id=test_person.id,
        )

        response = client.get(
            f"/api/v1/finance/summaries/by-org-unit?org_unit_id={test_org_unit.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_fund_summary_with_date_filters(
        self,
        client: TestClient,
        finance_user,
        test_org_unit,
        test_fund,
        test_person,
        db,
        tenant_id,
    ):
        """Test getting fund summary with date filters."""
        user, token = finance_user
        from datetime import timedelta

        today = date.today()

        FinanceEntryService.create_entry(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            fund_id=test_fund.id,
            amount=Decimal("100.00"),
            transaction_date=today,
            person_id=test_person.id,
        )

        response = client.get(
            f"/api/v1/finance/summaries/funds?fund_id={test_fund.id}&start_date={today.isoformat()}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_update_partnership_arm_not_found(
        self, client: TestClient, finance_user
    ):
        """Test updating non-existent partnership arm."""
        user, token = finance_user
        fake_id = uuid4()

        response = client.patch(
            f"/api/v1/finance/partnership-arms/{fake_id}",
            json={"name": "Updated Arm"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400

    def test_delete_partnership_arm_not_found(
        self, client: TestClient, finance_user
    ):
        """Test deleting non-existent partnership arm."""
        user, token = finance_user
        fake_id = uuid4()

        response = client.delete(
            f"/api/v1/finance/partnership-arms/{fake_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400

    def test_update_partnership_not_found(
        self, client: TestClient, finance_user
    ):
        """Test updating non-existent partnership."""
        user, token = finance_user
        fake_id = uuid4()

        # Use valid status value (active, paused, or ended)
        response = client.patch(
            f"/api/v1/finance/partnerships/{fake_id}",
            json={"status": "active"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400

    def test_delete_partnership_not_found(
        self, client: TestClient, finance_user
    ):
        """Test deleting non-existent partnership."""
        user, token = finance_user
        fake_id = uuid4()

        response = client.delete(
            f"/api/v1/finance/partnerships/{fake_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400

    def test_get_partnership_fulfilment_not_found(
        self, client: TestClient, finance_user
    ):
        """Test getting fulfilment for non-existent partnership."""
        user, token = finance_user
        fake_id = uuid4()

        response = client.get(
            f"/api/v1/finance/partnerships/{fake_id}/fulfilment",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400
