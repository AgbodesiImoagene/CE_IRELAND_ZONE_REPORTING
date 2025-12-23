"""Cells API routes."""

from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user_id, get_db_with_rls
from app.core.config import settings
from app.cells import schemas
from app.cells.service import (
    CellService,
    CellReportService,
)

router = APIRouter(prefix="/cells", tags=["cells"])


# Cell Routes
@router.post("", response_model=schemas.CellResponse, status_code=status.HTTP_201_CREATED)
async def create_cell(
    request: schemas.CellCreateRequest,
    creator_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Create a new cell."""
    tenant_id = UUID(settings.tenant_id)

    try:
        cell = CellService.create_cell(
            db=db,
            creator_id=creator_id,
            tenant_id=tenant_id,
            org_unit_id=request.org_unit_id,
            name=request.name,
            leader_id=request.leader_id,
            assistant_leader_id=request.assistant_leader_id,
            venue=request.venue,
            meeting_day=request.meeting_day,
            meeting_time=request.meeting_time,
            status=request.status,
        )

        return schemas.CellResponse(
            id=cell.id,
            org_unit_id=cell.org_unit_id,
            name=cell.name,
            leader_id=cell.leader_id,
            assistant_leader_id=cell.assistant_leader_id,
            venue=cell.venue,
            meeting_day=cell.meeting_day,
            meeting_time=cell.meeting_time,
            status=cell.status,
            created_at=cell.created_at.isoformat(),
            updated_at=cell.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("", response_model=list[schemas.CellResponse])
async def list_cells(
    org_unit_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    leader_id: Optional[UUID] = Query(None),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """List cells with optional filters."""
    tenant_id = UUID(settings.tenant_id)

    cells = CellService.list_cells(
        db=db,
        tenant_id=tenant_id,
        org_unit_id=org_unit_id,
        status=status,
        leader_id=leader_id,
    )

    return [
        schemas.CellResponse(
            id=c.id,
            org_unit_id=c.org_unit_id,
            name=c.name,
            leader_id=c.leader_id,
            assistant_leader_id=c.assistant_leader_id,
            venue=c.venue,
            meeting_day=c.meeting_day,
            meeting_time=c.meeting_time,
            status=c.status,
            created_at=c.created_at.isoformat(),
            updated_at=c.updated_at.isoformat(),
        )
        for c in cells
    ]


@router.get("/{cell_id}", response_model=schemas.CellResponse)
async def get_cell(
    cell_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get a cell by ID."""
    tenant_id = UUID(settings.tenant_id)

    cell = CellService.get_cell(db, cell_id, tenant_id)
    if not cell:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cell {cell_id} not found",
        )

    return schemas.CellResponse(
        id=cell.id,
        org_unit_id=cell.org_unit_id,
        name=cell.name,
        leader_id=cell.leader_id,
        assistant_leader_id=cell.assistant_leader_id,
        venue=cell.venue,
        meeting_day=cell.meeting_day,
        meeting_time=cell.meeting_time,
        status=cell.status,
        created_at=cell.created_at.isoformat(),
        updated_at=cell.updated_at.isoformat(),
    )


