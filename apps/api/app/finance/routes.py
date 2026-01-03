"""Finance API routes."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user_id, get_db_with_rls
from app.core.business_metrics import BusinessMetric
from app.core.config import settings
from app.core.metrics_service import MetricsService
from app.finance import schemas
from app.finance.service import (
    FundService,
    PartnershipArmService,
    BatchService,
    FinanceEntryService,
    PartnershipService,
)

router = APIRouter(prefix="/finance", tags=["finance"])


# Fund Routes
@router.post("/funds", response_model=schemas.FundResponse, status_code=status.HTTP_201_CREATED)
async def create_fund(
    request: schemas.FundCreateRequest,
    creator_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Create a new fund."""
    tenant_id = UUID(settings.tenant_id)

    try:
        fund = FundService.create_fund(
            db=db,
            creator_id=creator_id,
            tenant_id=tenant_id,
            name=request.name,
            is_partnership=request.is_partnership,
            active=request.active,
        )

        # Emit business metric
        MetricsService.emit_finance_metric(
            metric_name=BusinessMetric.FINANCE_FUND_CREATED,
            tenant_id=tenant_id,
            actor_id=creator_id,
        )

        return schemas.FundResponse(
            id=fund.id,
            name=fund.name,
            is_partnership=fund.is_partnership,
            active=fund.active,
            created_at=fund.created_at.isoformat(),
            updated_at=fund.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/funds", response_model=list[schemas.FundResponse])
async def list_funds(
    active_only: bool = Query(False),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """List funds with optional filters."""
    tenant_id = UUID(settings.tenant_id)

    funds = FundService.list_funds(
        db=db,
        tenant_id=tenant_id,
        active_only=active_only,
    )

    return [
        schemas.FundResponse(
            id=f.id,
            name=f.name,
            is_partnership=f.is_partnership,
            active=f.active,
            created_at=f.created_at.isoformat(),
            updated_at=f.updated_at.isoformat(),
        )
        for f in funds
    ]


@router.get("/funds/{fund_id}", response_model=schemas.FundResponse)
async def get_fund(
    fund_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get a fund by ID."""
    tenant_id = UUID(settings.tenant_id)

    fund = FundService.get_fund(db, fund_id, tenant_id)
    if not fund:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fund {fund_id} not found",
        )

    return schemas.FundResponse(
        id=fund.id,
        name=fund.name,
        is_partnership=fund.is_partnership,
        active=fund.active,
        created_at=fund.created_at.isoformat(),
        updated_at=fund.updated_at.isoformat(),
    )


@router.patch("/funds/{fund_id}", response_model=schemas.FundResponse)
async def update_fund(
    fund_id: UUID,
    request: schemas.FundUpdateRequest,
    updater_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Update a fund."""
    tenant_id = UUID(settings.tenant_id)

    try:
        updates = request.model_dump(exclude_unset=True)
        fund = FundService.update_fund(
            db=db,
            updater_id=updater_id,
            tenant_id=tenant_id,
            fund_id=fund_id,
            **updates,
        )

        return schemas.FundResponse(
            id=fund.id,
            name=fund.name,
            is_partnership=fund.is_partnership,
            active=fund.active,
            created_at=fund.created_at.isoformat(),
            updated_at=fund.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.delete("/funds/{fund_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fund(
    fund_id: UUID,
    deleter_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Delete a fund."""
    tenant_id = UUID(settings.tenant_id)

    try:
        FundService.delete_fund(
            db=db,
            deleter_id=deleter_id,
            tenant_id=tenant_id,
            fund_id=fund_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


# Partnership Arm Routes
@router.post(
    "/partnership-arms",
    response_model=schemas.PartnershipArmResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_partnership_arm(
    request: schemas.PartnershipArmCreateRequest,
    creator_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Create a new partnership arm."""
    tenant_id = UUID(settings.tenant_id)

    try:
        partnership_arm = PartnershipArmService.create_partnership_arm(
            db=db,
            creator_id=creator_id,
            tenant_id=tenant_id,
            name=request.name,
            active_from=request.active_from,
            active_to=request.active_to,
            active=request.active,
        )

        # Emit business metric
        MetricsService.emit_finance_metric(
            metric_name=BusinessMetric.FINANCE_PARTNERSHIP_CREATED,
            tenant_id=tenant_id,
            actor_id=creator_id,
        )

        return schemas.PartnershipArmResponse(
            id=partnership_arm.id,
            name=partnership_arm.name,
            active_from=partnership_arm.active_from,
            active_to=partnership_arm.active_to,
            active=partnership_arm.active,
            created_at=partnership_arm.created_at.isoformat(),
            updated_at=partnership_arm.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/partnership-arms", response_model=list[schemas.PartnershipArmResponse])
async def list_partnership_arms(
    active_only: bool = Query(False),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """List partnership arms with optional filters."""
    tenant_id = UUID(settings.tenant_id)

    partnership_arms = PartnershipArmService.list_partnership_arms(
        db=db,
        tenant_id=tenant_id,
        active_only=active_only,
    )

    return [
        schemas.PartnershipArmResponse(
            id=pa.id,
            name=pa.name,
            active_from=pa.active_from,
            active_to=pa.active_to,
            active=pa.active,
            created_at=pa.created_at.isoformat(),
            updated_at=pa.updated_at.isoformat(),
        )
        for pa in partnership_arms
    ]


@router.get("/partnership-arms/{partnership_arm_id}", response_model=schemas.PartnershipArmResponse)
async def get_partnership_arm(
    partnership_arm_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get a partnership arm by ID."""
    tenant_id = UUID(settings.tenant_id)

    partnership_arm = PartnershipArmService.get_partnership_arm(
        db, partnership_arm_id, tenant_id
    )
    if not partnership_arm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Partnership arm {partnership_arm_id} not found",
        )

    return schemas.PartnershipArmResponse(
        id=partnership_arm.id,
        name=partnership_arm.name,
        active_from=partnership_arm.active_from,
        active_to=partnership_arm.active_to,
        active=partnership_arm.active,
        created_at=partnership_arm.created_at.isoformat(),
        updated_at=partnership_arm.updated_at.isoformat(),
    )


@router.patch("/partnership-arms/{partnership_arm_id}", response_model=schemas.PartnershipArmResponse)
async def update_partnership_arm(
    partnership_arm_id: UUID,
    request: schemas.PartnershipArmUpdateRequest,
    updater_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Update a partnership arm."""
    tenant_id = UUID(settings.tenant_id)

    try:
        updates = request.model_dump(exclude_unset=True)
        partnership_arm = PartnershipArmService.update_partnership_arm(
            db=db,
            updater_id=updater_id,
            tenant_id=tenant_id,
            partnership_arm_id=partnership_arm_id,
            **updates,
        )

        return schemas.PartnershipArmResponse(
            id=partnership_arm.id,
            name=partnership_arm.name,
            active_from=partnership_arm.active_from,
            active_to=partnership_arm.active_to,
            active=partnership_arm.active,
            created_at=partnership_arm.created_at.isoformat(),
            updated_at=partnership_arm.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.delete("/partnership-arms/{partnership_arm_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_partnership_arm(
    partnership_arm_id: UUID,
    deleter_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Delete a partnership arm."""
    tenant_id = UUID(settings.tenant_id)

    try:
        PartnershipArmService.delete_partnership_arm(
            db=db,
            deleter_id=deleter_id,
            tenant_id=tenant_id,
            partnership_arm_id=partnership_arm_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


# Batch Routes
@router.post("/batches", response_model=schemas.BatchResponse, status_code=status.HTTP_201_CREATED)
async def create_batch(
    request: schemas.BatchCreateRequest,
    creator_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Create a new batch."""
    tenant_id = UUID(settings.tenant_id)

    try:
        batch = BatchService.create_batch(
            db=db,
            creator_id=creator_id,
            tenant_id=tenant_id,
            org_unit_id=request.org_unit_id,
            service_id=request.service_id,
        )

        # Emit business metric
        MetricsService.emit_finance_metric(
            metric_name=BusinessMetric.FINANCE_BATCH_CREATED,
            tenant_id=tenant_id,
            actor_id=creator_id,
            org_unit_id=request.org_unit_id,
        )

        return schemas.BatchResponse(
            id=batch.id,
            org_unit_id=batch.org_unit_id,
            service_id=batch.service_id,
            status=batch.status,
            locked_by=batch.locked_by,
            locked_at=batch.locked_at.isoformat() if batch.locked_at else None,
            verified_by_1=batch.verified_by_1,
            verified_by_2=batch.verified_by_2,
            created_at=batch.created_at.isoformat(),
            updated_at=batch.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/batches", response_model=list[schemas.BatchResponse])
async def list_batches(
    org_unit_id: Optional[UUID] = Query(None),
    service_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """List batches with optional filters."""
    tenant_id = UUID(settings.tenant_id)

    batches = BatchService.list_batches(
        db=db,
        tenant_id=tenant_id,
        org_unit_id=org_unit_id,
        service_id=service_id,
        status=status,
    )

    return [
        schemas.BatchResponse(
            id=b.id,
            org_unit_id=b.org_unit_id,
            service_id=b.service_id,
            status=b.status,
            locked_by=b.locked_by,
            locked_at=b.locked_at.isoformat() if b.locked_at else None,
            verified_by_1=b.verified_by_1,
            verified_by_2=b.verified_by_2,
            created_at=b.created_at.isoformat(),
            updated_at=b.updated_at.isoformat(),
        )
        for b in batches
    ]


@router.get("/batches/{batch_id}", response_model=schemas.BatchResponse)
async def get_batch(
    batch_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get a batch by ID."""
    tenant_id = UUID(settings.tenant_id)

    batch = BatchService.get_batch(db, batch_id, tenant_id)
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch {batch_id} not found",
        )

    return schemas.BatchResponse(
        id=batch.id,
        org_unit_id=batch.org_unit_id,
        service_id=batch.service_id,
        status=batch.status,
        locked_by=batch.locked_by,
        locked_at=batch.locked_at.isoformat() if batch.locked_at else None,
        verified_by_1=batch.verified_by_1,
        verified_by_2=batch.verified_by_2,
        created_at=batch.created_at.isoformat(),
        updated_at=batch.updated_at.isoformat(),
    )


@router.patch("/batches/{batch_id}", response_model=schemas.BatchResponse)
async def update_batch(
    batch_id: UUID,
    request: schemas.BatchUpdateRequest,
    updater_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Update a batch."""
    tenant_id = UUID(settings.tenant_id)

    try:
        updates = request.model_dump(exclude_unset=True)
        batch = BatchService.update_batch(
            db=db,
            updater_id=updater_id,
            tenant_id=tenant_id,
            batch_id=batch_id,
            **updates,
        )

        return schemas.BatchResponse(
            id=batch.id,
            org_unit_id=batch.org_unit_id,
            service_id=batch.service_id,
            status=batch.status,
            locked_by=batch.locked_by,
            locked_at=batch.locked_at.isoformat() if batch.locked_at else None,
            verified_by_1=batch.verified_by_1,
            verified_by_2=batch.verified_by_2,
            created_at=batch.created_at.isoformat(),
            updated_at=batch.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.delete("/batches/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_batch(
    batch_id: UUID,
    deleter_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Delete a batch."""
    tenant_id = UUID(settings.tenant_id)

    try:
        BatchService.delete_batch(
            db=db,
            deleter_id=deleter_id,
            tenant_id=tenant_id,
            batch_id=batch_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/batches/{batch_id}/verify", response_model=schemas.BatchResponse)
async def verify_batch(
    batch_id: UUID,
    verifier_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Verify a batch (first or second verification)."""
    tenant_id = UUID(settings.tenant_id)

    try:
        batch = BatchService.verify_batch(
            db=db,
            verifier_id=verifier_id,
            tenant_id=tenant_id,
            batch_id=batch_id,
        )

        # Determine verification number (1 or 2)
        verification_number = 1 if not batch.verified_by_1 else 2

        # Emit business metric
        MetricsService.emit_finance_metric(
            metric_name=BusinessMetric.FINANCE_BATCH_VERIFIED,
            tenant_id=tenant_id,
            actor_id=verifier_id,
            org_unit_id=batch.org_unit_id,
            verification_number=verification_number,
        )

        return schemas.BatchResponse(
            id=batch.id,
            org_unit_id=batch.org_unit_id,
            service_id=batch.service_id,
            status=batch.status,
            locked_by=batch.locked_by,
            locked_at=batch.locked_at.isoformat() if batch.locked_at else None,
            verified_by_1=batch.verified_by_1,
            verified_by_2=batch.verified_by_2,
            created_at=batch.created_at.isoformat(),
            updated_at=batch.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/batches/{batch_id}/lock", response_model=schemas.BatchResponse)
async def lock_batch(
    batch_id: UUID,
    request: schemas.BatchLockRequest,
    locker_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Lock a batch (requires dual verification)."""
    tenant_id = UUID(settings.tenant_id)

    try:
        batch = BatchService.lock_batch(
            db=db,
            locker_id=locker_id,
            tenant_id=tenant_id,
            batch_id=batch_id,
        )

        # Emit business metric
        MetricsService.emit_finance_metric(
            metric_name=BusinessMetric.FINANCE_BATCH_LOCKED,
            tenant_id=tenant_id,
            actor_id=locker_id,
            org_unit_id=batch.org_unit_id,
        )

        return schemas.BatchResponse(
            id=batch.id,
            org_unit_id=batch.org_unit_id,
            service_id=batch.service_id,
            status=batch.status,
            locked_by=batch.locked_by,
            locked_at=batch.locked_at.isoformat() if batch.locked_at else None,
            verified_by_1=batch.verified_by_1,
            verified_by_2=batch.verified_by_2,
            created_at=batch.created_at.isoformat(),
            updated_at=batch.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/batches/{batch_id}/unlock", response_model=schemas.BatchResponse)
async def unlock_batch(
    batch_id: UUID,
    request: schemas.BatchUnlockRequest,
    unlocker_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Unlock a batch (requires dual authorization)."""
    tenant_id = UUID(settings.tenant_id)

    try:
        batch = BatchService.unlock_batch(
            db=db,
            unlocker_id=unlocker_id,
            tenant_id=tenant_id,
            batch_id=batch_id,
            reason=request.reason,
        )

        # Emit business metric
        MetricsService.emit_finance_metric(
            metric_name=BusinessMetric.FINANCE_BATCH_UNLOCKED,
            tenant_id=tenant_id,
            actor_id=unlocker_id,
            org_unit_id=batch.org_unit_id,
        )

        return schemas.BatchResponse(
            id=batch.id,
            org_unit_id=batch.org_unit_id,
            service_id=batch.service_id,
            status=batch.status,
            locked_by=batch.locked_by,
            locked_at=batch.locked_at.isoformat() if batch.locked_at else None,
            verified_by_1=batch.verified_by_1,
            verified_by_2=batch.verified_by_2,
            created_at=batch.created_at.isoformat(),
            updated_at=batch.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


# Finance Entry Routes
@router.post(
    "/entries",
    response_model=schemas.FinanceEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_entry(
    request: schemas.FinanceEntryCreateRequest,
    creator_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Create a new finance entry."""
    tenant_id = UUID(settings.tenant_id)

    try:
        entry = FinanceEntryService.create_entry(
            db=db,
            creator_id=creator_id,
            tenant_id=tenant_id,
            org_unit_id=request.org_unit_id,
            fund_id=request.fund_id,
            amount=request.amount,
            transaction_date=request.transaction_date,
            batch_id=request.batch_id,
            service_id=request.service_id,
            partnership_arm_id=request.partnership_arm_id,
            currency=request.currency,
            method=request.method,
            person_id=request.person_id,
            cell_id=request.cell_id,
            external_giver_name=request.external_giver_name,
            reference=request.reference,
            comment=request.comment,
        )

        # Emit business metric
        MetricsService.emit_finance_metric(
            metric_name=BusinessMetric.FINANCE_ENTRY_CREATED,
            tenant_id=tenant_id,
            actor_id=creator_id,
            org_unit_id=request.org_unit_id,
        )

        return schemas.FinanceEntryResponse(
            id=entry.id,
            org_unit_id=entry.org_unit_id,
            batch_id=entry.batch_id,
            service_id=entry.service_id,
            fund_id=entry.fund_id,
            partnership_arm_id=entry.partnership_arm_id,
            amount=entry.amount,
            currency=entry.currency,
            method=entry.method,
            person_id=entry.person_id,
            cell_id=entry.cell_id,
            external_giver_name=entry.external_giver_name,
            reference=entry.reference,
            comment=entry.comment,
            verified_status=entry.verified_status,
            source_type=entry.source_type,
            source_id=entry.source_id,
            transaction_date=entry.transaction_date,
            created_at=entry.created_at.isoformat(),
            updated_at=entry.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/entries", response_model=list[schemas.FinanceEntryResponse])
async def list_entries(
    org_unit_id: Optional[UUID] = Query(None),
    batch_id: Optional[UUID] = Query(None),
    service_id: Optional[UUID] = Query(None),
    fund_id: Optional[UUID] = Query(None),
    partnership_arm_id: Optional[UUID] = Query(None),
    person_id: Optional[UUID] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    verified_status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """List finance entries with optional filters."""
    tenant_id = UUID(settings.tenant_id)

    entries = FinanceEntryService.list_entries(
        db=db,
        tenant_id=tenant_id,
        org_unit_id=org_unit_id,
        batch_id=batch_id,
        service_id=service_id,
        fund_id=fund_id,
        partnership_arm_id=partnership_arm_id,
        person_id=person_id,
        start_date=start_date,
        end_date=end_date,
        verified_status=verified_status,
        limit=limit,
        offset=offset,
    )

    return [
        schemas.FinanceEntryResponse(
            id=e.id,
            org_unit_id=e.org_unit_id,
            batch_id=e.batch_id,
            service_id=e.service_id,
            fund_id=e.fund_id,
            partnership_arm_id=e.partnership_arm_id,
            amount=e.amount,
            currency=e.currency,
            method=e.method,
            person_id=e.person_id,
            cell_id=e.cell_id,
            external_giver_name=e.external_giver_name,
            reference=e.reference,
            comment=e.comment,
            verified_status=e.verified_status,
            source_type=e.source_type,
            source_id=e.source_id,
            transaction_date=e.transaction_date,
            created_at=e.created_at.isoformat(),
            updated_at=e.updated_at.isoformat(),
        )
        for e in entries
    ]


@router.get("/entries/{entry_id}", response_model=schemas.FinanceEntryResponse)
async def get_entry(
    entry_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get a finance entry by ID."""
    tenant_id = UUID(settings.tenant_id)

    entry = FinanceEntryService.get_entry(db, entry_id, tenant_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finance entry {entry_id} not found",
        )

    return schemas.FinanceEntryResponse(
        id=entry.id,
        org_unit_id=entry.org_unit_id,
        batch_id=entry.batch_id,
        service_id=entry.service_id,
        fund_id=entry.fund_id,
        partnership_arm_id=entry.partnership_arm_id,
        amount=entry.amount,
        currency=entry.currency,
        method=entry.method,
        person_id=entry.person_id,
        cell_id=entry.cell_id,
        external_giver_name=entry.external_giver_name,
        reference=entry.reference,
        comment=entry.comment,
        verified_status=entry.verified_status,
        source_type=entry.source_type,
        source_id=entry.source_id,
        transaction_date=entry.transaction_date,
        created_at=entry.created_at.isoformat(),
        updated_at=entry.updated_at.isoformat(),
    )


@router.patch("/entries/{entry_id}", response_model=schemas.FinanceEntryResponse)
async def update_entry(
    entry_id: UUID,
    request: schemas.FinanceEntryUpdateRequest,
    updater_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Update a finance entry."""
    tenant_id = UUID(settings.tenant_id)

    try:
        updates = request.model_dump(exclude_unset=True)
        entry = FinanceEntryService.update_entry(
            db=db,
            updater_id=updater_id,
            tenant_id=tenant_id,
            entry_id=entry_id,
            **updates,
        )

        # Emit business metric
        MetricsService.emit_finance_metric(
            metric_name=BusinessMetric.FINANCE_ENTRY_UPDATED,
            tenant_id=tenant_id,
            actor_id=updater_id,
            org_unit_id=entry.org_unit_id,
        )

        return schemas.FinanceEntryResponse(
            id=entry.id,
            org_unit_id=entry.org_unit_id,
            batch_id=entry.batch_id,
            service_id=entry.service_id,
            fund_id=entry.fund_id,
            partnership_arm_id=entry.partnership_arm_id,
            amount=entry.amount,
            currency=entry.currency,
            method=entry.method,
            person_id=entry.person_id,
            cell_id=entry.cell_id,
            external_giver_name=entry.external_giver_name,
            reference=entry.reference,
            comment=entry.comment,
            verified_status=entry.verified_status,
            source_type=entry.source_type,
            source_id=entry.source_id,
            transaction_date=entry.transaction_date,
            created_at=entry.created_at.isoformat(),
            updated_at=entry.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    entry_id: UUID,
    deleter_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Delete a finance entry."""
    tenant_id = UUID(settings.tenant_id)

    try:
        # Get entry before deletion to get org_unit_id
        from app.common.models import FinanceEntry
        entry = db.get(FinanceEntry, entry_id)
        org_unit_id = entry.org_unit_id if entry else None

        FinanceEntryService.delete_entry(
            db=db,
            deleter_id=deleter_id,
            tenant_id=tenant_id,
            entry_id=entry_id,
        )

        # Emit business metric
        if org_unit_id:
            MetricsService.emit_finance_metric(
                metric_name=BusinessMetric.FINANCE_ENTRY_DELETED,
                tenant_id=tenant_id,
                actor_id=deleter_id,
                org_unit_id=org_unit_id,
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/entries/{entry_id}/verify", response_model=schemas.FinanceEntryResponse)
async def verify_entry(
    entry_id: UUID,
    request: schemas.FinanceEntryVerifyRequest,
    verifier_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Verify a finance entry."""
    tenant_id = UUID(settings.tenant_id)

    try:
        entry = FinanceEntryService.verify_entry(
            db=db,
            verifier_id=verifier_id,
            tenant_id=tenant_id,
            entry_id=entry_id,
            verified_status=request.verified_status,
        )

        # Emit business metric
        MetricsService.emit_finance_metric(
            metric_name=BusinessMetric.FINANCE_ENTRY_VERIFIED,
            tenant_id=tenant_id,
            actor_id=verifier_id,
            org_unit_id=entry.org_unit_id,
            entry_id=str(entry_id),
        )

        return schemas.FinanceEntryResponse(
            id=entry.id,
            org_unit_id=entry.org_unit_id,
            batch_id=entry.batch_id,
            service_id=entry.service_id,
            fund_id=entry.fund_id,
            partnership_arm_id=entry.partnership_arm_id,
            amount=entry.amount,
            currency=entry.currency,
            method=entry.method,
            person_id=entry.person_id,
            cell_id=entry.cell_id,
            external_giver_name=entry.external_giver_name,
            reference=entry.reference,
            comment=entry.comment,
            verified_status=entry.verified_status,
            source_type=entry.source_type,
            source_id=entry.source_id,
            transaction_date=entry.transaction_date,
            created_at=entry.created_at.isoformat(),
            updated_at=entry.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/entries/{entry_id}/reconcile", response_model=schemas.FinanceEntryResponse)
async def reconcile_entry(
    entry_id: UUID,
    reconciler_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Reconcile a finance entry."""
    tenant_id = UUID(settings.tenant_id)

    try:
        entry = FinanceEntryService.reconcile_entry(
            db=db,
            reconciler_id=reconciler_id,
            tenant_id=tenant_id,
            entry_id=entry_id,
        )

        # Emit business metric
        MetricsService.emit_finance_metric(
            metric_name=BusinessMetric.FINANCE_ENTRY_RECONCILED,
            tenant_id=tenant_id,
            actor_id=reconciler_id,
            org_unit_id=entry.org_unit_id,
            entry_id=str(entry_id),
        )

        return schemas.FinanceEntryResponse(
            id=entry.id,
            org_unit_id=entry.org_unit_id,
            batch_id=entry.batch_id,
            service_id=entry.service_id,
            fund_id=entry.fund_id,
            partnership_arm_id=entry.partnership_arm_id,
            amount=entry.amount,
            currency=entry.currency,
            method=entry.method,
            person_id=entry.person_id,
            cell_id=entry.cell_id,
            external_giver_name=entry.external_giver_name,
            reference=entry.reference,
            comment=entry.comment,
            verified_status=entry.verified_status,
            source_type=entry.source_type,
            source_id=entry.source_id,
            transaction_date=entry.transaction_date,
            created_at=entry.created_at.isoformat(),
            updated_at=entry.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


# Partnership Routes
@router.post(
    "/partnerships",
    response_model=schemas.PartnershipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_partnership(
    request: schemas.PartnershipCreateRequest,
    creator_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Create a new partnership."""
    tenant_id = UUID(settings.tenant_id)

    try:
        partnership = PartnershipService.create_partnership(
            db=db,
            creator_id=creator_id,
            tenant_id=tenant_id,
            person_id=request.person_id,
            fund_id=request.fund_id,
            partnership_arm_id=request.partnership_arm_id,
            cadence=request.cadence,
            start_date=request.start_date,
            end_date=request.end_date,
            target_amount=request.target_amount,
            status=request.status,
        )

        # Emit business metric
        MetricsService.emit_finance_metric(
            metric_name=BusinessMetric.FINANCE_PARTNERSHIP_CREATED,
            tenant_id=tenant_id,
            actor_id=creator_id,
        )

        return schemas.PartnershipResponse(
            id=partnership.id,
            person_id=partnership.person_id,
            fund_id=partnership.fund_id,
            partnership_arm_id=partnership.partnership_arm_id,
            cadence=partnership.cadence,
            start_date=partnership.start_date,
            end_date=partnership.end_date,
            target_amount=partnership.target_amount,
            status=partnership.status,
            created_at=partnership.created_at.isoformat(),
            updated_at=partnership.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/partnerships", response_model=list[schemas.PartnershipResponse])
async def list_partnerships(
    person_id: Optional[UUID] = Query(None),
    fund_id: Optional[UUID] = Query(None),
    partnership_arm_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """List partnerships with optional filters."""
    tenant_id = UUID(settings.tenant_id)

    partnerships = PartnershipService.list_partnerships(
        db=db,
        tenant_id=tenant_id,
        person_id=person_id,
        fund_id=fund_id,
        partnership_arm_id=partnership_arm_id,
        status=status,
    )

    return [
        schemas.PartnershipResponse(
            id=p.id,
            person_id=p.person_id,
            fund_id=p.fund_id,
            partnership_arm_id=p.partnership_arm_id,
            cadence=p.cadence,
            start_date=p.start_date,
            end_date=p.end_date,
            target_amount=p.target_amount,
            status=p.status,
            created_at=p.created_at.isoformat(),
            updated_at=p.updated_at.isoformat(),
        )
        for p in partnerships
    ]


@router.get("/partnerships/{partnership_id}", response_model=schemas.PartnershipResponse)
async def get_partnership(
    partnership_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get a partnership by ID."""
    tenant_id = UUID(settings.tenant_id)

    partnership = PartnershipService.get_partnership(db, partnership_id, tenant_id)
    if not partnership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Partnership {partnership_id} not found",
        )

    return schemas.PartnershipResponse(
        id=partnership.id,
        person_id=partnership.person_id,
        fund_id=partnership.fund_id,
        partnership_arm_id=partnership.partnership_arm_id,
        cadence=partnership.cadence,
        start_date=partnership.start_date,
        end_date=partnership.end_date,
        target_amount=partnership.target_amount,
        status=partnership.status,
        created_at=partnership.created_at.isoformat(),
        updated_at=partnership.updated_at.isoformat(),
    )


@router.patch("/partnerships/{partnership_id}", response_model=schemas.PartnershipResponse)
async def update_partnership(
    partnership_id: UUID,
    request: schemas.PartnershipUpdateRequest,
    updater_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Update a partnership."""
    tenant_id = UUID(settings.tenant_id)

    try:
        updates = request.model_dump(exclude_unset=True)
        partnership = PartnershipService.update_partnership(
            db=db,
            updater_id=updater_id,
            tenant_id=tenant_id,
            partnership_id=partnership_id,
            **updates,
        )

        return schemas.PartnershipResponse(
            id=partnership.id,
            person_id=partnership.person_id,
            fund_id=partnership.fund_id,
            partnership_arm_id=partnership.partnership_arm_id,
            cadence=partnership.cadence,
            start_date=partnership.start_date,
            end_date=partnership.end_date,
            target_amount=partnership.target_amount,
            status=partnership.status,
            created_at=partnership.created_at.isoformat(),
            updated_at=partnership.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.delete("/partnerships/{partnership_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_partnership(
    partnership_id: UUID,
    deleter_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Delete a partnership."""
    tenant_id = UUID(settings.tenant_id)

    try:
        PartnershipService.delete_partnership(
            db=db,
            deleter_id=deleter_id,
            tenant_id=tenant_id,
            partnership_id=partnership_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/partnerships/{partnership_id}/fulfilment", response_model=schemas.PartnershipFulfilmentResponse)
async def get_partnership_fulfilment(
    partnership_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get partnership fulfilment details."""
    tenant_id = UUID(settings.tenant_id)

    try:
        partnership = PartnershipService.get_partnership(db, partnership_id, tenant_id)
        if not partnership:
            raise ValueError(f"Partnership {partnership_id} not found")

        fulfilment = PartnershipService.calculate_fulfilment(
            db, partnership_id, tenant_id
        )

        return schemas.PartnershipFulfilmentResponse(
            partnership_id=partnership_id,
            target_amount=partnership.target_amount,
            fulfilled_amount=fulfilment["fulfilled_amount"],
            fulfilment_percentage=fulfilment["fulfilment_percentage"],
            cadence=partnership.cadence,
            start_date=partnership.start_date,
            end_date=partnership.end_date,
            entries_count=fulfilment["entries_count"],
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


# Summary Routes
@router.get("/summaries/funds")
async def get_fund_summary(
    fund_id: Optional[UUID] = Query(None),
    org_unit_id: Optional[UUID] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get summary by fund."""
    from app.common.models import FinanceEntry

    tenant_id = UUID(settings.tenant_id)

    stmt = select(
        FinanceEntry.fund_id,
        func.sum(FinanceEntry.amount).label("total_amount"),
        func.count(FinanceEntry.id).label("entry_count"),
    ).where(FinanceEntry.tenant_id == tenant_id)

    if fund_id:
        stmt = stmt.where(FinanceEntry.fund_id == fund_id)

    if org_unit_id:
        stmt = stmt.where(FinanceEntry.org_unit_id == org_unit_id)

    if start_date:
        stmt = stmt.where(FinanceEntry.transaction_date >= start_date)

    if end_date:
        stmt = stmt.where(FinanceEntry.transaction_date <= end_date)

    stmt = stmt.group_by(FinanceEntry.fund_id)

    results = db.execute(stmt).all()

    return [
        {
            "fund_id": str(r.fund_id),
            "total_amount": float(r.total_amount or 0),
            "entry_count": r.entry_count,
        }
        for r in results
    ]


@router.get("/summaries/partnership-arms")
async def get_partnership_arm_summary(
    partnership_arm_id: Optional[UUID] = Query(None),
    org_unit_id: Optional[UUID] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get summary by partnership arm."""
    from app.common.models import FinanceEntry

    tenant_id = UUID(settings.tenant_id)

    stmt = select(
        FinanceEntry.partnership_arm_id,
        func.sum(FinanceEntry.amount).label("total_amount"),
        func.count(FinanceEntry.id).label("entry_count"),
    ).where(
        FinanceEntry.tenant_id == tenant_id,
        FinanceEntry.partnership_arm_id.isnot(None),
    )

    if partnership_arm_id:
        stmt = stmt.where(FinanceEntry.partnership_arm_id == partnership_arm_id)

    if org_unit_id:
        stmt = stmt.where(FinanceEntry.org_unit_id == org_unit_id)

    if start_date:
        stmt = stmt.where(FinanceEntry.transaction_date >= start_date)

    if end_date:
        stmt = stmt.where(FinanceEntry.transaction_date <= end_date)

    stmt = stmt.group_by(FinanceEntry.partnership_arm_id)

    results = db.execute(stmt).all()

    return [
        {
            "partnership_arm_id": str(r.partnership_arm_id),
            "total_amount": float(r.total_amount or 0),
            "entry_count": r.entry_count,
        }
        for r in results
    ]


@router.get("/summaries/by-service")
async def get_service_summary(
    service_id: Optional[UUID] = Query(None),
    org_unit_id: Optional[UUID] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get summary by service."""
    from app.common.models import FinanceEntry, Service

    tenant_id = UUID(settings.tenant_id)

    stmt = (
        select(
            FinanceEntry.service_id,
            func.sum(FinanceEntry.amount).label("total_amount"),
            func.count(FinanceEntry.id).label("entry_count"),
        )
        .join(Service, Service.id == FinanceEntry.service_id)
        .where(FinanceEntry.tenant_id == tenant_id)
    )

    if service_id:
        stmt = stmt.where(FinanceEntry.service_id == service_id)

    if org_unit_id:
        stmt = stmt.where(Service.org_unit_id == org_unit_id)

    if start_date:
        stmt = stmt.where(Service.service_date >= start_date)

    if end_date:
        stmt = stmt.where(Service.service_date <= end_date)

    stmt = stmt.group_by(FinanceEntry.service_id)

    results = db.execute(stmt).all()

    return [
        {
            "service_id": str(r.service_id),
            "total_amount": float(r.total_amount or 0),
            "entry_count": r.entry_count,
        }
        for r in results
    ]


@router.get("/summaries/by-org-unit")
async def get_org_unit_summary(
    org_unit_id: Optional[UUID] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get summary by org unit."""
    from app.common.models import FinanceEntry

    tenant_id = UUID(settings.tenant_id)

    stmt = select(
        FinanceEntry.org_unit_id,
        func.sum(FinanceEntry.amount).label("total_amount"),
        func.count(FinanceEntry.id).label("entry_count"),
    ).where(FinanceEntry.tenant_id == tenant_id)

    if org_unit_id:
        stmt = stmt.where(FinanceEntry.org_unit_id == org_unit_id)

    if start_date:
        stmt = stmt.where(FinanceEntry.transaction_date >= start_date)

    if end_date:
        stmt = stmt.where(FinanceEntry.transaction_date <= end_date)

    stmt = stmt.group_by(FinanceEntry.org_unit_id)

    results = db.execute(stmt).all()

    return [
        {
            "org_unit_id": str(r.org_unit_id),
            "total_amount": float(r.total_amount or 0),
            "entry_count": r.entry_count,
        }
        for r in results
    ]

