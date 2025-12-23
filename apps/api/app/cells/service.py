"""Cells service layer for cells and cell reports."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.common.audit import create_audit_log
from app.common.models import (
    Cell,
    CellReport,
    People,
    Fund,
    FinanceEntry,
)
from app.cells.scope_validation import (
    validate_org_access_for_operation,
    require_permission,
)


class CellService:
    """Service for managing cells."""

    @staticmethod
    def create_cell(
        db: Session,
        creator_id: UUID,
        tenant_id: UUID,
        org_unit_id: UUID,
        name: str,
        leader_id: Optional[UUID] = None,
        assistant_leader_id: Optional[UUID] = None,
        venue: Optional[str] = None,
        meeting_day: Optional[str] = None,
        meeting_time: Optional[time] = None,
        status: str = "active",
    ) -> Cell:
        """Create a new cell."""
        validate_org_access_for_operation(
            db, creator_id, tenant_id, org_unit_id, "cells.manage"
        )

        # Check if cell with same name exists in this org unit
        existing = db.execute(
            select(Cell).where(
                Cell.tenant_id == tenant_id,
                Cell.org_unit_id == org_unit_id,
                Cell.name == name,
            )
        ).scalar_one_or_none()
        if existing:
            raise ValueError(
                f"Cell with name {name} already exists in this org unit"
            )

        # Validate leader if provided
        if leader_id:
            leader = db.get(People, leader_id)
            if not leader or leader.tenant_id != tenant_id:
                raise ValueError(f"Leader {leader_id} not found")

        # Validate assistant leader if provided
        if assistant_leader_id:
            assistant = db.get(People, assistant_leader_id)
            if not assistant or assistant.tenant_id != tenant_id:
                raise ValueError(f"Assistant leader {assistant_leader_id} not found")

        cell = Cell(
            id=uuid4(),
            tenant_id=tenant_id,
            org_unit_id=org_unit_id,
            name=name,
            leader_id=leader_id,
            assistant_leader_id=assistant_leader_id,
            venue=venue,
            meeting_day=meeting_day,
            meeting_time=meeting_time,
            status=status,
            created_by=creator_id,
        )
        db.add(cell)

        # Audit log
        create_audit_log(
            db,
            creator_id,
            "create",
            "cells",
            cell.id,
            None,
            {
                "id": str(cell.id),
                "org_unit_id": str(org_unit_id),
                "name": name,
            },
        )

        db.commit()
        db.refresh(cell)
        return cell

    @staticmethod
    def get_cell(db: Session, cell_id: UUID, tenant_id: UUID) -> Optional[Cell]:
        """Get a cell by ID."""
        return db.execute(
            select(Cell).where(Cell.id == cell_id, Cell.tenant_id == tenant_id)
        ).scalar_one_or_none()

    @staticmethod
    def list_cells(
        db: Session,
        tenant_id: UUID,
        org_unit_id: Optional[UUID] = None,
        status: Optional[str] = None,
        leader_id: Optional[UUID] = None,
    ) -> list[Cell]:
        """List cells with optional filters."""
        stmt = select(Cell).where(Cell.tenant_id == tenant_id)

        if org_unit_id:
            stmt = stmt.where(Cell.org_unit_id == org_unit_id)

        if status:
            stmt = stmt.where(Cell.status == status)

        if leader_id:
            stmt = stmt.where(Cell.leader_id == leader_id)

        stmt = stmt.order_by(Cell.name)

        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def update_cell(
        db: Session,
        updater_id: UUID,
        tenant_id: UUID,
        cell_id: UUID,
        **updates,
    ) -> Cell:
        """Update a cell."""
        cell = CellService.get_cell(db, cell_id, tenant_id)
        if not cell:
            raise ValueError(f"Cell {cell_id} not found")

        validate_org_access_for_operation(
            db, updater_id, tenant_id, cell.org_unit_id, "cells.manage"
        )

        before_json = {
            "name": cell.name,
            "status": cell.status,
            "leader_id": str(cell.leader_id) if cell.leader_id else None,
        }

        # Validate leader if being updated
        if "leader_id" in updates and updates["leader_id"]:
            leader = db.get(People, updates["leader_id"])
            if not leader or leader.tenant_id != tenant_id:
                raise ValueError(f"Leader {updates['leader_id']} not found")

        # Validate assistant leader if being updated
        if "assistant_leader_id" in updates and updates["assistant_leader_id"]:
            assistant = db.get(People, updates["assistant_leader_id"])
            if not assistant or assistant.tenant_id != tenant_id:
                raise ValueError(
                    f"Assistant leader {updates['assistant_leader_id']} not found"
                )

        # Update fields
        for key, value in updates.items():
            if hasattr(cell, key) and value is not None:
                setattr(cell, key, value)

        cell.updated_by = updater_id
        cell.updated_at = datetime.now(timezone.utc)

        after_json = {
            "name": cell.name,
            "status": cell.status,
            "leader_id": str(cell.leader_id) if cell.leader_id else None,
        }

        # Audit log
        create_audit_log(
            db, updater_id, "update", "cells", cell_id, before_json, after_json
        )

        db.commit()
        db.refresh(cell)
        return cell

    @staticmethod
    def delete_cell(
        db: Session,
        deleter_id: UUID,
        tenant_id: UUID,
        cell_id: UUID,
    ) -> None:
        """Delete a cell."""
        cell = CellService.get_cell(db, cell_id, tenant_id)
        if not cell:
            raise ValueError(f"Cell {cell_id} not found")

        validate_org_access_for_operation(
            db, deleter_id, tenant_id, cell.org_unit_id, "cells.manage"
        )

        # Check if cell has reports
        reports_count = db.execute(
            select(func.count()).where(CellReport.cell_id == cell_id)
        ).scalar() or 0
        if reports_count > 0:
            raise ValueError(
                f"Cannot delete cell {cell_id}: it has {reports_count} reports. "
                "Delete reports first or deactivate the cell instead."
            )

        before_json = {
            "id": str(cell_id),
            "name": cell.name,
            "org_unit_id": str(cell.org_unit_id),
        }

        db.delete(cell)

        # Audit log
        create_audit_log(
            db, deleter_id, "delete", "cells", cell_id, before_json, None
        )

        db.commit()


class CellReportService:
    """Service for managing cell reports."""

    @staticmethod
    def _get_default_offering_fund(db: Session, tenant_id: UUID) -> Optional[UUID]:
        """Get the default 'Offering' fund ID for cell offerings."""
        fund = db.execute(
            select(Fund).where(
                Fund.tenant_id == tenant_id,
                Fund.name.ilike("offering"),
                Fund.active == True,
            )
        ).scalar_one_or_none()
        return fund.id if fund else None

    @staticmethod
    def _create_finance_entry_from_report(
        db: Session,
        creator_id: UUID,
        tenant_id: UUID,
        cell_report: CellReport,
        cell: Cell,
    ) -> Optional[FinanceEntry]:
        """Create a finance entry from cell report offerings."""
        if cell_report.offerings_total <= 0:
            return None

        # Get default offering fund
        fund_id = CellReportService._get_default_offering_fund(db, tenant_id)
        if not fund_id:
            # If no offering fund exists, skip finance entry creation
            # This could be logged as a warning
            return None

        try:
            # Check if user has permission to create finance entries
            # If not, we'll skip finance entry creation (it can be created manually later)
            try:
                require_permission(db, creator_id, tenant_id, "finance.entries.create")
            except ValueError:
                # User doesn't have permission - skip finance entry creation
                # This is acceptable - finance entry can be created manually later
                return None

            # Validate fund exists
            fund = db.get(Fund, fund_id)
            if not fund or fund.tenant_id != tenant_id:
                return None

            # Create finance entry directly to avoid double org access check
            # We already validated org access for the cell report
            entry = FinanceEntry(
                id=uuid4(),
                tenant_id=tenant_id,
                org_unit_id=cell.org_unit_id,
                fund_id=fund_id,
                amount=cell_report.offerings_total,
                transaction_date=cell_report.report_date,
                cell_id=cell.id,
                source_type="cell_report",
                source_id=cell_report.id,
                method="cash",
                currency="EUR",
                verified_status="draft",
                comment=f"Cell report: {cell.name}",
                created_by=creator_id,
            )
            db.add(entry)
            db.flush()

            # Create audit log
            create_audit_log(
                db,
                creator_id,
                "create",
                "finance_entries",
                entry.id,
                None,
                {
                    "id": str(entry.id),
                    "org_unit_id": str(cell.org_unit_id),
                    "fund_id": str(fund_id),
                    "amount": str(cell_report.offerings_total),
                    "source_type": "cell_report",
                    "source_id": str(cell_report.id),
                },
            )

            return entry
        except Exception as e:
            # Log error but don't fail report creation
            # In production, this should be logged properly
            # For now, we'll just skip finance entry creation
            return None

    @staticmethod
    def _update_finance_entry_from_report(
        db: Session,
        updater_id: UUID,
        tenant_id: UUID,
        cell_report: CellReport,
        old_offerings: Decimal,
    ) -> None:
        """Update or create finance entry when report offerings change."""
        # Find existing finance entry linked to this report
        existing_entry = db.execute(
            select(FinanceEntry).where(
                FinanceEntry.tenant_id == tenant_id,
                FinanceEntry.source_type == "cell_report",
                FinanceEntry.source_id == cell_report.id,
            )
        ).scalar_one_or_none()

        if cell_report.offerings_total > 0:
            if existing_entry:
                # Update existing entry
                if existing_entry.amount != cell_report.offerings_total:
                    existing_entry.amount = cell_report.offerings_total
                    existing_entry.updated_by = updater_id
                    existing_entry.updated_at = datetime.now(timezone.utc)
            else:
                # Create new entry
                cell = CellService.get_cell(db, cell_report.cell_id, tenant_id)
                if cell:
                    # Check permission before creating
                    try:
                        require_permission(db, updater_id, tenant_id, "finance.entries.create")
                        CellReportService._create_finance_entry_from_report(
                            db, updater_id, tenant_id, cell_report, cell
                        )
                    except ValueError:
                        # User doesn't have permission - skip finance entry creation
                        pass
        else:
            # If offerings is 0, delete the finance entry if it exists
            if existing_entry:
                db.delete(existing_entry)

    @staticmethod
    def _delete_finance_entry_for_report(
        db: Session,
        tenant_id: UUID,
        report_id: UUID,
    ) -> None:
        """Delete finance entry linked to a cell report."""
        entry = db.execute(
            select(FinanceEntry).where(
                FinanceEntry.tenant_id == tenant_id,
                FinanceEntry.source_type == "cell_report",
                FinanceEntry.source_id == report_id,
            )
        ).scalar_one_or_none()

        if entry:
            db.delete(entry)

    @staticmethod
    def create_report(
        db: Session,
        creator_id: UUID,
        tenant_id: UUID,
        cell_id: UUID,
        report_date: date,
        attendance: int = 0,
        first_timers: int = 0,
        new_converts: int = 0,
        testimonies: Optional[str] = None,
        offerings_total: Decimal = Decimal("0.00"),
        meeting_type: str = "bible_study",
        report_time: Optional[time] = None,
        notes: Optional[str] = None,
    ) -> CellReport:
        """Create a new cell report."""
        # Validate cell exists
        cell = CellService.get_cell(db, cell_id, tenant_id)
        if not cell:
            raise ValueError(f"Cell {cell_id} not found")

        # Validate org access
        validate_org_access_for_operation(
            db, creator_id, tenant_id, cell.org_unit_id, "cells.reports.create"
        )

        # Check unique constraint (one report per cell per date)
        existing = db.execute(
            select(CellReport).where(
                CellReport.tenant_id == tenant_id,
                CellReport.cell_id == cell_id,
                CellReport.report_date == report_date,
            )
        ).scalar_one_or_none()
        if existing:
            raise ValueError(
                f"Report already exists for cell {cell_id} on date {report_date}"
            )

        # Validate cell leader can only create for their assigned cell
        # Get user's person_id - for now we'll check org access
        # TODO: Implement proper user-to-person linking to validate leader_id

        cell_report = CellReport(
            id=uuid4(),
            tenant_id=tenant_id,
            cell_id=cell_id,
            report_date=report_date,
            report_time=report_time,
            attendance=attendance,
            first_timers=first_timers,
            new_converts=new_converts,
            testimonies=testimonies,
            offerings_total=offerings_total,
            meeting_type=meeting_type,
            status="submitted",
            notes=notes,
            created_by=creator_id,
        )
        db.add(cell_report)
        db.flush()

        # Create finance entry if offerings > 0
        if offerings_total > 0:
            CellReportService._create_finance_entry_from_report(
                db, creator_id, tenant_id, cell_report, cell
            )

        # Audit log
        create_audit_log(
            db,
            creator_id,
            "create",
            "cell_reports",
            cell_report.id,
            None,
            {
                "id": str(cell_report.id),
                "cell_id": str(cell_id),
                "report_date": report_date.isoformat(),
                "offerings_total": str(offerings_total),
            },
        )

        db.commit()
        db.refresh(cell_report)
        return cell_report

    @staticmethod
    def get_report(
        db: Session, report_id: UUID, tenant_id: UUID
    ) -> Optional[CellReport]:
        """Get a cell report by ID."""
        return db.execute(
            select(CellReport).where(
                CellReport.id == report_id, CellReport.tenant_id == tenant_id
            )
        ).scalar_one_or_none()

    @staticmethod
    def list_reports(
        db: Session,
        tenant_id: UUID,
        cell_id: Optional[UUID] = None,
        org_unit_id: Optional[UUID] = None,
        status: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CellReport]:
        """List cell reports with optional filters."""
        stmt = select(CellReport).where(CellReport.tenant_id == tenant_id)

        if cell_id:
            stmt = stmt.where(CellReport.cell_id == cell_id)
        elif org_unit_id:
            # Filter by org_unit through cell
            stmt = stmt.join(Cell).where(Cell.org_unit_id == org_unit_id)

        if status:
            stmt = stmt.where(CellReport.status == status)

        if start_date:
            stmt = stmt.where(CellReport.report_date >= start_date)

        if end_date:
            stmt = stmt.where(CellReport.report_date <= end_date)

        stmt = stmt.order_by(CellReport.report_date.desc()).limit(limit).offset(offset)

        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def update_report(
        db: Session,
        updater_id: UUID,
        tenant_id: UUID,
        report_id: UUID,
        **updates,
    ) -> CellReport:
        """Update a cell report (only if status is submitted)."""
        report = CellReportService.get_report(db, report_id, tenant_id)
        if not report:
            raise ValueError(f"Cell report {report_id} not found")

        if report.status != "submitted":
            raise ValueError(
                f"Cannot update report with status {report.status}. "
                "Only submitted reports can be updated."
            )

        # Get cell to validate org access
        cell = CellService.get_cell(db, report.cell_id, tenant_id)
        if not cell:
            raise ValueError(f"Cell {report.cell_id} not found")

        validate_org_access_for_operation(
            db, updater_id, tenant_id, cell.org_unit_id, "cells.reports.update"
        )

        before_json = {
            "attendance": report.attendance,
            "offerings_total": str(report.offerings_total),
            "status": report.status,
        }

        old_offerings = report.offerings_total

        # Update fields
        for key, value in updates.items():
            if hasattr(report, key) and value is not None:
                setattr(report, key, value)

        report.updated_by = updater_id
        report.updated_at = datetime.now(timezone.utc)

        # Update finance entry if offerings changed
        if "offerings_total" in updates:
            CellReportService._update_finance_entry_from_report(
                db, updater_id, tenant_id, report, old_offerings
            )

        after_json = {
            "attendance": report.attendance,
            "offerings_total": str(report.offerings_total),
            "status": report.status,
        }

        # Audit log
        create_audit_log(
            db,
            updater_id,
            "update",
            "cell_reports",
            report_id,
            before_json,
            after_json,
        )

        db.commit()
        db.refresh(report)
        return report

    @staticmethod
    def approve_report(
        db: Session,
        approver_id: UUID,
        tenant_id: UUID,
        report_id: UUID,
        status: str,
    ) -> CellReport:
        """Approve or review a cell report (change status)."""
        if status not in ["reviewed", "approved"]:
            raise ValueError(f"Invalid status {status}. Must be 'reviewed' or 'approved'")

        report = CellReportService.get_report(db, report_id, tenant_id)
        if not report:
            raise ValueError(f"Cell report {report_id} not found")

        require_permission(db, approver_id, tenant_id, "cells.reports.approve")

        # Get cell to validate org access
        cell = CellService.get_cell(db, report.cell_id, tenant_id)
        if not cell:
            raise ValueError(f"Cell {report.cell_id} not found")

        validate_org_access_for_operation(
            db, approver_id, tenant_id, cell.org_unit_id, "cells.reports.approve"
        )

        before_json = {"status": report.status}

        report.status = status
        report.updated_by = approver_id
        report.updated_at = datetime.now(timezone.utc)

        # If approving and offerings > 0, ensure finance entry exists
        if status == "approved" and report.offerings_total > 0:
            existing_entry = db.execute(
                select(FinanceEntry).where(
                    FinanceEntry.tenant_id == tenant_id,
                    FinanceEntry.source_type == "cell_report",
                    FinanceEntry.source_id == report.id,
                )
            ).scalar_one_or_none()

            if not existing_entry:
                # Create finance entry if it doesn't exist
                CellReportService._create_finance_entry_from_report(
                    db, approver_id, tenant_id, report, cell
                )

        after_json = {"status": status}

        # Audit log
        create_audit_log(
            db,
            approver_id,
            "approve",
            "cell_reports",
            report_id,
            before_json,
            after_json,
        )

        db.commit()
        db.refresh(report)
        return report

    @staticmethod
    def delete_report(
        db: Session,
        deleter_id: UUID,
        tenant_id: UUID,
        report_id: UUID,
    ) -> None:
        """Delete a cell report (only if status is submitted)."""
        report = CellReportService.get_report(db, report_id, tenant_id)
        if not report:
            raise ValueError(f"Cell report {report_id} not found")

        if report.status != "submitted":
            raise ValueError(
                f"Cannot delete report with status {report.status}. "
                "Only submitted reports can be deleted."
            )

        # Get cell to validate org access
        cell = CellService.get_cell(db, report.cell_id, tenant_id)
        if not cell:
            raise ValueError(f"Cell {report.cell_id} not found")

        validate_org_access_for_operation(
            db, deleter_id, tenant_id, cell.org_unit_id, "cells.reports.delete"
        )

        before_json = {
            "id": str(report_id),
            "cell_id": str(report.cell_id),
            "report_date": report.report_date.isoformat(),
        }

        # Delete linked finance entry if exists
        CellReportService._delete_finance_entry_for_report(db, tenant_id, report_id)

        db.delete(report)

        # Audit log
        create_audit_log(
            db, deleter_id, "delete", "cell_reports", report_id, before_json, None
        )

        db.commit()