@router.patch("/{cell_id}", response_model=schemas.CellResponse)
async def update_cell(
    cell_id: UUID,
    request: schemas.CellUpdateRequest,
    updater_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Update a cell."""
    tenant_id = UUID(settings.tenant_id)

    try:
        updates = request.model_dump(exclude_unset=True)
        cell = CellService.update_cell(
            db=db,
            updater_id=updater_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            **updates,
        )

        return schemas.CellResponse(
            id=cell.id,
            org_unit_id=cell.org_unit_id,
            name=cell.name,
            leader_id=cell.leader_id,
            assistant_leader_id=cell.assistant_leader_id,
            venue=cell.venue,
            meeting_day=cell.meeting_day,
            meeting_time=cell.meeting_time,
            status=cell.status,
            created_at=cell.created_at.isoformat(),
            updated_at=cell.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.delete("/{cell_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cell(
    cell_id: UUID,
    deleter_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Delete a cell."""
    tenant_id = UUID(settings.tenant_id)

    try:
        CellService.delete_cell(
            db=db,
            deleter_id=deleter_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


# Cell Report Routes
@router.post(
    "/cell-reports",
    response_model=schemas.CellReportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_cell_report(
    request: schemas.CellReportCreateRequest,
    creator_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Create a new cell report."""
    tenant_id = UUID(settings.tenant_id)

    try:
        report = CellReportService.create_report(
            db=db,
            creator_id=creator_id,
            tenant_id=tenant_id,
            cell_id=request.cell_id,
            report_date=request.report_date,
            report_time=request.report_time,
            attendance=request.attendance,
            first_timers=request.first_timers,
            new_converts=request.new_converts,
            testimonies=request.testimonies,
            offerings_total=request.offerings_total,
            meeting_type=request.meeting_type,
            notes=request.notes,
        )

        return schemas.CellReportResponse(
            id=report.id,
            cell_id=report.cell_id,
            report_date=report.report_date,
            report_time=report.report_time,
            attendance=report.attendance,
            first_timers=report.first_timers,
            new_converts=report.new_converts,
            testimonies=report.testimonies,
            offerings_total=report.offerings_total,
            meeting_type=report.meeting_type,
            status=report.status,
            notes=report.notes,
            created_at=report.created_at.isoformat(),
            updated_at=report.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/cell-reports", response_model=list[schemas.CellReportResponse])
async def list_cell_reports(
    cell_id: Optional[UUID] = Query(None),
    org_unit_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """List cell reports with optional filters."""
    tenant_id = UUID(settings.tenant_id)

    reports = CellReportService.list_reports(
        db=db,
        tenant_id=tenant_id,
        cell_id=cell_id,
        org_unit_id=org_unit_id,
        status=status,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )

    return [
        schemas.CellReportResponse(
            id=r.id,
            cell_id=r.cell_id,
            report_date=r.report_date,
            report_time=r.report_time,
            attendance=r.attendance,
            first_timers=r.first_timers,
            new_converts=r.new_converts,
            testimonies=r.testimonies,
            offerings_total=r.offerings_total,
            meeting_type=r.meeting_type,
            status=r.status,
            notes=r.notes,
            created_at=r.created_at.isoformat(),
            updated_at=r.updated_at.isoformat(),
        )
        for r in reports
    ]


@router.get("/cell-reports/{report_id}", response_model=schemas.CellReportResponse)
async def get_cell_report(
    report_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get a cell report by ID."""
    tenant_id = UUID(settings.tenant_id)

    report = CellReportService.get_report(db, report_id, tenant_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cell report {report_id} not found",
        )

    return schemas.CellReportResponse(
        id=report.id,
        cell_id=report.cell_id,
        report_date=report.report_date,
        report_time=report.report_time,
        attendance=report.attendance,
        first_timers=report.first_timers,
        new_converts=report.new_converts,
        testimonies=report.testimonies,
        offerings_total=report.offerings_total,
        meeting_type=report.meeting_type,
        status=report.status,
        notes=report.notes,
        created_at=report.created_at.isoformat(),
        updated_at=report.updated_at.isoformat(),
    )


@router.patch("/cell-reports/{report_id}", response_model=schemas.CellReportResponse)
async def update_cell_report(
    report_id: UUID,
    request: schemas.CellReportUpdateRequest,
    updater_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Update a cell report."""
    tenant_id = UUID(settings.tenant_id)

    try:
        updates = request.model_dump(exclude_unset=True)
        report = CellReportService.update_report(
            db=db,
            updater_id=updater_id,
            tenant_id=tenant_id,
            report_id=report_id,
            **updates,
        )

        return schemas.CellReportResponse(
            id=report.id,
            cell_id=report.cell_id,
            report_date=report.report_date,
            report_time=report.report_time,
            attendance=report.attendance,
            first_timers=report.first_timers,
            new_converts=report.new_converts,
            testimonies=report.testimonies,
            offerings_total=report.offerings_total,
            meeting_type=report.meeting_type,
            status=report.status,
            notes=report.notes,
            created_at=report.created_at.isoformat(),
            updated_at=report.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/cell-reports/{report_id}/approve", response_model=schemas.CellReportResponse)
async def approve_cell_report(
    report_id: UUID,
    request: schemas.CellReportApproveRequest,
    approver_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Approve or review a cell report."""
    tenant_id = UUID(settings.tenant_id)

    try:
        report = CellReportService.approve_report(
            db=db,
            approver_id=approver_id,
            tenant_id=tenant_id,
            report_id=report_id,
            status=request.status,
        )

        return schemas.CellReportResponse(
            id=report.id,
            cell_id=report.cell_id,
            report_date=report.report_date,
            report_time=report.report_time,
            attendance=report.attendance,
            first_timers=report.first_timers,
            new_converts=report.new_converts,
            testimonies=report.testimonies,
            offerings_total=report.offerings_total,
            meeting_type=report.meeting_type,
            status=report.status,
            notes=report.notes,
            created_at=report.created_at.isoformat(),
            updated_at=report.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.delete("/cell-reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cell_report(
    report_id: UUID,
    deleter_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Delete a cell report."""
    tenant_id = UUID(settings.tenant_id)

    try:
        CellReportService.delete_report(
            db=db,
            deleter_id=deleter_id,
            tenant_id=tenant_id,
            report_id=report_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

