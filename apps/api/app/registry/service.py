"""Registry service layer for people, first-timers, services, attendance, and departments."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from app.common.audit import create_audit_log
from app.common.models import (
    People,
    Membership,
    FirstTimer,
    Service,
    Attendance,
    Department,
    DepartmentRole,
    OrgUnit,
)
from app.core.config import settings
from app.registry.scope_validation import validate_org_access_for_operation


class PeopleService:
    """Service for managing people (members) records."""

    @staticmethod
    def create_person(
        db: Session,
        creator_id: UUID,
        tenant_id: UUID,
        org_unit_id: UUID,
        first_name: str,
        last_name: str,
        gender: str,
        title: Optional[str] = None,
        alias: Optional[str] = None,
        dob: Optional[date] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        address_line1: Optional[str] = None,
        address_line2: Optional[str] = None,
        town: Optional[str] = None,
        county: Optional[str] = None,
        eircode: Optional[str] = None,
        marital_status: Optional[str] = None,
        consent_contact: bool = True,
        consent_data_storage: bool = True,
        membership_status: Optional[str] = None,
        join_date: Optional[date] = None,
        foundation_completed: bool = False,
        baptism_date: Optional[date] = None,
    ) -> People:
        """Create a new person record."""
        validate_org_access_for_operation(
            db, creator_id, tenant_id, org_unit_id, "registry.people.create"
        )

        # Generate member code
        member_code = PeopleService._generate_member_code(db, tenant_id)

        # Create person
        person = People(
            id=uuid4(),
            tenant_id=tenant_id,
            org_unit_id=org_unit_id,
            member_code=member_code,
            title=title,
            first_name=first_name,
            last_name=last_name,
            alias=alias,
            dob=dob,
            gender=gender,
            email=email.lower() if email else None,
            phone=phone,
            address_line1=address_line1,
            address_line2=address_line2,
            town=town,
            county=county,
            eircode=eircode,
            marital_status=marital_status,
            consent_contact=consent_contact,
            consent_data_storage=consent_data_storage,
            created_by=creator_id,
        )
        db.add(person)
        db.flush()

        # Create membership if status provided
        if membership_status:
            membership = Membership(
                person_id=person.id,
                status=membership_status,
                join_date=join_date,
                foundation_completed=foundation_completed,
                baptism_date=baptism_date,
            )
            db.add(membership)

        # Audit log
        create_audit_log(
            db,
            creator_id,
            "create",
            "people",
            person.id,
            None,
            {
                "id": str(person.id),
                "org_unit_id": str(org_unit_id),
                "member_code": member_code,
                "first_name": first_name,
                "last_name": last_name,
            },
        )

        db.commit()
        db.refresh(person)
        return person

    @staticmethod
    def _generate_member_code(db: Session, tenant_id: UUID) -> str:
        """Generate unique member code per tenant."""
        # Find highest existing member code
        stmt = select(func.max(People.member_code)).where(People.tenant_id == tenant_id)
        max_code = db.execute(stmt).scalar()
        if max_code:
            # Extract number and increment
            try:
                num = int(max_code.split("-")[-1]) if "-" in max_code else 0
                num += 1
            except ValueError:
                num = 1
        else:
            num = 1
        return f"MEM-{num:04d}"

    @staticmethod
    def get_person(db: Session, person_id: UUID, tenant_id: UUID) -> Optional[People]:
        """Get a person by ID."""
        return db.execute(
            select(People).where(People.id == person_id, People.tenant_id == tenant_id)
        ).scalar_one_or_none()

    @staticmethod
    def update_person(
        db: Session,
        updater_id: UUID,
        tenant_id: UUID,
        person_id: UUID,
        **updates,
    ) -> People:
        """Update a person record."""
        person = PeopleService.get_person(db, person_id, tenant_id)
        if not person:
            raise ValueError(f"Person {person_id} not found")

        validate_org_access_for_operation(
            db, updater_id, tenant_id, person.org_unit_id, "registry.people.update"
        )

        before_json = {
            "first_name": person.first_name,
            "last_name": person.last_name,
            "email": person.email,
            "phone": person.phone,
        }

        # Update fields
        for key, value in updates.items():
            if hasattr(person, key) and value is not None:
                if key == "email" and value:
                    setattr(person, key, value.lower())
                else:
                    setattr(person, key, value)

        person.updated_by = updater_id
        person.updated_at = datetime.now(timezone.utc)

        after_json = {
            "first_name": person.first_name,
            "last_name": person.last_name,
            "email": person.email,
            "phone": person.phone,
        }

        # Audit log
        create_audit_log(
            db,
            updater_id,
            "update",
            "people",
            person_id,
            before_json,
            after_json,
        )

        db.commit()
        db.refresh(person)
        return person

    @staticmethod
    def list_people(
        db: Session,
        tenant_id: UUID,
        org_unit_id: Optional[UUID] = None,
        search: Optional[str] = None,
        membership_status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[People]:
        """List people with optional filters."""
        stmt = select(People).where(People.tenant_id == tenant_id)

        if org_unit_id:
            stmt = stmt.where(People.org_unit_id == org_unit_id)

        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    People.first_name.ilike(search_pattern),
                    People.last_name.ilike(search_pattern),
                    People.email.ilike(search_pattern),
                    People.phone.ilike(search_pattern),
                    People.member_code.ilike(search_pattern),
                )
            )

        if membership_status:
            stmt = stmt.join(Membership).where(Membership.status == membership_status)

        stmt = stmt.order_by(People.last_name, People.first_name).limit(limit).offset(offset)

        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def merge_people(
        db: Session,
        merger_id: UUID,
        tenant_id: UUID,
        source_person_id: UUID,
        target_person_id: UUID,
        reason: str,
    ) -> People:
        """Merge two people records. Source is deleted, target is kept."""
        source = PeopleService.get_person(db, source_person_id, tenant_id)
        target = PeopleService.get_person(db, target_person_id, tenant_id)

        if not source:
            raise ValueError(f"Source person {source_person_id} not found")
        if not target:
            raise ValueError(f"Target person {target_person_id} not found")

        validate_org_access_for_operation(
            db, merger_id, tenant_id, source.org_unit_id, "registry.people.merge"
        )
        validate_org_access_for_operation(
            db, merger_id, tenant_id, target.org_unit_id, "registry.people.merge"
        )

        before_json = {
            "source": {
                "id": str(source.id),
                "name": f"{source.first_name} {source.last_name}",
            },
            "target": {
                "id": str(target.id),
                "name": f"{target.first_name} {target.last_name}",
            },
        }

        # Transfer related records from source to target
        # Update first_timers
        first_timers = db.execute(
            select(FirstTimer).where(FirstTimer.person_id == source_person_id)
        ).scalars().all()
        for ft in first_timers:
            ft.person_id = target_person_id

        # Update department roles
        dept_roles = db.execute(
            select(DepartmentRole).where(DepartmentRole.person_id == source_person_id)
        ).scalars().all()
        for dr in dept_roles:
            dr.person_id = target_person_id

        # Transfer membership if source has one and target doesn't
        source_membership = db.execute(
            select(Membership).where(Membership.person_id == source_person_id)
        ).scalar_one_or_none()
        target_membership = db.execute(
            select(Membership).where(Membership.person_id == target_person_id)
        ).scalar_one_or_none()

        if source_membership and not target_membership:
            # Transfer membership
            source_membership.person_id = target_person_id
        elif source_membership and target_membership:
            # Merge membership data (keep target, update missing fields from source)
            if source_membership.join_date and not target_membership.join_date:
                target_membership.join_date = source_membership.join_date
            if source_membership.foundation_completed:
                target_membership.foundation_completed = True
            if source_membership.baptism_date and not target_membership.baptism_date:
                target_membership.baptism_date = source_membership.baptism_date
            # Delete source membership since we're keeping target
            db.delete(source_membership)

        # Delete source person (cascade will handle related records, but membership was handled above)
        db.delete(source)

        after_json = {
            "target": {
                "id": str(target.id),
                "name": f"{target.first_name} {target.last_name}",
            },
            "reason": reason,
        }

        # Audit log
        create_audit_log(
            db,
            merger_id,
            "merge",
            "people",
            target_person_id,
            before_json,
            after_json,
        )

        db.commit()
        db.refresh(target)
        return target


class FirstTimerService:
    """Service for managing first-timer records."""

    @staticmethod
    def create_first_timer(
        db: Session,
        creator_id: UUID,
        tenant_id: UUID,
        service_id: UUID,
        person_id: Optional[UUID] = None,
        source: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> FirstTimer:
        """Create a new first-timer record."""
        # Verify service exists and get org_unit_id
        service = db.get(Service, service_id)
        if not service or service.tenant_id != tenant_id:
            raise ValueError(f"Service {service_id} not found")

        validate_org_access_for_operation(
            db, creator_id, tenant_id, service.org_unit_id, "registry.firsttimers.create"
        )

        first_timer = FirstTimer(
            id=uuid4(),
            tenant_id=tenant_id,
            person_id=person_id,
            service_id=service_id,
            source=source,
            status="New",
            notes=notes,
            created_by=creator_id,
        )
        db.add(first_timer)

        # Audit log
        create_audit_log(
            db,
            creator_id,
            "create",
            "first_timers",
            first_timer.id,
            None,
            {"id": str(first_timer.id), "service_id": str(service_id), "status": "New"},
        )

        db.commit()
        db.refresh(first_timer)
        return first_timer

    @staticmethod
    def update_first_timer_status(
        db: Session,
        updater_id: UUID,
        tenant_id: UUID,
        first_timer_id: UUID,
        status: str,
    ) -> FirstTimer:
        """Update first-timer status."""
        first_timer = db.execute(
            select(FirstTimer).where(
                FirstTimer.id == first_timer_id, FirstTimer.tenant_id == tenant_id
            )
        ).scalar_one_or_none()

        if not first_timer:
            raise ValueError(f"First-timer {first_timer_id} not found")

        # Verify service and org access
        service = db.get(Service, first_timer.service_id)
        validate_org_access_for_operation(
            db, updater_id, tenant_id, service.org_unit_id, "registry.firsttimers.update"
        )

        before_json = {"status": first_timer.status}
        first_timer.status = status
        first_timer.updated_by = updater_id
        first_timer.updated_at = datetime.now(timezone.utc)
        after_json = {"status": status}

        # Audit log
        create_audit_log(
            db,
            updater_id,
            "update",
            "first_timers",
            first_timer_id,
            before_json,
            after_json,
        )

        db.commit()
        db.refresh(first_timer)
        return first_timer

    @staticmethod
    def get_first_timer(
        db: Session, first_timer_id: UUID, tenant_id: UUID
    ) -> Optional[FirstTimer]:
        """Get a first-timer by ID."""
        return db.execute(
            select(FirstTimer).where(
                FirstTimer.id == first_timer_id, FirstTimer.tenant_id == tenant_id
            )
        ).scalar_one_or_none()

    @staticmethod
    def list_first_timers(
        db: Session,
        tenant_id: UUID,
        org_unit_id: Optional[UUID] = None,
        service_id: Optional[UUID] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[FirstTimer]:
        """List first-timers with optional filters."""
        stmt = select(FirstTimer).where(FirstTimer.tenant_id == tenant_id)

        if service_id:
            stmt = stmt.where(FirstTimer.service_id == service_id)
        elif org_unit_id:
            # Filter by org_unit through service
            stmt = stmt.join(Service).where(Service.org_unit_id == org_unit_id)

        if status:
            stmt = stmt.where(FirstTimer.status == status)

        stmt = stmt.order_by(FirstTimer.created_at.desc()).limit(limit).offset(offset)

        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def convert_to_member(
        db: Session,
        converter_id: UUID,
        tenant_id: UUID,
        first_timer_id: UUID,
        org_unit_id: UUID,
        first_name: str,
        last_name: str,
        gender: str,
        title: Optional[str] = None,
        dob: Optional[date] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        address_line1: Optional[str] = None,
        address_line2: Optional[str] = None,
        town: Optional[str] = None,
        county: Optional[str] = None,
        eircode: Optional[str] = None,
        marital_status: Optional[str] = None,
        consent_contact: bool = True,
        consent_data_storage: bool = True,
    ) -> People:
        """Convert a first-timer to a member (person record)."""
        first_timer = FirstTimerService.get_first_timer(db, first_timer_id, tenant_id)
        if not first_timer:
            raise ValueError(f"First-timer {first_timer_id} not found")

        # Verify service and org access
        service = db.get(Service, first_timer.service_id)
        validate_org_access_for_operation(
            db, converter_id, tenant_id, service.org_unit_id, "registry.firsttimers.update"
        )
        validate_org_access_for_operation(
            db, converter_id, tenant_id, org_unit_id, "registry.people.create"
        )

        # Create person
        person = PeopleService.create_person(
            db=db,
            creator_id=converter_id,
            tenant_id=tenant_id,
            org_unit_id=org_unit_id,
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            title=title,
            dob=dob,
            email=email,
            phone=phone,
            address_line1=address_line1,
            address_line2=address_line2,
            town=town,
            county=county,
            eircode=eircode,
            marital_status=marital_status,
            consent_contact=consent_contact,
            consent_data_storage=consent_data_storage,
            membership_status="member",
            join_date=service.service_date,
        )

        # Link first-timer to person and update status
        first_timer.person_id = person.id
        first_timer.status = "Member"
        first_timer.updated_by = converter_id
        first_timer.updated_at = datetime.now(timezone.utc)

        # Audit log for conversion
        create_audit_log(
            db,
            converter_id,
            "convert_to_member",
            "first_timers",
            first_timer_id,
            {"status": "New", "person_id": None},
            {"status": "Member", "person_id": str(person.id)},
        )

        db.commit()
        db.refresh(person)
        return person


class ServiceService:
    """Service for managing service records."""

    @staticmethod
    def create_service(
        db: Session,
        creator_id: UUID,
        tenant_id: UUID,
        org_unit_id: UUID,
        name: str,
        service_date: date,
        service_time: Optional[time] = None,
    ) -> Service:
        """Create a new service record."""
        validate_org_access_for_operation(
            db, creator_id, tenant_id, org_unit_id, "registry.attendance.create"
        )

        service = Service(
            id=uuid4(),
            tenant_id=tenant_id,
            org_unit_id=org_unit_id,
            name=name,
            service_date=service_date,
            service_time=service_time,
        )
        db.add(service)

        db.commit()
        db.refresh(service)
        return service

    @staticmethod
    def list_services(
        db: Session,
        tenant_id: UUID,
        org_unit_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[Service]:
        """List services with optional filters."""
        stmt = select(Service).where(Service.tenant_id == tenant_id)

        if org_unit_id:
            stmt = stmt.where(Service.org_unit_id == org_unit_id)

        if start_date:
            stmt = stmt.where(Service.service_date >= start_date)

        if end_date:
            stmt = stmt.where(Service.service_date <= end_date)

        stmt = stmt.order_by(Service.service_date.desc(), Service.service_time)

        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def get_service(db: Session, service_id: UUID, tenant_id: UUID) -> Optional[Service]:
        """Get a service by ID."""
        return db.execute(
            select(Service).where(Service.id == service_id, Service.tenant_id == tenant_id)
        ).scalar_one_or_none()


class AttendanceService:
    """Service for managing attendance records."""

    @staticmethod
    def create_attendance(
        db: Session,
        creator_id: UUID,
        tenant_id: UUID,
        service_id: UUID,
        men_count: int = 0,
        women_count: int = 0,
        teens_count: int = 0,
        kids_count: int = 0,
        first_timers_count: int = 0,
        new_converts_count: int = 0,
        total_attendance: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> Attendance:
        """Create a new attendance record."""
        # Verify service exists
        service = db.get(Service, service_id)
        if not service or service.tenant_id != tenant_id:
            raise ValueError(f"Service {service_id} not found")

        validate_org_access_for_operation(
            db, creator_id, tenant_id, service.org_unit_id, "registry.attendance.create"
        )

        # Check if attendance already exists for this service
        existing = db.execute(
            select(Attendance).where(
                Attendance.service_id == service_id, Attendance.tenant_id == tenant_id
            )
        ).scalar_one_or_none()

        if existing:
            raise ValueError(f"Attendance already exists for service {service_id}")

        # Calculate total if not provided
        if total_attendance is None:
            total_attendance = (
                men_count + women_count + teens_count + kids_count
                + first_timers_count
                + new_converts_count
            )

        attendance = Attendance(
            id=uuid4(),
            tenant_id=tenant_id,
            service_id=service_id,
            men_count=men_count,
            women_count=women_count,
            teens_count=teens_count,
            kids_count=kids_count,
            first_timers_count=first_timers_count,
            new_converts_count=new_converts_count,
            total_attendance=total_attendance,
            notes=notes,
            created_by=creator_id,
        )
        db.add(attendance)

        # Audit log
        create_audit_log(
            db,
            creator_id,
            "create",
            "attendance",
            attendance.id,
            None,
            {
                "id": str(attendance.id),
                "service_id": str(service_id),
                "total_attendance": total_attendance,
            },
        )

        db.commit()
        db.refresh(attendance)
        return attendance

    @staticmethod
    def update_attendance(
        db: Session,
        updater_id: UUID,
        tenant_id: UUID,
        attendance_id: UUID,
        **updates,
    ) -> Attendance:
        """Update an attendance record."""
        attendance = db.execute(
            select(Attendance).where(
                Attendance.id == attendance_id, Attendance.tenant_id == tenant_id
            )
        ).scalar_one_or_none()

        if not attendance:
            raise ValueError(f"Attendance {attendance_id} not found")

        service = db.get(Service, attendance.service_id)
        validate_org_access_for_operation(
            db, updater_id, tenant_id, service.org_unit_id, "registry.attendance.update"
        )

        before_json = {
            "men_count": attendance.men_count,
            "women_count": attendance.women_count,
            "total_attendance": attendance.total_attendance,
        }

        # Update fields
        for key, value in updates.items():
            if hasattr(attendance, key) and value is not None:
                setattr(attendance, key, value)

        # Recalculate total if counts changed
        if any(
            k in updates
            for k in ["men_count", "women_count", "teens_count", "kids_count", "first_timers_count", "new_converts_count"]
        ):
            attendance.total_attendance = (
                attendance.men_count
                + attendance.women_count
                + attendance.teens_count
                + attendance.kids_count
                + attendance.first_timers_count
                + attendance.new_converts_count
            )

        attendance.updated_by = updater_id
        attendance.updated_at = datetime.now(timezone.utc)

        after_json = {
            "men_count": attendance.men_count,
            "women_count": attendance.women_count,
            "total_attendance": attendance.total_attendance,
        }

        # Audit log
        create_audit_log(
            db,
            updater_id,
            "update",
            "attendance",
            attendance_id,
            before_json,
            after_json,
        )

        db.commit()
        db.refresh(attendance)
        return attendance

    @staticmethod
    def get_attendance(
        db: Session, attendance_id: UUID, tenant_id: UUID
    ) -> Optional[Attendance]:
        """Get an attendance record by ID."""
        return db.execute(
            select(Attendance).where(
                Attendance.id == attendance_id, Attendance.tenant_id == tenant_id
            )
        ).scalar_one_or_none()

    @staticmethod
    def list_attendance(
        db: Session,
        tenant_id: UUID,
        org_unit_id: Optional[UUID] = None,
        service_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Attendance]:
        """List attendance records with optional filters."""
        stmt = select(Attendance).where(Attendance.tenant_id == tenant_id)

        if service_id:
            stmt = stmt.where(Attendance.service_id == service_id)
        elif org_unit_id:
            # Filter by org_unit through service
            stmt = stmt.join(Service).where(Service.org_unit_id == org_unit_id)
            if start_date:
                stmt = stmt.where(Service.service_date >= start_date)
            if end_date:
                stmt = stmt.where(Service.service_date <= end_date)
        elif start_date or end_date:
            # Need to join service to filter by date
            stmt = stmt.join(Service)
            if start_date:
                stmt = stmt.where(Service.service_date >= start_date)
            if end_date:
                stmt = stmt.where(Service.service_date <= end_date)

        # Order by service date if we joined Service, otherwise by created_at
        # Note: If we joined Service, we need to select both or order by Attendance fields
        if org_unit_id or start_date or end_date:
            # We joined Service, so order by service date through the join
            # Since we already joined, we can reference Service.service_date
            stmt = stmt.order_by(Service.service_date.desc())
        elif service_id:
            # We filtered by service_id, so we can get the service date via join
            stmt = stmt.join(Service).order_by(Service.service_date.desc())
        else:
            stmt = stmt.order_by(Attendance.created_at.desc())

        stmt = stmt.limit(limit).offset(offset)

        return list(db.execute(stmt).scalars().all())


class DepartmentService:
    """Service for managing departments."""

    @staticmethod
    def create_department(
        db: Session,
        creator_id: UUID,
        tenant_id: UUID,
        org_unit_id: UUID,
        name: str,
        status: str = "active",
    ) -> Department:
        """Create a new department."""
        validate_org_access_for_operation(
            db, creator_id, tenant_id, org_unit_id, "registry.departments.create"
        )

        department = Department(
            id=uuid4(),
            tenant_id=tenant_id,
            org_unit_id=org_unit_id,
            name=name,
            status=status,
            created_by=creator_id,
        )
        db.add(department)

        # Audit log
        create_audit_log(
            db,
            creator_id,
            "create",
            "departments",
            department.id,
            None,
            {"id": str(department.id), "name": name, "org_unit_id": str(org_unit_id)},
        )

        db.commit()
        db.refresh(department)
        return department

    @staticmethod
    def assign_person_to_department(
        db: Session,
        updater_id: UUID,
        tenant_id: UUID,
        dept_id: UUID,
        person_id: UUID,
        role: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> DepartmentRole:
        """Assign a person to a department with a role."""
        # Verify department exists
        department = db.execute(
            select(Department).where(
                Department.id == dept_id, Department.tenant_id == tenant_id
            )
        ).scalar_one_or_none()

        if not department:
            raise ValueError(f"Department {dept_id} not found")

        validate_org_access_for_operation(
            db, updater_id, tenant_id, department.org_unit_id, "registry.departments.update"
        )

        # Check if assignment already exists
        existing = db.execute(
            select(DepartmentRole).where(
                DepartmentRole.dept_id == dept_id, DepartmentRole.person_id == person_id
            )
        ).scalar_one_or_none()

        if existing:
            # Update existing
            existing.role = role
            if start_date:
                existing.start_date = start_date
            if end_date:
                existing.end_date = end_date
            dept_role = existing
        else:
            # Create new
            dept_role = DepartmentRole(
                id=uuid4(),
                dept_id=dept_id,
                person_id=person_id,
                role=role,
                start_date=start_date,
                end_date=end_date,
            )
            db.add(dept_role)

        db.commit()
        db.refresh(dept_role)
        return dept_role

    @staticmethod
    def get_department(
        db: Session, dept_id: UUID, tenant_id: UUID
    ) -> Optional[Department]:
        """Get a department by ID."""
        return db.execute(
            select(Department).where(
                Department.id == dept_id, Department.tenant_id == tenant_id
            )
        ).scalar_one_or_none()

    @staticmethod
    def list_departments(
        db: Session,
        tenant_id: UUID,
        org_unit_id: Optional[UUID] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Department]:
        """List departments with optional filters."""
        stmt = select(Department).where(Department.tenant_id == tenant_id)

        if org_unit_id:
            stmt = stmt.where(Department.org_unit_id == org_unit_id)

        if status:
            stmt = stmt.where(Department.status == status)

        stmt = stmt.order_by(Department.name).limit(limit).offset(offset)

        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def update_department(
        db: Session,
        updater_id: UUID,
        tenant_id: UUID,
        dept_id: UUID,
        **updates,
    ) -> Department:
        """Update a department."""
        department = DepartmentService.get_department(db, dept_id, tenant_id)
        if not department:
            raise ValueError(f"Department {dept_id} not found")

        validate_org_access_for_operation(
            db,
            updater_id,
            tenant_id,
            department.org_unit_id,
            "registry.departments.update",
        )

        before_json = {"name": department.name, "status": department.status}

        # Update fields
        for key, value in updates.items():
            if hasattr(department, key) and value is not None:
                setattr(department, key, value)

        department.updated_by = updater_id
        department.updated_at = datetime.now(timezone.utc)

        after_json = {"name": department.name, "status": department.status}

        # Audit log
        create_audit_log(
            db,
            updater_id,
            "update",
            "departments",
            dept_id,
            before_json,
            after_json,
        )

        db.commit()
        db.refresh(department)
        return department

    @staticmethod
    def delete_department(
        db: Session,
        deleter_id: UUID,
        tenant_id: UUID,
        dept_id: UUID,
    ) -> None:
        """Delete a department."""
        department = DepartmentService.get_department(db, dept_id, tenant_id)
        if not department:
            raise ValueError(f"Department {dept_id} not found")

        validate_org_access_for_operation(
            db,
            deleter_id,
            tenant_id,
            department.org_unit_id,
            "registry.departments.delete",
        )

        before_json = {
            "id": str(dept_id),
            "name": department.name,
            "org_unit_id": str(department.org_unit_id),
        }

        # Delete department (cascade will handle department_roles)
        db.delete(department)

        # Audit log
        create_audit_log(
            db,
            deleter_id,
            "delete",
            "departments",
            dept_id,
            before_json,
            None,
        )

        db.commit()

    @staticmethod
    def list_department_members(
        db: Session,
        tenant_id: UUID,
        dept_id: UUID,
        role: Optional[str] = None,
    ) -> list[DepartmentRole]:
        """List all members of a department."""
        department = DepartmentService.get_department(db, dept_id, tenant_id)
        if not department:
            raise ValueError(f"Department {dept_id} not found")

        stmt = select(DepartmentRole).where(DepartmentRole.dept_id == dept_id)

        if role:
            stmt = stmt.where(DepartmentRole.role == role)

        stmt = stmt.order_by(DepartmentRole.role, DepartmentRole.start_date)

        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def remove_person_from_department(
        db: Session,
        updater_id: UUID,
        tenant_id: UUID,
        dept_id: UUID,
        person_id: UUID,
    ) -> None:
        """Remove a person from a department."""
        department = DepartmentService.get_department(db, dept_id, tenant_id)
        if not department:
            raise ValueError(f"Department {dept_id} not found")

        validate_org_access_for_operation(
            db,
            updater_id,
            tenant_id,
            department.org_unit_id,
            "registry.departments.update",
        )

        dept_role = db.execute(
            select(DepartmentRole).where(
                DepartmentRole.dept_id == dept_id,
                DepartmentRole.person_id == person_id,
            )
        ).scalar_one_or_none()

        if not dept_role:
            raise ValueError(
                f"Person {person_id} is not assigned to department {dept_id}"
            )

        before_json = {
            "dept_id": str(dept_id),
            "person_id": str(person_id),
            "role": dept_role.role,
        }

        # Delete the role assignment
        db.delete(dept_role)

        # Audit log
        create_audit_log(
            db,
            updater_id,
            "remove_from_department",
            "department_roles",
            dept_role.id,
            before_json,
            None,
        )

        db.commit()

