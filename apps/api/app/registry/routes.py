"""Registry API routes."""

from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user_id, get_db_with_rls
from app.common.models import Membership, FirstTimer
from app.core.business_metrics import BusinessMetric
from app.core.config import settings
from app.core.metrics_service import MetricsService
from app.registry import schemas
from app.registry.service import (
    PeopleService,
    FirstTimerService,
    ServiceService,
    AttendanceService,
    DepartmentService,
)

router = APIRouter(prefix="/registry", tags=["registry"])


# People Routes
@router.post("/people", response_model=schemas.PeopleResponse, status_code=status.HTTP_201_CREATED)
async def create_person(
    request: schemas.PeopleCreateRequest,
    creator_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Create a new person (member/visitor)."""
    tenant_id = UUID(settings.tenant_id)

    try:
        person = PeopleService.create_person(
            db=db,
            creator_id=creator_id,
            tenant_id=tenant_id,
            org_unit_id=request.org_unit_id,
            first_name=request.first_name,
            last_name=request.last_name,
            gender=request.gender,
            title=request.title,
            alias=request.alias,
            dob=request.dob,
            email=request.email,
            phone=request.phone,
            address_line1=request.address_line1,
            address_line2=request.address_line2,
            town=request.town,
            county=request.county,
            eircode=request.eircode,
            marital_status=request.marital_status,
            consent_contact=request.consent_contact,
            consent_data_storage=request.consent_data_storage,
            membership_status=request.membership_status,
            join_date=request.join_date,
            foundation_completed=request.foundation_completed,
            baptism_date=request.baptism_date,
        )

        # Get membership if exists
        membership = db.execute(
            select(Membership).where(Membership.person_id == person.id)
        ).scalar_one_or_none()

        # Emit business metric
        MetricsService.emit_registry_metric(
            metric_name=BusinessMetric.PERSON_CREATED,
            tenant_id=tenant_id,
            actor_id=creator_id,
            org_unit_id=request.org_unit_id,
            entity_type="person",
        )

        return schemas.PeopleResponse(
            id=person.id,
            org_unit_id=person.org_unit_id,
            member_code=person.member_code,
            title=person.title,
            first_name=person.first_name,
            last_name=person.last_name,
            alias=person.alias,
            dob=person.dob,
            gender=person.gender,
            email=person.email,
            phone=person.phone,
            address_line1=person.address_line1,
            address_line2=person.address_line2,
            town=person.town,
            county=person.county,
            eircode=person.eircode,
            marital_status=person.marital_status,
            consent_contact=person.consent_contact,
            consent_data_storage=person.consent_data_storage,
            membership_status=membership.status if membership else None,
            join_date=membership.join_date if membership else None,
            foundation_completed=membership.foundation_completed if membership else None,
            baptism_date=membership.baptism_date if membership else None,
            cell_id=membership.cell_id if membership else None,
            created_at=person.created_at.isoformat(),
            updated_at=person.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/people/{person_id}", response_model=schemas.PeopleResponse)
async def get_person(
    person_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get a person by ID."""
    tenant_id = UUID(settings.tenant_id)

    person = PeopleService.get_person(db, person_id, tenant_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Person {person_id} not found",
        )

    membership = db.execute(
        select(Membership).where(Membership.person_id == person.id)
    ).scalar_one_or_none()

    return schemas.PeopleResponse(
        id=person.id,
        org_unit_id=person.org_unit_id,
        member_code=person.member_code,
        title=person.title,
        first_name=person.first_name,
        last_name=person.last_name,
        alias=person.alias,
        dob=person.dob,
        gender=person.gender,
        email=person.email,
        phone=person.phone,
        address_line1=person.address_line1,
        address_line2=person.address_line2,
        town=person.town,
        county=person.county,
        eircode=person.eircode,
        marital_status=person.marital_status,
        consent_contact=person.consent_contact,
        consent_data_storage=person.consent_data_storage,
        membership_status=membership.status if membership else None,
        join_date=membership.join_date if membership else None,
        foundation_completed=membership.foundation_completed if membership else None,
        baptism_date=membership.baptism_date if membership else None,
        cell_id=membership.cell_id if membership else None,
        created_at=person.created_at.isoformat(),
        updated_at=person.updated_at.isoformat(),
    )


@router.get("/people", response_model=list[schemas.PeopleResponse])
async def list_people(
    org_unit_id: Optional[UUID] = Query(None),
    search: Optional[str] = Query(None),
    membership_status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """List people with optional filters."""
    tenant_id = UUID(settings.tenant_id)

    people = PeopleService.list_people(
        db=db,
        tenant_id=tenant_id,
        org_unit_id=org_unit_id,
        search=search,
        membership_status=membership_status,
        limit=limit,
        offset=offset,
    )

    result = []
    for person in people:
        membership = db.execute(
            select(Membership).where(Membership.person_id == person.id)
        ).scalar_one_or_none()

        result.append(
            schemas.PeopleResponse(
                id=person.id,
                org_unit_id=person.org_unit_id,
                member_code=person.member_code,
                title=person.title,
                first_name=person.first_name,
                last_name=person.last_name,
                alias=person.alias,
                dob=person.dob,
                gender=person.gender,
                email=person.email,
                phone=person.phone,
                address_line1=person.address_line1,
                address_line2=person.address_line2,
                town=person.town,
                county=person.county,
                eircode=person.eircode,
                marital_status=person.marital_status,
                consent_contact=person.consent_contact,
                consent_data_storage=person.consent_data_storage,
                membership_status=membership.status if membership else None,
                join_date=membership.join_date if membership else None,
                foundation_completed=membership.foundation_completed if membership else None,
                baptism_date=membership.baptism_date if membership else None,
                cell_id=membership.cell_id if membership else None,
                created_at=person.created_at.isoformat(),
                updated_at=person.updated_at.isoformat(),
            )
        )

    return result


@router.patch("/people/{person_id}", response_model=schemas.PeopleResponse)
async def update_person(
    person_id: UUID,
    request: schemas.PeopleUpdateRequest,
    updater_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Update a person record."""
    tenant_id = UUID(settings.tenant_id)

    try:
        # Convert request to dict, excluding None values
        updates = request.model_dump(exclude_unset=True)
        person = PeopleService.update_person(
            db=db,
            updater_id=updater_id,
            tenant_id=tenant_id,
            person_id=person_id,
            **updates,
        )

        membership = db.execute(
            select(Membership).where(Membership.person_id == person.id)
        ).scalar_one_or_none()

        # Emit business metric
        MetricsService.emit_registry_metric(
            metric_name=BusinessMetric.PERSON_UPDATED,
            tenant_id=tenant_id,
            actor_id=updater_id,
            org_unit_id=person.org_unit_id,
            entity_type="person",
        )

        return schemas.PeopleResponse(
            id=person.id,
            org_unit_id=person.org_unit_id,
            member_code=person.member_code,
            title=person.title,
            first_name=person.first_name,
            last_name=person.last_name,
            alias=person.alias,
            dob=person.dob,
            gender=person.gender,
            email=person.email,
            phone=person.phone,
            address_line1=person.address_line1,
            address_line2=person.address_line2,
            town=person.town,
            county=person.county,
            eircode=person.eircode,
            marital_status=person.marital_status,
            consent_contact=person.consent_contact,
            consent_data_storage=person.consent_data_storage,
            membership_status=membership.status if membership else None,
            join_date=membership.join_date if membership else None,
            foundation_completed=membership.foundation_completed if membership else None,
            baptism_date=membership.baptism_date if membership else None,
            cell_id=membership.cell_id if membership else None,
            created_at=person.created_at.isoformat(),
            updated_at=person.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/people/merge", response_model=schemas.PeopleResponse)
async def merge_people(
    request: schemas.PeopleMergeRequest,
    merger_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Merge two people records."""
    tenant_id = UUID(settings.tenant_id)

    try:
        merged_person = PeopleService.merge_people(
            db=db,
            merger_id=merger_id,
            tenant_id=tenant_id,
            source_person_id=request.source_person_id,
            target_person_id=request.target_person_id,
            reason=request.reason,
        )

        membership = db.execute(
            select(Membership).where(Membership.person_id == merged_person.id)
        ).scalar_one_or_none()

        # Emit business metric
        MetricsService.emit_registry_metric(
            metric_name=BusinessMetric.PERSON_MERGED,
            tenant_id=tenant_id,
            actor_id=merger_id,
            org_unit_id=merged_person.org_unit_id,
            entity_type="person",
        )

        return schemas.PeopleResponse(
            id=merged_person.id,
            org_unit_id=merged_person.org_unit_id,
            member_code=merged_person.member_code,
            title=merged_person.title,
            first_name=merged_person.first_name,
            last_name=merged_person.last_name,
            alias=merged_person.alias,
            dob=merged_person.dob,
            gender=merged_person.gender,
            email=merged_person.email,
            phone=merged_person.phone,
            address_line1=merged_person.address_line1,
            address_line2=merged_person.address_line2,
            town=merged_person.town,
            county=merged_person.county,
            eircode=merged_person.eircode,
            marital_status=merged_person.marital_status,
            consent_contact=merged_person.consent_contact,
            consent_data_storage=merged_person.consent_data_storage,
            membership_status=membership.status if membership else None,
            join_date=membership.join_date if membership else None,
            foundation_completed=membership.foundation_completed if membership else None,
            baptism_date=membership.baptism_date if membership else None,
            cell_id=membership.cell_id if membership else None,
            created_at=merged_person.created_at.isoformat(),
            updated_at=merged_person.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


# First-Timers Routes
@router.post("/first-timers", response_model=schemas.FirstTimerResponse, status_code=status.HTTP_201_CREATED)
async def create_first_timer(
    request: schemas.FirstTimerCreateRequest,
    creator_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Create a new first-timer record."""
    tenant_id = UUID(settings.tenant_id)

    try:
        first_timer = FirstTimerService.create_first_timer(
            db=db,
            creator_id=creator_id,
            tenant_id=tenant_id,
            service_id=request.service_id,
            person_id=request.person_id,
            source=request.source,
            notes=request.notes,
        )

        # Get org_unit_id from service
        from app.common.models import Service
        service = db.get(Service, request.service_id)
        org_unit_id = service.org_unit_id if service else None

        # Emit business metric
        MetricsService.emit_registry_metric(
            metric_name=BusinessMetric.FIRST_TIMER_CREATED,
            tenant_id=tenant_id,
            actor_id=creator_id,
            org_unit_id=org_unit_id,
            entity_type="first_timer",
        )

        return schemas.FirstTimerResponse(
            id=first_timer.id,
            person_id=first_timer.person_id,
            service_id=first_timer.service_id,
            source=first_timer.source,
            status=first_timer.status,
            notes=first_timer.notes,
            created_at=first_timer.created_at.isoformat(),
            updated_at=first_timer.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/first-timers", response_model=list[schemas.FirstTimerResponse])
async def list_first_timers(
    org_unit_id: Optional[UUID] = Query(None),
    service_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """List first-timers with optional filters."""
    tenant_id = UUID(settings.tenant_id)

    first_timers = FirstTimerService.list_first_timers(
        db=db,
        tenant_id=tenant_id,
        org_unit_id=org_unit_id,
        service_id=service_id,
        status=status,
        limit=limit,
        offset=offset,
    )

    return [
        schemas.FirstTimerResponse(
            id=ft.id,
            person_id=ft.person_id,
            service_id=ft.service_id,
            source=ft.source,
            status=ft.status,
            notes=ft.notes,
            created_at=ft.created_at.isoformat(),
            updated_at=ft.updated_at.isoformat(),
        )
        for ft in first_timers
    ]


@router.get("/first-timers/{first_timer_id}", response_model=schemas.FirstTimerResponse)
async def get_first_timer(
    first_timer_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get a first-timer by ID."""
    tenant_id = UUID(settings.tenant_id)

    first_timer = FirstTimerService.get_first_timer(db, first_timer_id, tenant_id)
    if not first_timer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"First-timer {first_timer_id} not found",
        )

    return schemas.FirstTimerResponse(
        id=first_timer.id,
        person_id=first_timer.person_id,
        service_id=first_timer.service_id,
        source=first_timer.source,
        status=first_timer.status,
        notes=first_timer.notes,
        created_at=first_timer.created_at.isoformat(),
        updated_at=first_timer.updated_at.isoformat(),
    )


@router.patch("/first-timers/{first_timer_id}", response_model=schemas.FirstTimerResponse)
async def update_first_timer(
    first_timer_id: UUID,
    request: schemas.FirstTimerUpdateRequest,
    updater_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Update a first-timer record."""
    tenant_id = UUID(settings.tenant_id)

    try:
        updates = {}
        if request.status:
            updates["status"] = request.status
        if request.source:
            updates["source"] = request.source
        if request.notes:
            updates["notes"] = request.notes

        if request.status:
            first_timer = FirstTimerService.update_first_timer_status(
                db=db,
                updater_id=updater_id,
                tenant_id=tenant_id,
                first_timer_id=first_timer_id,
                status=request.status,
            )
        else:
            first_timer = db.execute(
                select(FirstTimer).where(
                    FirstTimer.id == first_timer_id, FirstTimer.tenant_id == tenant_id
                )
            ).scalar_one_or_none()

            if not first_timer:
                raise ValueError(f"First-timer {first_timer_id} not found")

            if request.source:
                first_timer.source = request.source
            if request.notes:
                first_timer.notes = request.notes
            first_timer.updated_by = updater_id
            from datetime import datetime, timezone

            first_timer.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(first_timer)

        return schemas.FirstTimerResponse(
            id=first_timer.id,
            person_id=first_timer.person_id,
            service_id=first_timer.service_id,
            source=first_timer.source,
            status=first_timer.status,
            notes=first_timer.notes,
            created_at=first_timer.created_at.isoformat(),
            updated_at=first_timer.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/first-timers/{first_timer_id}/convert", response_model=schemas.PeopleResponse)
async def convert_first_timer_to_member(
    first_timer_id: UUID,
    request: schemas.FirstTimerConvertRequest,
    converter_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Convert a first-timer to a member (person record)."""
    tenant_id = UUID(settings.tenant_id)

    try:
        person = FirstTimerService.convert_to_member(
            db=db,
            converter_id=converter_id,
            tenant_id=tenant_id,
            first_timer_id=first_timer_id,
            org_unit_id=request.org_unit_id,
            first_name=request.first_name,
            last_name=request.last_name,
            gender=request.gender,
            title=request.title,
            dob=request.dob,
            email=request.email,
            phone=request.phone,
            address_line1=request.address_line1,
            address_line2=request.address_line2,
            town=request.town,
            county=request.county,
            eircode=request.eircode,
            marital_status=request.marital_status,
            consent_contact=request.consent_contact,
            consent_data_storage=request.consent_data_storage,
        )

        membership = db.execute(
            select(Membership).where(Membership.person_id == person.id)
        ).scalar_one_or_none()

        # Emit business metric
        MetricsService.emit_registry_metric(
            metric_name=BusinessMetric.FIRST_TIMER_CONVERTED,
            tenant_id=tenant_id,
            actor_id=converter_id,
            org_unit_id=request.org_unit_id,
            entity_type="first_timer",
        )

        return schemas.PeopleResponse(
            id=person.id,
            org_unit_id=person.org_unit_id,
            member_code=person.member_code,
            title=person.title,
            first_name=person.first_name,
            last_name=person.last_name,
            alias=person.alias,
            dob=person.dob,
            gender=person.gender,
            email=person.email,
            phone=person.phone,
            address_line1=person.address_line1,
            address_line2=person.address_line2,
            town=person.town,
            county=person.county,
            eircode=person.eircode,
            marital_status=person.marital_status,
            consent_contact=person.consent_contact,
            consent_data_storage=person.consent_data_storage,
            membership_status=membership.status if membership else None,
            join_date=membership.join_date if membership else None,
            foundation_completed=membership.foundation_completed if membership else None,
            baptism_date=membership.baptism_date if membership else None,
            cell_id=membership.cell_id if membership else None,
            created_at=person.created_at.isoformat(),
            updated_at=person.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


# Services Routes
@router.post("/services", response_model=schemas.ServiceResponse, status_code=status.HTTP_201_CREATED)
async def create_service(
    request: schemas.ServiceCreateRequest,
    creator_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Create a new service record."""
    tenant_id = UUID(settings.tenant_id)

    try:
        service = ServiceService.create_service(
            db=db,
            creator_id=creator_id,
            tenant_id=tenant_id,
            org_unit_id=request.org_unit_id,
            name=request.name,
            service_date=request.service_date,
            service_time=request.service_time,
        )

        # Emit business metric
        MetricsService.emit_registry_metric(
            metric_name=BusinessMetric.SERVICE_CREATED,
            tenant_id=tenant_id,
            actor_id=creator_id,
            org_unit_id=request.org_unit_id,
            entity_type="service",
        )

        return schemas.ServiceResponse(
            id=service.id,
            org_unit_id=service.org_unit_id,
            name=service.name,
            service_date=service.service_date,
            service_time=service.service_time,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/services", response_model=list[schemas.ServiceResponse])
async def list_services(
    org_unit_id: Optional[UUID] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """List services with optional filters."""
    tenant_id = UUID(settings.tenant_id)

    services = ServiceService.list_services(
        db=db,
        tenant_id=tenant_id,
        org_unit_id=org_unit_id,
        start_date=start_date,
        end_date=end_date,
    )

    return [
        schemas.ServiceResponse(
            id=s.id,
            org_unit_id=s.org_unit_id,
            name=s.name,
            service_date=s.service_date,
            service_time=s.service_time,
        )
        for s in services
    ]


@router.get("/services/{service_id}", response_model=schemas.ServiceResponse)
async def get_service(
    service_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get a service by ID."""
    tenant_id = UUID(settings.tenant_id)

    service = ServiceService.get_service(db, service_id, tenant_id)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service {service_id} not found",
        )

    return schemas.ServiceResponse(
        id=service.id,
        org_unit_id=service.org_unit_id,
        name=service.name,
        service_date=service.service_date,
        service_time=service.service_time,
    )


# Attendance Routes
@router.post("/attendance", response_model=schemas.AttendanceResponse, status_code=status.HTTP_201_CREATED)
async def create_attendance(
    request: schemas.AttendanceCreateRequest,
    creator_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Create a new attendance record."""
    tenant_id = UUID(settings.tenant_id)

    try:
        attendance = AttendanceService.create_attendance(
            db=db,
            creator_id=creator_id,
            tenant_id=tenant_id,
            service_id=request.service_id,
            men_count=request.men_count,
            women_count=request.women_count,
            teens_count=request.teens_count,
            kids_count=request.kids_count,
            first_timers_count=request.first_timers_count,
            new_converts_count=request.new_converts_count,
            total_attendance=request.total_attendance,
            notes=request.notes,
        )

        # Get org_unit_id from service
        from app.common.models import Service
        service = db.get(Service, request.service_id)
        org_unit_id = service.org_unit_id if service else None

        # Emit business metric
        MetricsService.emit_registry_metric(
            metric_name=BusinessMetric.ATTENDANCE_RECORDED,
            tenant_id=tenant_id,
            actor_id=creator_id,
            org_unit_id=org_unit_id,
            entity_type="attendance",
            total_attendance=request.total_attendance,
        )

        return schemas.AttendanceResponse(
            id=attendance.id,
            service_id=attendance.service_id,
            men_count=attendance.men_count,
            women_count=attendance.women_count,
            teens_count=attendance.teens_count,
            kids_count=attendance.kids_count,
            first_timers_count=attendance.first_timers_count,
            new_converts_count=attendance.new_converts_count,
            total_attendance=attendance.total_attendance,
            notes=attendance.notes,
            created_at=attendance.created_at.isoformat(),
            updated_at=attendance.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/attendance", response_model=list[schemas.AttendanceResponse])
async def list_attendance(
    org_unit_id: Optional[UUID] = Query(None),
    service_id: Optional[UUID] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """List attendance records with optional filters."""
    tenant_id = UUID(settings.tenant_id)

    attendance_records = AttendanceService.list_attendance(
        db=db,
        tenant_id=tenant_id,
        org_unit_id=org_unit_id,
        service_id=service_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )

    return [
        schemas.AttendanceResponse(
            id=a.id,
            service_id=a.service_id,
            men_count=a.men_count,
            women_count=a.women_count,
            teens_count=a.teens_count,
            kids_count=a.kids_count,
            first_timers_count=a.first_timers_count,
            new_converts_count=a.new_converts_count,
            total_attendance=a.total_attendance,
            notes=a.notes,
            created_at=a.created_at.isoformat(),
            updated_at=a.updated_at.isoformat(),
        )
        for a in attendance_records
    ]


@router.get("/attendance/{attendance_id}", response_model=schemas.AttendanceResponse)
async def get_attendance(
    attendance_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get an attendance record by ID."""
    tenant_id = UUID(settings.tenant_id)

    attendance = AttendanceService.get_attendance(db, attendance_id, tenant_id)
    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attendance {attendance_id} not found",
        )

    return schemas.AttendanceResponse(
        id=attendance.id,
        service_id=attendance.service_id,
        men_count=attendance.men_count,
        women_count=attendance.women_count,
        teens_count=attendance.teens_count,
        kids_count=attendance.kids_count,
        first_timers_count=attendance.first_timers_count,
        new_converts_count=attendance.new_converts_count,
        total_attendance=attendance.total_attendance,
        notes=attendance.notes,
        created_at=attendance.created_at.isoformat(),
        updated_at=attendance.updated_at.isoformat(),
    )


@router.patch("/attendance/{attendance_id}", response_model=schemas.AttendanceResponse)
async def update_attendance(
    attendance_id: UUID,
    request: schemas.AttendanceUpdateRequest,
    updater_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Update an attendance record."""
    tenant_id = UUID(settings.tenant_id)

    try:
        updates = request.model_dump(exclude_unset=True)
        attendance = AttendanceService.update_attendance(
            db=db,
            updater_id=updater_id,
            tenant_id=tenant_id,
            attendance_id=attendance_id,
            **updates,
        )

        return schemas.AttendanceResponse(
            id=attendance.id,
            service_id=attendance.service_id,
            men_count=attendance.men_count,
            women_count=attendance.women_count,
            teens_count=attendance.teens_count,
            kids_count=attendance.kids_count,
            first_timers_count=attendance.first_timers_count,
            new_converts_count=attendance.new_converts_count,
            total_attendance=attendance.total_attendance,
            notes=attendance.notes,
            created_at=attendance.created_at.isoformat(),
            updated_at=attendance.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


# Departments Routes
@router.post("/departments", response_model=schemas.DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(
    request: schemas.DepartmentCreateRequest,
    creator_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Create a new department."""
    tenant_id = UUID(settings.tenant_id)

    try:
        department = DepartmentService.create_department(
            db=db,
            creator_id=creator_id,
            tenant_id=tenant_id,
            org_unit_id=request.org_unit_id,
            name=request.name,
            status=request.status,
        )

        # Emit business metric
        MetricsService.emit_registry_metric(
            metric_name=BusinessMetric.DEPARTMENT_CREATED,
            tenant_id=tenant_id,
            actor_id=creator_id,
            org_unit_id=request.org_unit_id,
            entity_type="department",
        )

        return schemas.DepartmentResponse(
            id=department.id,
            org_unit_id=department.org_unit_id,
            name=department.name,
            status=department.status,
            created_at=department.created_at.isoformat(),
            updated_at=department.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/departments", response_model=list[schemas.DepartmentResponse])
async def list_departments(
    org_unit_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """List departments with optional filters."""
    tenant_id = UUID(settings.tenant_id)

    departments = DepartmentService.list_departments(
        db=db,
        tenant_id=tenant_id,
        org_unit_id=org_unit_id,
        status=status,
        limit=limit,
        offset=offset,
    )

    return [
        schemas.DepartmentResponse(
            id=d.id,
            org_unit_id=d.org_unit_id,
            name=d.name,
            status=d.status,
            created_at=d.created_at.isoformat(),
            updated_at=d.updated_at.isoformat(),
        )
        for d in departments
    ]


@router.get("/departments/{dept_id}", response_model=schemas.DepartmentResponse)
async def get_department(
    dept_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get a department by ID."""
    tenant_id = UUID(settings.tenant_id)

    department = DepartmentService.get_department(db, dept_id, tenant_id)
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department {dept_id} not found",
        )

    return schemas.DepartmentResponse(
        id=department.id,
        org_unit_id=department.org_unit_id,
        name=department.name,
        status=department.status,
        created_at=department.created_at.isoformat(),
        updated_at=department.updated_at.isoformat(),
    )


@router.patch("/departments/{dept_id}", response_model=schemas.DepartmentResponse)
async def update_department(
    dept_id: UUID,
    request: schemas.DepartmentUpdateRequest,
    updater_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Update a department."""
    tenant_id = UUID(settings.tenant_id)

    try:
        updates = request.model_dump(exclude_unset=True)
        department = DepartmentService.update_department(
            db=db,
            updater_id=updater_id,
            tenant_id=tenant_id,
            dept_id=dept_id,
            **updates,
        )

        return schemas.DepartmentResponse(
            id=department.id,
            org_unit_id=department.org_unit_id,
            name=department.name,
            status=department.status,
            created_at=department.created_at.isoformat(),
            updated_at=department.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.delete("/departments/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    dept_id: UUID,
    deleter_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Delete a department."""
    tenant_id = UUID(settings.tenant_id)

    try:
        DepartmentService.delete_department(
            db=db,
            deleter_id=deleter_id,
            tenant_id=tenant_id,
            dept_id=dept_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/departments/{dept_id}/members", response_model=list[schemas.DepartmentRoleResponse])
async def list_department_members(
    dept_id: UUID,
    role: Optional[str] = Query(None),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """List all members of a department."""
    tenant_id = UUID(settings.tenant_id)

    try:
        dept_roles = DepartmentService.list_department_members(
            db=db,
            tenant_id=tenant_id,
            dept_id=dept_id,
            role=role,
        )

        return [
            schemas.DepartmentRoleResponse(
                id=dr.id,
                dept_id=dr.dept_id,
                person_id=dr.person_id,
                role=dr.role,
                start_date=dr.start_date,
                end_date=dr.end_date,
            )
            for dr in dept_roles
        ]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/departments/{dept_id}/members", response_model=schemas.DepartmentRoleResponse)
async def assign_person_to_department(
    dept_id: UUID,
    request: schemas.DepartmentRoleAssignRequest,
    updater_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Assign a person to a department."""
    tenant_id = UUID(settings.tenant_id)

    try:
        dept_role = DepartmentService.assign_person_to_department(
            db=db,
            updater_id=updater_id,
            tenant_id=tenant_id,
            dept_id=dept_id,
            person_id=request.person_id,
            role=request.role,
            start_date=request.start_date,
            end_date=request.end_date,
        )

        return schemas.DepartmentRoleResponse(
            id=dept_role.id,
            dept_id=dept_role.dept_id,
            person_id=dept_role.person_id,
            role=dept_role.role,
            start_date=dept_role.start_date,
            end_date=dept_role.end_date,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.delete("/departments/{dept_id}/members/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_person_from_department(
    dept_id: UUID,
    person_id: UUID,
    updater_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Remove a person from a department."""
    tenant_id = UUID(settings.tenant_id)

    try:
        DepartmentService.remove_person_from_department(
            db=db,
            updater_id=updater_id,
            tenant_id=tenant_id,
            dept_id=dept_id,
            person_id=person_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

