"""Tests for Finance service layer."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

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
        ("finance.funds.update", "Update funds"),
        ("finance.funds.delete", "Delete funds"),
        ("finance.partnership_arms.create", "Create partnership arms"),
        ("finance.partnership_arms.update", "Update partnership arms"),
        ("finance.partnership_arms.delete", "Delete partnership arms"),
        ("finance.batches.create", "Create batches"),
        ("finance.batches.update", "Update batches"),
        ("finance.batches.delete", "Delete batches"),
        ("finance.batches.lock", "Lock batches"),
        ("finance.batches.unlock", "Unlock batches"),
        ("finance.entries.create", "Create finance entries"),
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
    from app.auth.utils import hash_password

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
    return user


@pytest.fixture
def test_fund(db, tenant_id, finance_user):
    """Create a test fund."""
    fund = FundService.create_fund(
        db=db,
        creator_id=finance_user.id,
        tenant_id=UUID(tenant_id),
        name="Tithe",
        is_partnership=False,
        active=True,
    )
    return fund


@pytest.fixture
def test_partnership_arm(db, tenant_id, finance_user):
    """Create a test partnership arm."""
    partnership_arm = PartnershipArmService.create_partnership_arm(
        db=db,
        creator_id=finance_user.id,
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


class TestFundService:
    """Test FundService methods."""

    def test_create_fund_success(self, db, tenant_id, finance_user):
        """Test creating a fund successfully."""
        fund = FundService.create_fund(
            db=db,
            creator_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            name="Offering",
            is_partnership=False,
            active=True,
        )

        assert fund is not None
        assert fund.name == "Offering"
        assert fund.is_partnership is False
        assert fund.active is True

    def test_create_fund_duplicate_name(self, db, tenant_id, finance_user, test_fund):
        """Test creating a fund with duplicate name fails."""
        with pytest.raises(ValueError, match="already exists"):
            FundService.create_fund(
                db=db,
                creator_id=finance_user.id,
                tenant_id=UUID(tenant_id),
                name="Tithe",
                is_partnership=False,
                active=True,
            )

    def test_get_fund_success(self, db, tenant_id, test_fund):
        """Test getting a fund by ID."""
        fund = FundService.get_fund(db, test_fund.id, UUID(tenant_id))
        assert fund is not None
        assert fund.id == test_fund.id
        assert fund.name == "Tithe"

    def test_list_funds(self, db, tenant_id, test_fund):
        """Test listing funds."""
        funds = FundService.list_funds(db, UUID(tenant_id))
        assert len(funds) >= 1
        assert any(f.id == test_fund.id for f in funds)

    def test_update_fund_success(self, db, tenant_id, finance_user, test_fund):
        """Test updating a fund."""
        fund = FundService.update_fund(
            db=db,
            updater_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            fund_id=test_fund.id,
            name="Updated Tithe",
            active=False,
        )

        assert fund.name == "Updated Tithe"
        assert fund.active is False

    def test_delete_fund_success(self, db, tenant_id, finance_user, test_fund):
        """Test deleting a fund."""
        FundService.delete_fund(
            db=db,
            deleter_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            fund_id=test_fund.id,
        )

        fund = FundService.get_fund(db, test_fund.id, UUID(tenant_id))
        assert fund is None

    def test_delete_fund_used_in_entries_fails(
        self, db, tenant_id, finance_user, test_fund, test_person, test_org_unit
    ):
        """Test deleting a fund used in entries fails."""
        # Create an entry using the fund
        entry = FinanceEntryService.create_entry(
            db=db,
            creator_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            fund_id=test_fund.id,
            amount=Decimal("100.00"),
            transaction_date=date.today(),
            person_id=test_person.id,  # Provide person_id as required
        )

        with pytest.raises(ValueError, match="used in"):
            FundService.delete_fund(
                db=db,
                deleter_id=finance_user.id,
                tenant_id=UUID(tenant_id),
                fund_id=test_fund.id,
            )


class TestPartnershipArmService:
    """Test PartnershipArmService methods."""

    def test_create_partnership_arm_success(self, db, tenant_id, finance_user):
        """Test creating a partnership arm successfully."""
        partnership_arm = PartnershipArmService.create_partnership_arm(
            db=db,
            creator_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            name="Healing School",
            active_from=date.today(),
            active=True,
        )

        assert partnership_arm is not None
        assert partnership_arm.name == "Healing School"
        assert partnership_arm.active is True

    def test_get_partnership_arm_success(
        self, db, tenant_id, test_partnership_arm
    ):
        """Test getting a partnership arm by ID."""
        partnership_arm = PartnershipArmService.get_partnership_arm(
            db, test_partnership_arm.id, UUID(tenant_id)
        )
        assert partnership_arm is not None
        assert partnership_arm.id == test_partnership_arm.id

    def test_list_partnership_arms(self, db, tenant_id, test_partnership_arm):
        """Test listing partnership arms."""
        partnership_arms = PartnershipArmService.list_partnership_arms(
            db, UUID(tenant_id)
        )
        assert len(partnership_arms) >= 1
        assert any(pa.id == test_partnership_arm.id for pa in partnership_arms)

    def test_update_partnership_arm_success(
        self, db, tenant_id, finance_user, test_partnership_arm
    ):
        """Test updating a partnership arm."""
        partnership_arm = PartnershipArmService.update_partnership_arm(
            db=db,
            updater_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            partnership_arm_id=test_partnership_arm.id,
            name="Updated Rhapsody",
            active=False,
        )

        assert partnership_arm.name == "Updated Rhapsody"
        assert partnership_arm.active is False

    def test_delete_partnership_arm_success(
        self, db, tenant_id, finance_user, test_partnership_arm
    ):
        """Test deleting a partnership arm."""
        PartnershipArmService.delete_partnership_arm(
            db=db,
            deleter_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            partnership_arm_id=test_partnership_arm.id,
        )

        partnership_arm = PartnershipArmService.get_partnership_arm(
            db, test_partnership_arm.id, UUID(tenant_id)
        )
        assert partnership_arm is None


class TestBatchService:
    """Test BatchService methods."""

    def test_create_batch_success(
        self, db, tenant_id, finance_user, test_org_unit, test_service
    ):
        """Test creating a batch successfully."""
        batch = BatchService.create_batch(
            db=db,
            creator_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            service_id=test_service.id,
        )

        assert batch is not None
        assert batch.org_unit_id == test_org_unit.id
        assert batch.service_id == test_service.id
        assert batch.status == "draft"

    def test_create_batch_duplicate_service_fails(
        self, db, tenant_id, finance_user, test_org_unit, test_service
    ):
        """Test creating duplicate batch for same service fails."""
        BatchService.create_batch(
            db=db,
            creator_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            service_id=test_service.id,
        )

        with pytest.raises(ValueError, match="already exists"):
            BatchService.create_batch(
                db=db,
                creator_id=finance_user.id,
                tenant_id=UUID(tenant_id),
                org_unit_id=test_org_unit.id,
                service_id=test_service.id,
            )

    def test_verify_batch_first_verification(
        self, db, tenant_id, finance_user, test_org_unit, test_service
    ):
        """Test first verification of a batch."""
        batch = BatchService.create_batch(
            db=db,
            creator_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            service_id=test_service.id,
        )

        batch = BatchService.verify_batch(
            db=db,
            verifier_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            batch_id=batch.id,
        )

        assert batch.verified_by_1 == finance_user.id
        assert batch.verified_by_2 is None

    def test_verify_batch_dual_verification(
        self, db, tenant_id, finance_user, finance_role, test_org_unit, test_service
    ):
        """Test dual verification of a batch."""
        from app.common.models import OrgAssignment, User
        from app.auth.utils import hash_password

        # Create second user
        user2 = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="finance2@example.com",
            password_hash=hash_password("testpass123"),
            is_active=True,
            is_2fa_enabled=False,
        )
        db.add(user2)
        db.flush()

        # Assign same role to user2
        assignment = OrgAssignment(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=user2.id,
            org_unit_id=test_org_unit.id,
            role_id=finance_role.id,  # Use finance_role.id (not finance_user.id)
        )
        db.add(assignment)
        db.commit()

        batch = BatchService.create_batch(
            db=db,
            creator_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            service_id=test_service.id,
        )

        # First verification
        batch = BatchService.verify_batch(
            db=db,
            verifier_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            batch_id=batch.id,
        )

        # Second verification
        batch = BatchService.verify_batch(
            db=db,
            verifier_id=user2.id,
            tenant_id=UUID(tenant_id),
            batch_id=batch.id,
        )

        assert batch.verified_by_1 == finance_user.id
        assert batch.verified_by_2 == user2.id

    def test_verify_batch_same_user_twice_fails(
        self, db, tenant_id, finance_user, test_org_unit, test_service
    ):
        """Test that same user cannot verify twice."""
        batch = BatchService.create_batch(
            db=db,
            creator_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            service_id=test_service.id,
        )

        BatchService.verify_batch(
            db=db,
            verifier_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            batch_id=batch.id,
        )

        with pytest.raises(ValueError, match="already been verified by you"):
            BatchService.verify_batch(
                db=db,
                verifier_id=finance_user.id,
                tenant_id=UUID(tenant_id),
                batch_id=batch.id,
            )

    def test_lock_batch_requires_dual_verification(
        self, db, tenant_id, finance_user, test_org_unit, test_service
    ):
        """Test that locking requires dual verification."""
        from app.common.models import OrgAssignment, User
        from app.auth.utils import hash_password

        # Create second and third users
        user2 = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="finance2@example.com",
            password_hash=hash_password("testpass123"),
            is_active=True,
            is_2fa_enabled=False,
        )
        db.add(user2)
        db.flush()

        user3 = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="finance3@example.com",
            password_hash=hash_password("testpass123"),
            is_active=True,
            is_2fa_enabled=False,
        )
        db.add(user3)
        db.flush()

        # Get finance role
        from app.common.models import Role
        role = db.execute(
            select(Role).where(Role.name == "Finance Role")
        ).scalar_one()

        # Assign roles
        for user in [user2, user3]:
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

        batch = BatchService.create_batch(
            db=db,
            creator_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            service_id=test_service.id,
        )

        # First verification
        batch = BatchService.verify_batch(
            db=db,
            verifier_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            batch_id=batch.id,
        )

        # Second verification
        batch = BatchService.verify_batch(
            db=db,
            verifier_id=user2.id,
            tenant_id=UUID(tenant_id),
            batch_id=batch.id,
        )

        # Lock by third user
        batch = BatchService.lock_batch(
            db=db,
            locker_id=user3.id,
            tenant_id=UUID(tenant_id),
            batch_id=batch.id,
        )

        assert batch.status == "locked"
        assert batch.locked_by == user3.id
        assert batch.locked_at is not None

    def test_lock_batch_without_dual_verification_fails(
        self, db, tenant_id, finance_user, test_org_unit, test_service
    ):
        """Test that locking without dual verification fails."""
        batch = BatchService.create_batch(
            db=db,
            creator_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            service_id=test_service.id,
        )

        with pytest.raises(ValueError, match="requires dual verification"):
            BatchService.lock_batch(
                db=db,
                locker_id=finance_user.id,
                tenant_id=UUID(tenant_id),
                batch_id=batch.id,
            )

    def test_update_locked_batch_fails(
        self, db, tenant_id, finance_user, test_org_unit, test_service
    ):
        """Test that updating a locked batch fails."""
        from app.common.models import OrgAssignment, User
        from app.auth.utils import hash_password

        # Create second and third users
        user2 = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="finance2@example.com",
            password_hash=hash_password("testpass123"),
            is_active=True,
            is_2fa_enabled=False,
        )
        db.add(user2)
        db.flush()

        user3 = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="finance3@example.com",
            password_hash=hash_password("testpass123"),
            is_active=True,
            is_2fa_enabled=False,
        )
        db.add(user3)
        db.flush()

        # Get finance role
        from app.common.models import Role
        role = db.execute(
            select(Role).where(Role.name == "Finance Role")
        ).scalar_one()

        # Assign roles
        for user in [user2, user3]:
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

        batch = BatchService.create_batch(
            db=db,
            creator_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            service_id=test_service.id,
        )

        # Verify and lock
        BatchService.verify_batch(
            db=db,
            verifier_id=finance_user.id,
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
        with pytest.raises(ValueError, match="locked"):
            BatchService.update_batch(
                db=db,
                updater_id=finance_user.id,
                tenant_id=UUID(tenant_id),
                batch_id=batch.id,
                service_id=test_service.id,
            )


class TestFinanceEntryService:
    """Test FinanceEntryService methods."""

    def test_create_entry_success(
        self, db, tenant_id, finance_user, test_org_unit, test_fund, test_person
    ):
        """Test creating a finance entry successfully."""
        entry = FinanceEntryService.create_entry(
            db=db,
            creator_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            fund_id=test_fund.id,
            amount=Decimal("100.00"),
            transaction_date=date.today(),
            person_id=test_person.id,
        )

        assert entry is not None
        assert entry.amount == Decimal("100.00")
        assert entry.fund_id == test_fund.id
        assert entry.person_id == test_person.id
        assert entry.verified_status == "draft"

    def test_create_entry_with_external_giver(
        self, db, tenant_id, finance_user, test_org_unit, test_fund
    ):
        """Test creating entry with external giver."""
        entry = FinanceEntryService.create_entry(
            db=db,
            creator_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            fund_id=test_fund.id,
            amount=Decimal("50.00"),
            transaction_date=date.today(),
            external_giver_name="Anonymous Donor",
        )

        assert entry.external_giver_name == "Anonymous Donor"
        assert entry.person_id is None

    def test_create_entry_no_giver_fails(
        self, db, tenant_id, finance_user, test_org_unit, test_fund
    ):
        """Test creating entry without any giver fails."""
        with pytest.raises(ValueError, match="At least one of"):
            FinanceEntryService.create_entry(
                db=db,
                creator_id=finance_user.id,
                tenant_id=UUID(tenant_id),
                org_unit_id=test_org_unit.id,
                fund_id=test_fund.id,
                amount=Decimal("100.00"),
                transaction_date=date.today(),
            )

    def test_create_entry_in_locked_batch_fails(
        self,
        db,
        tenant_id,
        finance_user,
        test_org_unit,
        test_fund,
        test_person,
        test_service,
    ):
        """Test creating entry in locked batch fails."""
        from app.common.models import OrgAssignment, User
        from app.auth.utils import hash_password

        # Create batch and lock it
        batch = BatchService.create_batch(
            db=db,
            creator_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            service_id=test_service.id,
        )

        # Create second and third users for verification
        user2 = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="finance2@example.com",
            password_hash=hash_password("testpass123"),
            is_active=True,
            is_2fa_enabled=False,
        )
        db.add(user2)
        db.flush()

        user3 = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="finance3@example.com",
            password_hash=hash_password("testpass123"),
            is_active=True,
            is_2fa_enabled=False,
        )
        db.add(user3)
        db.flush()

        # Get finance role
        from app.common.models import Role
        role = db.execute(
            select(Role).where(Role.name == "Finance Role")
        ).scalar_one()

        # Assign roles
        for user in [user2, user3]:
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

        # Verify and lock
        BatchService.verify_batch(
            db=db,
            verifier_id=finance_user.id,
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

        # Try to create entry in locked batch
        with pytest.raises(ValueError, match="locked batch"):
            FinanceEntryService.create_entry(
                db=db,
                creator_id=finance_user.id,
                tenant_id=UUID(tenant_id),
                org_unit_id=test_org_unit.id,
                fund_id=test_fund.id,
                amount=Decimal("100.00"),
                transaction_date=date.today(),
                person_id=test_person.id,
                batch_id=batch.id,
            )

    def test_update_entry_success(
        self, db, tenant_id, finance_user, test_org_unit, test_fund, test_person
    ):
        """Test updating a finance entry."""
        entry = FinanceEntryService.create_entry(
            db=db,
            creator_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            fund_id=test_fund.id,
            amount=Decimal("100.00"),
            transaction_date=date.today(),
            person_id=test_person.id,
        )

        entry = FinanceEntryService.update_entry(
            db=db,
            updater_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            entry_id=entry.id,
            amount=Decimal("150.00"),
            comment="Updated amount",
        )

        assert entry.amount == Decimal("150.00")
        assert entry.comment == "Updated amount"

    def test_update_locked_entry_fails(
        self, db, tenant_id, finance_user, test_org_unit, test_fund, test_person
    ):
        """Test updating a locked entry fails."""
        entry = FinanceEntryService.create_entry(
            db=db,
            creator_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            fund_id=test_fund.id,
            amount=Decimal("100.00"),
            transaction_date=date.today(),
            person_id=test_person.id,
        )

        # Lock the entry
        entry.verified_status = "locked"
        db.commit()

        with pytest.raises(ValueError, match="locked"):
            FinanceEntryService.update_entry(
                db=db,
                updater_id=finance_user.id,
                tenant_id=UUID(tenant_id),
                entry_id=entry.id,
                amount=Decimal("150.00"),
            )

    def test_verify_entry_success(
        self, db, tenant_id, finance_user, test_org_unit, test_fund, test_person
    ):
        """Test verifying a finance entry."""
        entry = FinanceEntryService.create_entry(
            db=db,
            creator_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            fund_id=test_fund.id,
            amount=Decimal("100.00"),
            transaction_date=date.today(),
            person_id=test_person.id,
        )

        entry = FinanceEntryService.verify_entry(
            db=db,
            verifier_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            entry_id=entry.id,
            verified_status="verified",
        )

        assert entry.verified_status == "verified"

    def test_reconcile_entry_success(
        self, db, tenant_id, finance_user, test_org_unit, test_fund, test_person
    ):
        """Test reconciling a finance entry."""
        entry = FinanceEntryService.create_entry(
            db=db,
            creator_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            fund_id=test_fund.id,
            amount=Decimal("100.00"),
            transaction_date=date.today(),
            person_id=test_person.id,
        )

        entry = FinanceEntryService.reconcile_entry(
            db=db,
            reconciler_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            entry_id=entry.id,
        )

        assert entry.verified_status == "reconciled"


class TestPartnershipService:
    """Test PartnershipService methods."""

    def test_create_partnership_success(
        self, db, tenant_id, finance_user, test_person, test_fund
    ):
        """Test creating a partnership successfully."""
        partnership = PartnershipService.create_partnership(
            db=db,
            creator_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            person_id=test_person.id,
            fund_id=test_fund.id,
            cadence="monthly",
            start_date=date.today(),
            target_amount=Decimal("1000.00"),
        )

        assert partnership is not None
        assert partnership.person_id == test_person.id
        assert partnership.fund_id == test_fund.id
        assert partnership.cadence == "monthly"
        assert partnership.target_amount == Decimal("1000.00")

    def test_get_fund_not_found(self, db, tenant_id):
        """Test getting non-existent fund."""
        fake_id = uuid4()
        fund = FundService.get_fund(db, fake_id, UUID(tenant_id))
        assert fund is None

    def test_list_funds_active_only(
        self, db, tenant_id, finance_user
    ):
        """Test listing only active funds."""
        user = finance_user

        # Create active and inactive funds
        active_fund = FundService.create_fund(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            name="Active Fund",
            active=True,
        )

        inactive_fund = FundService.create_fund(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            name="Inactive Fund",
            active=False,
        )

        # List all funds
        all_funds = FundService.list_funds(
            db=db, tenant_id=UUID(tenant_id), active_only=False
        )
        assert len(all_funds) >= 2

        # List only active funds
        active_funds = FundService.list_funds(
            db=db, tenant_id=UUID(tenant_id), active_only=True
        )
        assert all(f.active for f in active_funds)
        assert active_fund.id in [f.id for f in active_funds]
        assert inactive_fund.id not in [f.id for f in active_funds]

    def test_get_partnership_arm_not_found(self, db, tenant_id):
        """Test getting non-existent partnership arm."""
        fake_id = uuid4()
        arm = PartnershipArmService.get_partnership_arm(
            db, fake_id, UUID(tenant_id)
        )
        assert arm is None

    def test_list_partnership_arms_active_only(
        self, db, tenant_id, finance_user
    ):
        """Test listing only active partnership arms."""
        user = finance_user

        # Create active and inactive arms
        active_arm = PartnershipArmService.create_partnership_arm(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            name="Active Arm",
            active_from=date.today(),
            active=True,
        )

        inactive_arm = PartnershipArmService.create_partnership_arm(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            name="Inactive Arm",
            active_from=date.today(),
            active=False,
        )

        # List only active arms
        active_arms = PartnershipArmService.list_partnership_arms(
            db=db, tenant_id=UUID(tenant_id), active_only=True
        )
        assert all(pa.active for pa in active_arms)
        assert active_arm.id in [pa.id for pa in active_arms]
        assert inactive_arm.id not in [pa.id for pa in active_arms]

    def test_get_entry_not_found(self, db, tenant_id):
        """Test getting non-existent entry."""
        fake_id = uuid4()
        entry = FinanceEntryService.get_entry(db, fake_id, UUID(tenant_id))
        assert entry is None

    def test_calculate_fulfilment_success(
        self,
        db,
        tenant_id,
        finance_user,
        test_org_unit,
        test_person,
        test_fund,
    ):
        """Test calculating partnership fulfilment."""
        partnership = PartnershipService.create_partnership(
            db=db,
            creator_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            person_id=test_person.id,
            fund_id=test_fund.id,
            cadence="monthly",
            start_date=date.today(),
            target_amount=Decimal("1000.00"),
        )

        # Create some finance entries
        FinanceEntryService.create_entry(
            db=db,
            creator_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            fund_id=test_fund.id,
            amount=Decimal("300.00"),
            transaction_date=date.today(),
            person_id=test_person.id,
        )

        FinanceEntryService.create_entry(
            db=db,
            creator_id=finance_user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            fund_id=test_fund.id,
            amount=Decimal("200.00"),
            transaction_date=date.today(),
            person_id=test_person.id,
        )

        fulfilment = PartnershipService.calculate_fulfilment(
            db, partnership.id, UUID(tenant_id)
        )

        assert fulfilment["fulfilled_amount"] == Decimal("500.00")
        assert fulfilment["entries_count"] == 2
        assert fulfilment["fulfilment_percentage"] == Decimal("50.0")

    def test_unlock_batch_success(  # noqa: PLR0913
        self,
        db,
        tenant_id,
        finance_user,
        test_org_unit,
        test_fund,
        test_person,
        finance_role,
    ):
        """Test unlocking a locked batch."""
        from app.common.models import OrgAssignment, User
        from app.auth.utils import hash_password

        user = finance_user

        # Create second and third users for dual verification and locking
        user2 = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="finance2@example.com",
            password_hash=hash_password("testpass123"),
            is_active=True,
            is_2fa_enabled=False,
        )
        db.add(user2)
        db.flush()

        user3 = User(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            email="finance3@example.com",
            password_hash=hash_password("testpass123"),
            is_active=True,
            is_2fa_enabled=False,
        )
        db.add(user3)
        db.flush()

        # Assign same role to user2 and user3
        assignment2 = OrgAssignment(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=user2.id,
            org_unit_id=test_org_unit.id,
            role_id=finance_role.id,
        )
        db.add(assignment2)

        assignment3 = OrgAssignment(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=user3.id,
            org_unit_id=test_org_unit.id,
            role_id=finance_role.id,
        )
        db.add(assignment3)
        db.commit()

        # Create batch
        batch = BatchService.create_batch(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
        )

        # First verification
        batch = BatchService.verify_batch(
            db=db,
            verifier_id=user.id,
            tenant_id=UUID(tenant_id),
            batch_id=batch.id,
        )

        # Second verification
        batch = BatchService.verify_batch(
            db=db,
            verifier_id=user2.id,
            tenant_id=UUID(tenant_id),
            batch_id=batch.id,
        )

        # Lock the batch (requires third user who wasn't a verifier)
        batch = BatchService.lock_batch(
            db=db,
            locker_id=user3.id,
            tenant_id=UUID(tenant_id),
            batch_id=batch.id,
        )

        # Unlock the batch
        unlocked = BatchService.unlock_batch(
            db=db,
            unlocker_id=user3.id,
            tenant_id=UUID(tenant_id),
            batch_id=batch.id,
            reason="Correction needed",
        )

        assert unlocked.status == "draft"
        assert unlocked.locked_by is None
        assert unlocked.locked_at is None

    def test_unlock_batch_not_found(self, db, tenant_id, finance_user):
        """Test unlocking non-existent batch."""
        user = finance_user
        fake_id = uuid4()

        with pytest.raises(ValueError, match="not found"):
            BatchService.unlock_batch(
                db=db,
                unlocker_id=user.id,
                tenant_id=UUID(tenant_id),
                batch_id=fake_id,
                reason="Test",
            )

    def test_unlock_batch_not_locked(
        self, db, tenant_id, finance_user, test_org_unit
    ):
        """Test unlocking a batch that is not locked."""
        user = finance_user

        batch = BatchService.create_batch(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
        )

        with pytest.raises(ValueError, match="not locked"):
            BatchService.unlock_batch(
                db=db,
                unlocker_id=user.id,
                tenant_id=UUID(tenant_id),
                batch_id=batch.id,
                reason="Test",
            )

    def test_list_batches_with_filters(
        self, db, tenant_id, finance_user, test_org_unit, test_service
    ):
        """Test listing batches with filters."""
        user = finance_user

        # Create batches
        BatchService.create_batch(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
        )

        BatchService.create_batch(
            db=db,
            creator_id=user.id,
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            service_id=test_service.id,
        )

        # List all batches
        all_batches = BatchService.list_batches(
            db=db, tenant_id=UUID(tenant_id)
        )
        assert len(all_batches) >= 2

        # List with org_unit filter
        org_batches = BatchService.list_batches(
            db=db, tenant_id=UUID(tenant_id), org_unit_id=test_org_unit.id
        )
        assert all(b.org_unit_id == test_org_unit.id for b in org_batches)

        # List with service filter
        service_batches = BatchService.list_batches(
            db=db, tenant_id=UUID(tenant_id), service_id=test_service.id
        )
        assert all(
            b.service_id == test_service.id for b in service_batches if b.service_id
        )

        # List with status filter
        draft_batches = BatchService.list_batches(
            db=db, tenant_id=UUID(tenant_id), status="draft"
        )
        assert all(b.status == "draft" for b in draft_batches)

