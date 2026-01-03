"""Tests for report background job tasks."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.common.models import FinanceEntry, Fund, OrgAssignment, Permission, RolePermission
from app.reports.models import ExportJob, ReportSchedule, ReportTemplate
from app.jobs.tasks import process_export_job, process_scheduled_report


@pytest.fixture
def reports_user(db, tenant_id, test_role, test_org_unit):
    """Create a user with reports permissions."""
    from app.common.models import User
    from app.auth.utils import hash_password

    user = User(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        email="reports@test.com",
        password_hash=hash_password("testpass123"),
        is_active=True,
    )
    db.add(user)
    db.flush()

    # Create permissions
    perms = [
        ("reports.query.execute", "Execute queries"),
        ("reports.exports.create", "Create exports"),
    ]

    for code, desc in [
        ("reports.query.execute", "Execute queries"),
        ("reports.exports.create", "Create exports"),
    ]:
        perm = Permission(id=uuid4(), code=code, description=desc)
        db.add(perm)
        db.flush()
        role_perm = RolePermission(role_id=test_role.id, permission_id=perm.id)
        db.add(role_perm)

    assignment = OrgAssignment(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        user_id=user.id,
        org_unit_id=test_org_unit.id,
        role_id=test_role.id,
        scope_type="self",
    )
    db.add(assignment)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_fund(db, tenant_id):
    """Create a test fund."""
    fund = Fund(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        name="Tithes",
        is_partnership=False,
        active=True,
    )
    db.add(fund)
    db.commit()
    db.refresh(fund)
    return fund


@pytest.fixture
def test_finance_entries(db, tenant_id, test_org_unit, test_fund, reports_user):
    """Create test finance entries."""
    entries = []
    for i in range(3):
        entry = FinanceEntry(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            org_unit_id=test_org_unit.id,
            fund_id=test_fund.id,
            amount=Decimal(f"100.{i}"),
            currency="EUR",
            method="cash",
            verified_status="verified",
            transaction_date=date(2024, 1, 1 + i),
        )
        db.add(entry)
        entries.append(entry)
    db.commit()
    return entries


class TestProcessExportJob:
    """Test export job processing."""

    def test_process_export_job_csv(
        self, db, tenant_id, reports_user, test_finance_entries, monkeypatch
    ):
        """Test processing CSV export job."""
        # Mock SessionLocal to return the test database session
        monkeypatch.setattr("app.jobs.tasks.SessionLocal", lambda: db)
        
        # Mock S3 client
        class MockS3Client:
            def upload_file(self, file_content, key, content_type=None):
                return key

            def get_presigned_url(self, key, expiration=3600):
                return f"https://s3.example.com/{key}"

        monkeypatch.setattr("app.jobs.tasks.S3Client", MockS3Client)
        monkeypatch.setattr("app.jobs.tasks.enqueue_email_notification", lambda *args, **kwargs: None)

        # Create export job
        query_definition = {
            "entity_type": "finance_entries",
            "filters": {},
            "aggregations": [],
            "group_by": [],
        }

        job = ExportJob(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
            status="pending",
            format="csv",
            query_definition=query_definition,
        )
        db.add(job)
        db.commit()

        # Process job
        process_export_job(str(job.id))

        # Verify job completed - query fresh since the task closed its session
        job_id = job.id
        from sqlalchemy import select
        job = db.execute(select(ExportJob).where(ExportJob.id == job_id)).scalar_one()
        assert job.status == "completed"
        assert job.file_path is not None
        assert job.file_size is not None

    def test_process_export_job_excel(
        self, db, tenant_id, reports_user, test_finance_entries, monkeypatch
    ):
        """Test processing Excel export job."""
        # Mock SessionLocal to return the test database session
        monkeypatch.setattr("app.jobs.tasks.SessionLocal", lambda: db)
        
        class MockS3Client:
            def upload_file(self, file_content, key, content_type=None):
                return key

            def get_presigned_url(self, key, expiration=3600):
                return f"https://s3.example.com/{key}"

        monkeypatch.setattr("app.jobs.tasks.S3Client", MockS3Client)
        monkeypatch.setattr("app.jobs.tasks.enqueue_email_notification", lambda *args, **kwargs: None)

        query_definition = {
            "entity_type": "finance_entries",
            "filters": {},
        }

        job = ExportJob(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
            status="pending",
            format="excel",
            query_definition=query_definition,
        )
        db.add(job)
        db.commit()

        process_export_job(str(job.id))

        # Query fresh since the task closed its session
        job_id = job.id
        from sqlalchemy import select
        job = db.execute(select(ExportJob).where(ExportJob.id == job_id)).scalar_one()
        assert job.status == "completed"

    def test_process_export_job_pdf(
        self, db, tenant_id, reports_user, test_finance_entries, monkeypatch
    ):
        """Test processing PDF export job."""
        # Mock SessionLocal to return the test database session
        monkeypatch.setattr("app.jobs.tasks.SessionLocal", lambda: db)
        
        class MockS3Client:
            def upload_file(self, file_content, key, content_type=None):
                return key

            def get_presigned_url(self, key, expiration=3600):
                return f"https://s3.example.com/{key}"

        monkeypatch.setattr("app.jobs.tasks.S3Client", MockS3Client)
        monkeypatch.setattr("app.jobs.tasks.enqueue_email_notification", lambda *args, **kwargs: None)

        query_definition = {
            "entity_type": "finance_entries",
            "filters": {},
        }

        job = ExportJob(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
            status="pending",
            format="pdf",
            query_definition=query_definition,
        )
        db.add(job)
        db.commit()

        process_export_job(str(job.id))

        # Query fresh since the task closed its session
        job_id = job.id
        from sqlalchemy import select
        job = db.execute(select(ExportJob).where(ExportJob.id == job_id)).scalar_one()
        assert job.status == "completed"

    def test_process_export_job_failure(
        self, db, tenant_id, reports_user, monkeypatch
    ):
        """Test handling export job failure."""
        # Mock SessionLocal to return the test database session
        monkeypatch.setattr("app.jobs.tasks.SessionLocal", lambda: db)
        
        # Create job with invalid query
        query_definition = {
            "entity_type": "invalid_entity",
            "filters": {},
        }

        job = ExportJob(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
            status="pending",
            format="csv",
            query_definition=query_definition,
        )
        db.add(job)
        db.commit()

        # Capture job_id before task runs (task may close session)
        job_id = job.id
        process_export_job(str(job_id))

        # Query fresh since the task closed its session
        from sqlalchemy import select
        job = db.execute(select(ExportJob).where(ExportJob.id == job_id)).scalar_one()
        assert job.status == "failed"
        assert job.error_message is not None


class TestProcessScheduledReport:
    """Test scheduled report processing."""

    def test_process_scheduled_report(
        self, db, tenant_id, reports_user, test_finance_entries, monkeypatch
    ):
        """Test processing scheduled report."""
        # Mock SessionLocal to return the test database session
        monkeypatch.setattr("app.jobs.tasks.SessionLocal", lambda: db)
        
        class MockS3Client:
            def upload_file(self, file_content, key, content_type=None):
                return key

            def get_presigned_url(self, key, expiration=3600):
                return f"https://s3.example.com/{key}"

        monkeypatch.setattr("app.jobs.tasks.S3Client", MockS3Client)
        monkeypatch.setattr("app.jobs.tasks.enqueue_email_notification", lambda *args, **kwargs: None)

        # Create template
        query_definition = {
            "entity_type": "finance_entries",
            "filters": {},
        }

        template = ReportTemplate(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
            name="Scheduled Template",
            query_definition=query_definition,
        )
        db.add(template)
        db.commit()

        # Create schedule
        schedule = ReportSchedule(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
            template_id=template.id,
            frequency="daily",
            time=time(9, 0),
            recipients=["recipient@test.com"],
            is_active=True,
            next_run_at=datetime.now(timezone.utc),
        )
        db.add(schedule)
        db.commit()

        # Process schedule
        process_scheduled_report(str(schedule.id))

        # Verify schedule updated - query fresh since the task closed its session
        schedule_id = schedule.id
        from sqlalchemy import select
        schedule = db.execute(select(ReportSchedule).where(ReportSchedule.id == schedule_id)).scalar_one()
        assert schedule.last_run_at is not None
        assert schedule.next_run_at is not None

    def test_process_scheduled_report_inactive(
        self, db, tenant_id, reports_user, monkeypatch
    ):
        """Test that inactive schedules are skipped."""
        # Mock SessionLocal to return the test database session
        monkeypatch.setattr("app.jobs.tasks.SessionLocal", lambda: db)
        
        query_definition = {
            "entity_type": "finance_entries",
            "filters": {},
        }

        template = ReportTemplate(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
            name="Template",
            query_definition=query_definition,
        )
        db.add(template)
        db.commit()

        schedule = ReportSchedule(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=reports_user.id,
            template_id=template.id,
            frequency="daily",
            time=time(9, 0),
            recipients=["test@example.com"],
            is_active=False,
            next_run_at=datetime.now(timezone.utc),
        )
        db.add(schedule)
        db.commit()

        # Process should not fail, just skip
        process_scheduled_report(str(schedule.id))

        # Query fresh since the task closed its session
        schedule_id = schedule.id
        from sqlalchemy import select
        schedule = db.execute(select(ReportSchedule).where(ReportSchedule.id == schedule_id)).scalar_one()
        assert schedule.is_active is False

