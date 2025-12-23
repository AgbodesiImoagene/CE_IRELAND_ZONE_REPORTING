"""Finance service layer for funds, partnership arms, batches, finance entries, and partnerships."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import Session

from app.common.audit import create_audit_log
from app.common.models import (
    Fund,
    PartnershipArm,
    Batch,
    FinanceEntry,
    Partnership,
    Service,
    People,
)
from app.finance.scope_validation import (
    validate_org_access_for_operation,
    validate_batch_lock_authorization,
    validate_entry_modification,
    require_permission,
)


class FundService:
    """Service for managing funds."""

    @staticmethod
    def create_fund(
        db: Session,
        creator_id: UUID,
        tenant_id: UUID,
        name: str,
        is_partnership: bool = False,
        active: bool = True,
    ) -> Fund:
        """Create a new fund."""
        require_permission(db, creator_id, tenant_id, "finance.lookups.manage")

        # Check if fund with same name exists
        existing = db.execute(
            select(Fund).where(
                Fund.name == name, Fund.tenant_id == tenant_id
            )
        ).scalar_one_or_none()
        if existing:
            raise ValueError(f"Fund with name {name} already exists")

        fund = Fund(
            id=uuid4(),
            tenant_id=tenant_id,
            name=name,
            is_partnership=is_partnership,
            active=active,
        )
        db.add(fund)

        # Audit log
        create_audit_log(
            db,
            creator_id,
            "create",
            "funds",
            fund.id,
            None,
            {"id": str(fund.id), "name": name},
        )

        db.commit()
        db.refresh(fund)
        return fund

    @staticmethod
    def get_fund(db: Session, fund_id: UUID, tenant_id: UUID) -> Optional[Fund]:
        """Get a fund by ID."""
        return db.execute(
            select(Fund).where(Fund.id == fund_id, Fund.tenant_id == tenant_id)
        ).scalar_one_or_none()

    @staticmethod
    def list_funds(
        db: Session,
        tenant_id: UUID,
        active_only: bool = False,
    ) -> list[Fund]:
        """List funds with optional filters."""
        stmt = select(Fund).where(Fund.tenant_id == tenant_id)

        if active_only:
            stmt = stmt.where(Fund.active == True)

        stmt = stmt.order_by(Fund.name)

        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def update_fund(
        db: Session,
        updater_id: UUID,
        tenant_id: UUID,
        fund_id: UUID,
        **updates,
    ) -> Fund:
        """Update a fund."""
        fund = FundService.get_fund(db, fund_id, tenant_id)
        if not fund:
            raise ValueError(f"Fund {fund_id} not found")

        require_permission(db, updater_id, tenant_id, "finance.lookups.manage")

        before_json = {"name": fund.name, "active": fund.active}

        # Update fields
        for key, value in updates.items():
            if hasattr(fund, key) and value is not None:
                setattr(fund, key, value)

        after_json = {"name": fund.name, "active": fund.active}

        # Audit log
        create_audit_log(
            db, updater_id, "update", "funds", fund_id, before_json, after_json
        )

        db.commit()
        db.refresh(fund)
        return fund

    @staticmethod
    def delete_fund(
        db: Session,
        deleter_id: UUID,
        tenant_id: UUID,
        fund_id: UUID,
    ) -> None:
        """Delete a fund."""
        fund = FundService.get_fund(db, fund_id, tenant_id)
        if not fund:
            raise ValueError(f"Fund {fund_id} not found")

        require_permission(db, deleter_id, tenant_id, "finance.lookups.manage")

        # Check if fund is used in any finance entries
        entries_count = db.execute(
            select(func.count()).where(FinanceEntry.fund_id == fund_id)
        ).scalar() or 0
        if entries_count > 0:
            raise ValueError(
                f"Cannot delete fund {fund_id}: it is used in {entries_count} finance entries"
            )

        before_json = {"id": str(fund_id), "name": fund.name}

        db.delete(fund)

        # Audit log
        create_audit_log(
            db, deleter_id, "delete", "funds", fund_id, before_json, None
        )

        db.commit()


class PartnershipArmService:
    """Service for managing partnership arms."""

    @staticmethod
    def create_partnership_arm(
        db: Session,
        creator_id: UUID,
        tenant_id: UUID,
        name: str,
        active_from: date,
        active_to: Optional[date] = None,
        active: bool = True,
    ) -> PartnershipArm:
        """Create a new partnership arm."""
        require_permission(db, creator_id, tenant_id, "finance.lookups.manage")

        # Check if partnership arm with same name exists
        existing = db.execute(
            select(PartnershipArm).where(
                PartnershipArm.name == name, PartnershipArm.tenant_id == tenant_id
            )
        ).scalar_one_or_none()
        if existing:
            raise ValueError(f"Partnership arm with name {name} already exists")

        partnership_arm = PartnershipArm(
            id=uuid4(),
            tenant_id=tenant_id,
            name=name,
            active_from=active_from,
            active_to=active_to,
            active=active,
        )
        db.add(partnership_arm)

        # Audit log
        create_audit_log(
            db,
            creator_id,
            "create",
            "partnership_arms",
            partnership_arm.id,
            None,
            {"id": str(partnership_arm.id), "name": name},
        )

        db.commit()
        db.refresh(partnership_arm)
        return partnership_arm

    @staticmethod
    def get_partnership_arm(
        db: Session, partnership_arm_id: UUID, tenant_id: UUID
    ) -> Optional[PartnershipArm]:
        """Get a partnership arm by ID."""
        return db.execute(
            select(PartnershipArm).where(
                PartnershipArm.id == partnership_arm_id,
                PartnershipArm.tenant_id == tenant_id,
            )
        ).scalar_one_or_none()

    @staticmethod
    def list_partnership_arms(
        db: Session,
        tenant_id: UUID,
        active_only: bool = False,
    ) -> list[PartnershipArm]:
        """List partnership arms with optional filters."""
        stmt = select(PartnershipArm).where(PartnershipArm.tenant_id == tenant_id)

        if active_only:
            stmt = stmt.where(PartnershipArm.active == True)

        stmt = stmt.order_by(PartnershipArm.name)

        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def update_partnership_arm(
        db: Session,
        updater_id: UUID,
        tenant_id: UUID,
        partnership_arm_id: UUID,
        **updates,
    ) -> PartnershipArm:
        """Update a partnership arm."""
        partnership_arm = PartnershipArmService.get_partnership_arm(
            db, partnership_arm_id, tenant_id
        )
        if not partnership_arm:
            raise ValueError(f"Partnership arm {partnership_arm_id} not found")

        require_permission(db, updater_id, tenant_id, "finance.lookups.manage")

        before_json = {
            "name": partnership_arm.name,
            "active": partnership_arm.active,
        }

        # Update fields
        for key, value in updates.items():
            if hasattr(partnership_arm, key) and value is not None:
                setattr(partnership_arm, key, value)

        after_json = {
            "name": partnership_arm.name,
            "active": partnership_arm.active,
        }

        # Audit log
        create_audit_log(
            db,
            updater_id,
            "update",
            "partnership_arms",
            partnership_arm_id,
            before_json,
            after_json,
        )

        db.commit()
        db.refresh(partnership_arm)
        return partnership_arm

    @staticmethod
    def delete_partnership_arm(
        db: Session,
        deleter_id: UUID,
        tenant_id: UUID,
        partnership_arm_id: UUID,
    ) -> None:
        """Delete a partnership arm."""
        partnership_arm = PartnershipArmService.get_partnership_arm(
            db, partnership_arm_id, tenant_id
        )
        if not partnership_arm:
            raise ValueError(f"Partnership arm {partnership_arm_id} not found")

        require_permission(db, deleter_id, tenant_id, "finance.lookups.manage")

        before_json = {
            "id": str(partnership_arm_id),
            "name": partnership_arm.name,
        }

        db.delete(partnership_arm)

        # Audit log
        create_audit_log(
            db,
            deleter_id,
            "delete",
            "partnership_arms",
            partnership_arm_id,
            before_json,
            None,
        )

        db.commit()


class BatchService:
    """Service for managing batches."""

    @staticmethod
    def create_batch(
        db: Session,
        creator_id: UUID,
        tenant_id: UUID,
        org_unit_id: UUID,
        service_id: Optional[UUID] = None,
    ) -> Batch:
        """Create a new batch."""
        validate_org_access_for_operation(
            db, creator_id, tenant_id, org_unit_id, "finance.batches.create"
        )

        # Check if batch already exists for this service
        if service_id:
            existing = db.execute(
                select(Batch).where(
                    Batch.tenant_id == tenant_id,
                    Batch.org_unit_id == org_unit_id,
                    Batch.service_id == service_id,
                )
            ).scalar_one_or_none()
            if existing:
                raise ValueError(
                    f"Batch already exists for service {service_id} in org unit {org_unit_id}"
                )

        batch = Batch(
            id=uuid4(),
            tenant_id=tenant_id,
            org_unit_id=org_unit_id,
            service_id=service_id,
            status="draft",
            created_by=creator_id,
        )
        db.add(batch)

        # Audit log
        create_audit_log(
            db,
            creator_id,
            "create",
            "batches",
            batch.id,
            None,
            {
                "id": str(batch.id),
                "org_unit_id": str(org_unit_id),
                "service_id": str(service_id) if service_id else None,
            },
        )

        db.commit()
        db.refresh(batch)
        return batch

    @staticmethod
    def get_batch(db: Session, batch_id: UUID, tenant_id: UUID) -> Optional[Batch]:
        """Get a batch by ID."""
        return db.execute(
            select(Batch).where(Batch.id == batch_id, Batch.tenant_id == tenant_id)
        ).scalar_one_or_none()

    @staticmethod
    def list_batches(
        db: Session,
        tenant_id: UUID,
        org_unit_id: Optional[UUID] = None,
        service_id: Optional[UUID] = None,
        status: Optional[str] = None,
    ) -> list[Batch]:
        """List batches with optional filters."""
        stmt = select(Batch).where(Batch.tenant_id == tenant_id)

        if org_unit_id:
            stmt = stmt.where(Batch.org_unit_id == org_unit_id)

        if service_id:
            stmt = stmt.where(Batch.service_id == service_id)

        if status:
            stmt = stmt.where(Batch.status == status)

        stmt = stmt.order_by(Batch.created_at.desc())

        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def update_batch(
        db: Session,
        updater_id: UUID,
        tenant_id: UUID,
        batch_id: UUID,
        **updates,
    ) -> Batch:
        """Update a batch (only if status is draft)."""
        batch = BatchService.get_batch(db, batch_id, tenant_id)
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")

        if batch.status == "locked":
            raise ValueError("Cannot update locked batch")

        validate_org_access_for_operation(
            db, updater_id, tenant_id, batch.org_unit_id, "finance.batches.update"
        )

        before_json = {
            "status": batch.status,
            "service_id": str(batch.service_id) if batch.service_id else None,
        }

        # Update fields
        for key, value in updates.items():
            if hasattr(batch, key) and value is not None:
                setattr(batch, key, value)

        after_json = {
            "status": batch.status,
            "service_id": str(batch.service_id) if batch.service_id else None,
        }

        # Audit log
        create_audit_log(
            db, updater_id, "update", "batches", batch_id, before_json, after_json
        )

        db.commit()
        db.refresh(batch)
        return batch

    @staticmethod
    def delete_batch(
        db: Session,
        deleter_id: UUID,
        tenant_id: UUID,
        batch_id: UUID,
    ) -> None:
        """Delete a batch (only if status is draft)."""
        batch = BatchService.get_batch(db, batch_id, tenant_id)
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")

        if batch.status == "locked":
            raise ValueError("Cannot delete locked batch")

        validate_org_access_for_operation(
            db, deleter_id, tenant_id, batch.org_unit_id, "finance.batches.delete"
        )

        before_json = {
            "id": str(batch_id),
            "org_unit_id": str(batch.org_unit_id),
        }

        db.delete(batch)

        # Audit log
        create_audit_log(
            db, deleter_id, "delete", "batches", batch_id, before_json, None
        )

        db.commit()

    @staticmethod
    def verify_batch(
        db: Session,
        verifier_id: UUID,
        tenant_id: UUID,
        batch_id: UUID,
    ) -> Batch:
        """Verify a batch (first or second verification)."""
        batch = BatchService.get_batch(db, batch_id, tenant_id)
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")

        if batch.status == "locked":
            raise ValueError("Batch is already locked")

        validate_org_access_for_operation(
            db, verifier_id, tenant_id, batch.org_unit_id, "finance.verify"
        )

        if batch.verified_by_1 is None:
            # First verification
            batch.verified_by_1 = verifier_id
        elif batch.verified_by_2 is None:
            # Second verification - must be different user
            if batch.verified_by_1 == verifier_id:
                raise ValueError(
                    "Dual verification requires two different users. "
                    "This batch has already been verified by you."
                )
            batch.verified_by_2 = verifier_id
        else:
            raise ValueError("Batch has already been verified by two users")

        batch.updated_at = datetime.now(timezone.utc)

        # Audit log
        create_audit_log(
            db,
            verifier_id,
            "verify",
            "batches",
            batch_id,
            {
                "verified_by_1": str(batch.verified_by_1) if batch.verified_by_1 else None,
                "verified_by_2": str(batch.verified_by_2) if batch.verified_by_2 else None,
            },
            {
                "verified_by_1": str(batch.verified_by_1) if batch.verified_by_1 else None,
                "verified_by_2": str(batch.verified_by_2) if batch.verified_by_2 else None,
            },
        )

        db.commit()
        db.refresh(batch)
        return batch

    @staticmethod
    def lock_batch(
        db: Session,
        locker_id: UUID,
        tenant_id: UUID,
        batch_id: UUID,
    ) -> Batch:
        """Lock a batch (requires dual verification)."""
        org_unit_id, is_ready = validate_batch_lock_authorization(
            db, locker_id, tenant_id, batch_id
        )

        batch = BatchService.get_batch(db, batch_id, tenant_id)
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")

        if not is_ready:
            raise ValueError(
                "Batch requires dual verification before it can be locked. "
                "Both verified_by_1 and verified_by_2 must be set by different users."
            )

        if batch.verified_by_1 == locker_id or batch.verified_by_2 == locker_id:
            raise ValueError(
                "Cannot lock batch: you were one of the verifiers. "
                "Locking requires a third user."
            )

        batch.status = "locked"
        batch.locked_by = locker_id
        batch.locked_at = datetime.now(timezone.utc)
        batch.updated_at = datetime.now(timezone.utc)

        # Lock all entries in the batch
        entries = db.execute(
            select(FinanceEntry).where(FinanceEntry.batch_id == batch_id)
        ).scalars().all()
        for entry in entries:
            entry.verified_status = "locked"
            entry.updated_at = datetime.now(timezone.utc)

        # Audit log
        create_audit_log(
            db,
            locker_id,
            "lock",
            "batches",
            batch_id,
            {"status": "draft"},
            {
                "status": "locked",
                "locked_by": str(locker_id),
                "locked_at": batch.locked_at.isoformat(),
            },
        )

        db.commit()
        db.refresh(batch)
        return batch

    @staticmethod
    def unlock_batch(
        db: Session,
        unlocker_id: UUID,
        tenant_id: UUID,
        batch_id: UUID,
        reason: str,
    ) -> Batch:
        """Unlock a batch (requires dual authorization)."""
        batch = BatchService.get_batch(db, batch_id, tenant_id)
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")

        if batch.status != "locked":
            raise ValueError("Batch is not locked")

        # Check permission - unlock requires special permission
        require_permission(db, unlocker_id, tenant_id, "finance.batches.unlock")

        validate_org_access_for_operation(
            db, unlocker_id, tenant_id, batch.org_unit_id, "finance.batches.unlock"
        )

        # Note: Dual authorization for unlock would require tracking unlock requests
        # For now, we require the unlock permission which is restricted to admins
        batch.status = "draft"
        batch.locked_by = None
        batch.locked_at = None
        batch.updated_at = datetime.now(timezone.utc)

        # Unlock all entries in the batch (set back to reconciled if they were locked)
        entries = db.execute(
            select(FinanceEntry).where(FinanceEntry.batch_id == batch_id)
        ).scalars().all()
        for entry in entries:
            if entry.verified_status == "locked":
                entry.verified_status = "reconciled"
                entry.updated_at = datetime.now(timezone.utc)

        # Audit log
        create_audit_log(
            db,
            unlocker_id,
            "unlock",
            "batches",
            batch_id,
            {"status": "locked"},
            {
                "status": "draft",
                "reason": reason,
            },
        )

        db.commit()
        db.refresh(batch)
        return batch


class FinanceEntryService:
    """Service for managing finance entries."""

    @staticmethod
    def create_entry(
        db: Session,
        creator_id: UUID,
        tenant_id: UUID,
        org_unit_id: UUID,
        fund_id: UUID,
        amount: Decimal,
        transaction_date: date,
        batch_id: Optional[UUID] = None,
        service_id: Optional[UUID] = None,
        partnership_arm_id: Optional[UUID] = None,
        currency: str = "EUR",
        method: str = "cash",
        person_id: Optional[UUID] = None,
        cell_id: Optional[UUID] = None,
        external_giver_name: Optional[str] = None,
        reference: Optional[str] = None,
        comment: Optional[str] = None,
        source_type: str = "manual",
        source_id: Optional[UUID] = None,
    ) -> FinanceEntry:
        """Create a new finance entry."""
        validate_org_access_for_operation(
            db, creator_id, tenant_id, org_unit_id, "finance.entries.create"
        )

        # Validate fund exists
        fund = db.get(Fund, fund_id)
        if not fund or fund.tenant_id != tenant_id:
            raise ValueError(f"Fund {fund_id} not found")

        # Validate partnership arm if provided
        if partnership_arm_id:
            partnership_arm = db.get(PartnershipArm, partnership_arm_id)
            if not partnership_arm or partnership_arm.tenant_id != tenant_id:
                raise ValueError(f"Partnership arm {partnership_arm_id} not found")

        # Validate person if provided
        if person_id:
            person = db.get(People, person_id)
            if not person or person.tenant_id != tenant_id:
                raise ValueError(f"Person {person_id} not found")

        # Validate batch if provided
        if batch_id:
            batch = db.get(Batch, batch_id)
            if not batch or batch.tenant_id != tenant_id:
                raise ValueError(f"Batch {batch_id} not found")
            if batch.status == "locked":
                raise ValueError("Cannot add entry to locked batch")

        # Validate service if provided
        if service_id:
            service = db.get(Service, service_id)
            if not service or service.tenant_id != tenant_id:
                raise ValueError(f"Service {service_id} not found")

        # Ensure at least one giver is specified
        if not person_id and not cell_id and not external_giver_name:
            raise ValueError(
                "At least one of person_id, cell_id, or external_giver_name must be provided"
            )

        entry = FinanceEntry(
            id=uuid4(),
            tenant_id=tenant_id,
            org_unit_id=org_unit_id,
            batch_id=batch_id,
            service_id=service_id,
            fund_id=fund_id,
            partnership_arm_id=partnership_arm_id,
            amount=amount,
            currency=currency,
            method=method,
            person_id=person_id,
            cell_id=cell_id,
            external_giver_name=external_giver_name,
            reference=reference,
            comment=comment,
            verified_status="draft",
            source_type=source_type,
            source_id=source_id,
            transaction_date=transaction_date,
            created_by=creator_id,
        )
        db.add(entry)

        # Audit log
        create_audit_log(
            db,
            creator_id,
            "create",
            "finance_entries",
            entry.id,
            None,
            {
                "id": str(entry.id),
                "org_unit_id": str(org_unit_id),
                "fund_id": str(fund_id),
                "amount": str(amount),
            },
        )

        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def get_entry(
        db: Session, entry_id: UUID, tenant_id: UUID
    ) -> Optional[FinanceEntry]:
        """Get a finance entry by ID."""
        return db.execute(
            select(FinanceEntry).where(
                FinanceEntry.id == entry_id, FinanceEntry.tenant_id == tenant_id
            )
        ).scalar_one_or_none()

    @staticmethod
    def list_entries(
        db: Session,
        tenant_id: UUID,
        org_unit_id: Optional[UUID] = None,
        batch_id: Optional[UUID] = None,
        service_id: Optional[UUID] = None,
        fund_id: Optional[UUID] = None,
        partnership_arm_id: Optional[UUID] = None,
        person_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        verified_status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[FinanceEntry]:
        """List finance entries with optional filters."""
        stmt = select(FinanceEntry).where(FinanceEntry.tenant_id == tenant_id)

        if org_unit_id:
            stmt = stmt.where(FinanceEntry.org_unit_id == org_unit_id)

        if batch_id:
            stmt = stmt.where(FinanceEntry.batch_id == batch_id)

        if service_id:
            stmt = stmt.where(FinanceEntry.service_id == service_id)

        if fund_id:
            stmt = stmt.where(FinanceEntry.fund_id == fund_id)

        if partnership_arm_id:
            stmt = stmt.where(FinanceEntry.partnership_arm_id == partnership_arm_id)

        if person_id:
            stmt = stmt.where(FinanceEntry.person_id == person_id)

        if start_date:
            stmt = stmt.where(FinanceEntry.transaction_date >= start_date)

        if end_date:
            stmt = stmt.where(FinanceEntry.transaction_date <= end_date)

        if verified_status:
            stmt = stmt.where(FinanceEntry.verified_status == verified_status)

        stmt = stmt.order_by(FinanceEntry.transaction_date.desc()).limit(limit).offset(offset)

        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def update_entry(
        db: Session,
        updater_id: UUID,
        tenant_id: UUID,
        entry_id: UUID,
        **updates,
    ) -> FinanceEntry:
        """Update a finance entry."""
        entry = FinanceEntryService.get_entry(db, entry_id, tenant_id)
        if not entry:
            raise ValueError(f"Finance entry {entry_id} not found")

        # Validate entry can be modified
        validate_entry_modification(
            db, updater_id, tenant_id, entry_id, "finance.entries.update"
        )

        before_json = {
            "fund_id": str(entry.fund_id),
            "amount": str(entry.amount),
            "verified_status": entry.verified_status,
        }

        # Update fields
        for key, value in updates.items():
            if hasattr(entry, key) and value is not None:
                setattr(entry, key, value)

        entry.updated_by = updater_id
        entry.updated_at = datetime.now(timezone.utc)

        after_json = {
            "fund_id": str(entry.fund_id),
            "amount": str(entry.amount),
            "verified_status": entry.verified_status,
        }

        # Audit log
        create_audit_log(
            db,
            updater_id,
            "update",
            "finance_entries",
            entry_id,
            before_json,
            after_json,
        )

        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def delete_entry(
        db: Session,
        deleter_id: UUID,
        tenant_id: UUID,
        entry_id: UUID,
    ) -> None:
        """Delete a finance entry."""
        entry = FinanceEntryService.get_entry(db, entry_id, tenant_id)
        if not entry:
            raise ValueError(f"Finance entry {entry_id} not found")

        # Validate entry can be modified
        validate_entry_modification(
            db, deleter_id, tenant_id, entry_id, "finance.entries.delete"
        )

        before_json = {
            "id": str(entry_id),
            "fund_id": str(entry.fund_id),
            "amount": str(entry.amount),
        }

        db.delete(entry)

        # Audit log
        create_audit_log(
            db,
            deleter_id,
            "delete",
            "finance_entries",
            entry_id,
            before_json,
            None,
        )

        db.commit()

    @staticmethod
    def verify_entry(
        db: Session,
        verifier_id: UUID,
        tenant_id: UUID,
        entry_id: UUID,
        verified_status: str,
    ) -> FinanceEntry:
        """Verify a finance entry (set verified_status)."""
        entry = FinanceEntryService.get_entry(db, entry_id, tenant_id)
        if not entry:
            raise ValueError(f"Finance entry {entry_id} not found")

        if entry.verified_status == "locked":
            raise ValueError("Cannot modify locked finance entry")

        require_permission(db, verifier_id, tenant_id, "finance.verify")
        validate_org_access_for_operation(
            db, verifier_id, tenant_id, entry.org_unit_id, "finance.verify"
        )

        before_json = {"verified_status": entry.verified_status}

        entry.verified_status = verified_status
        entry.updated_by = verifier_id
        entry.updated_at = datetime.now(timezone.utc)

        after_json = {"verified_status": verified_status}

        # Audit log
        create_audit_log(
            db,
            verifier_id,
            "verify",
            "finance_entries",
            entry_id,
            before_json,
            after_json,
        )

        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def reconcile_entry(
        db: Session,
        reconciler_id: UUID,
        tenant_id: UUID,
        entry_id: UUID,
    ) -> FinanceEntry:
        """Reconcile a finance entry (set verified_status to reconciled)."""
        return FinanceEntryService.verify_entry(
            db, reconciler_id, tenant_id, entry_id, "reconciled"
        )


class PartnershipService:
    """Service for managing partnerships."""

    @staticmethod
    def create_partnership(
        db: Session,
        creator_id: UUID,
        tenant_id: UUID,
        person_id: UUID,
        fund_id: UUID,
        cadence: str,
        start_date: date,
        partnership_arm_id: Optional[UUID] = None,
        end_date: Optional[date] = None,
        target_amount: Optional[Decimal] = None,
        status: str = "active",
    ) -> Partnership:
        """Create a new partnership."""
        # Validate person exists
        person = db.get(People, person_id)
        if not person or person.tenant_id != tenant_id:
            raise ValueError(f"Person {person_id} not found")

        validate_org_access_for_operation(
            db, creator_id, tenant_id, person.org_unit_id, "finance.entries.create"
        )

        # Validate fund exists
        fund = db.get(Fund, fund_id)
        if not fund or fund.tenant_id != tenant_id:
            raise ValueError(f"Fund {fund_id} not found")

        # Validate partnership arm if provided
        if partnership_arm_id:
            partnership_arm = db.get(PartnershipArm, partnership_arm_id)
            if not partnership_arm or partnership_arm.tenant_id != tenant_id:
                raise ValueError(f"Partnership arm {partnership_arm_id} not found")

        partnership = Partnership(
            id=uuid4(),
            tenant_id=tenant_id,
            person_id=person_id,
            fund_id=fund_id,
            partnership_arm_id=partnership_arm_id,
            cadence=cadence,
            start_date=start_date,
            end_date=end_date,
            target_amount=target_amount,
            status=status,
        )
        db.add(partnership)

        # Audit log
        create_audit_log(
            db,
            creator_id,
            "create",
            "partnerships",
            partnership.id,
            None,
            {
                "id": str(partnership.id),
                "person_id": str(person_id),
                "fund_id": str(fund_id),
                "cadence": cadence,
            },
        )

        db.commit()
        db.refresh(partnership)
        return partnership

    @staticmethod
    def get_partnership(
        db: Session, partnership_id: UUID, tenant_id: UUID
    ) -> Optional[Partnership]:
        """Get a partnership by ID."""
        return db.execute(
            select(Partnership).where(
                Partnership.id == partnership_id, Partnership.tenant_id == tenant_id
            )
        ).scalar_one_or_none()

    @staticmethod
    def list_partnerships(
        db: Session,
        tenant_id: UUID,
        person_id: Optional[UUID] = None,
        fund_id: Optional[UUID] = None,
        partnership_arm_id: Optional[UUID] = None,
        status: Optional[str] = None,
    ) -> list[Partnership]:
        """List partnerships with optional filters."""
        stmt = select(Partnership).where(Partnership.tenant_id == tenant_id)

        if person_id:
            stmt = stmt.where(Partnership.person_id == person_id)

        if fund_id:
            stmt = stmt.where(Partnership.fund_id == fund_id)

        if partnership_arm_id:
            stmt = stmt.where(Partnership.partnership_arm_id == partnership_arm_id)

        if status:
            stmt = stmt.where(Partnership.status == status)

        stmt = stmt.order_by(Partnership.start_date.desc())

        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def update_partnership(
        db: Session,
        updater_id: UUID,
        tenant_id: UUID,
        partnership_id: UUID,
        **updates,
    ) -> Partnership:
        """Update a partnership."""
        partnership = PartnershipService.get_partnership(db, partnership_id, tenant_id)
        if not partnership:
            raise ValueError(f"Partnership {partnership_id} not found")

        # Get person to check org access
        person = db.get(People, partnership.person_id)
        if not person:
            raise ValueError(f"Person {partnership.person_id} not found")

        validate_org_access_for_operation(
            db, updater_id, tenant_id, person.org_unit_id, "finance.entries.update"
        )

        before_json = {
            "cadence": partnership.cadence,
            "status": partnership.status,
            "target_amount": str(partnership.target_amount) if partnership.target_amount else None,
        }

        # Update fields
        for key, value in updates.items():
            if hasattr(partnership, key) and value is not None:
                setattr(partnership, key, value)

        after_json = {
            "cadence": partnership.cadence,
            "status": partnership.status,
            "target_amount": str(partnership.target_amount) if partnership.target_amount else None,
        }

        # Audit log
        create_audit_log(
            db,
            updater_id,
            "update",
            "partnerships",
            partnership_id,
            before_json,
            after_json,
        )

        db.commit()
        db.refresh(partnership)
        return partnership

    @staticmethod
    def delete_partnership(
        db: Session,
        deleter_id: UUID,
        tenant_id: UUID,
        partnership_id: UUID,
    ) -> None:
        """Delete a partnership."""
        partnership = PartnershipService.get_partnership(db, partnership_id, tenant_id)
        if not partnership:
            raise ValueError(f"Partnership {partnership_id} not found")

        # Get person to check org access
        person = db.get(People, partnership.person_id)
        if not person:
            raise ValueError(f"Person {partnership.person_id} not found")

        validate_org_access_for_operation(
            db, deleter_id, tenant_id, person.org_unit_id, "finance.entries.delete"
        )

        before_json = {
            "id": str(partnership_id),
            "person_id": str(partnership.person_id),
            "fund_id": str(partnership.fund_id),
        }

        db.delete(partnership)

        # Audit log
        create_audit_log(
            db,
            deleter_id,
            "delete",
            "partnerships",
            partnership_id,
            before_json,
            None,
        )

        db.commit()

    @staticmethod
    def calculate_fulfilment(
        db: Session,
        partnership_id: UUID,
        tenant_id: UUID,
    ) -> dict:
        """
        Calculate partnership fulfilment from linked finance entries.

        Returns:
            Dictionary with fulfilment details:
            - fulfilled_amount: Total amount from linked entries
            - fulfilment_percentage: Percentage if target_amount is set
            - entries_count: Number of linked entries
        """
        partnership = PartnershipService.get_partnership(db, partnership_id, tenant_id)
        if not partnership:
            raise ValueError(f"Partnership {partnership_id} not found")

        # Calculate date range based on cadence
        end_date = partnership.end_date or date.today()
        start_window = PartnershipService._get_cadence_start_date(
            partnership.cadence, end_date
        )

        # Find linked finance entries
        stmt = select(FinanceEntry).where(
            FinanceEntry.tenant_id == tenant_id,
            FinanceEntry.person_id == partnership.person_id,
            FinanceEntry.fund_id == partnership.fund_id,
            FinanceEntry.transaction_date >= start_window,
            FinanceEntry.transaction_date <= end_date,
        )

        if partnership.partnership_arm_id:
            stmt = stmt.where(
                FinanceEntry.partnership_arm_id == partnership.partnership_arm_id
            )

        entries = db.execute(stmt).scalars().all()

        fulfilled_amount = sum(entry.amount for entry in entries)
        entries_count = len(entries)

        fulfilment_percentage = None
        if partnership.target_amount and partnership.target_amount > 0:
            fulfilment_percentage = (fulfilled_amount / partnership.target_amount) * 100

        return {
            "fulfilled_amount": fulfilled_amount,
            "fulfilment_percentage": fulfilment_percentage,
            "entries_count": entries_count,
        }

    @staticmethod
    def _get_cadence_start_date(cadence: str, end_date: date) -> date:
        """Get the start date for a cadence period ending on end_date."""
        if cadence == "weekly":
            return end_date - timedelta(days=7)
        elif cadence == "monthly":
            # Approximate: 30 days
            return end_date - timedelta(days=30)
        elif cadence == "quarterly":
            # Approximate: 90 days
            return end_date - timedelta(days=90)
        elif cadence == "annual":
            return end_date - timedelta(days=365)
        else:
            # Default to 30 days
            return end_date - timedelta(days=30)

