"""Tests for import background tasks."""

from __future__ import annotations

from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from app.common.models import ImportJob, ImportError
from app.jobs.tasks import process_import_job


@pytest.fixture
def test_import_job(db, tenant_id, test_user, monkeypatch):
    """Create a test import job."""
    # Mock S3 client
    class MockS3Client:
        def download_file(self, key):
            return b"first_name,last_name,email\nJohn,Doe,john@test.com"

        def upload_file(self, content, key, content_type=None):
            return key

    monkeypatch.setattr("app.jobs.tasks.S3Client", MockS3Client)

    # Mock processor
    from app.imports.processors import ProcessResult
    class MockProcessor:
        def requires_org_unit(self):
            return False

        def process_row(
            self, db, row, mapping, mode, tenant_id, user_id, org_unit_id=None
        ):
            return ProcessResult(success=True, errors=[])

    monkeypatch.setattr(
        "app.imports.processors.get_processor",
        lambda entity_type: MockProcessor(),
    )

    # Mock email notification
    monkeypatch.setattr(
        "app.jobs.tasks.enqueue_email_notification", lambda **kwargs: None
    )

    job = ImportJob(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        user_id=test_user.id,
        entity_type="people",
        file_name="test.csv",
        file_format="csv",
        file_path="imports/test/test.csv",
        file_size=100,
        status="queued",
        mapping_config={
            "first_name": {"target_field": "first_name"},
            "last_name": {"target_field": "last_name"},
            "email": {"target_field": "email"},
        },
    )
    db.add(job)
    db.commit()
    return job


class TestProcessImportJob:
    """Test import job processing."""

    def test_process_import_job_success(self, db, test_import_job):
        """Test successful import processing."""
        # Mock SessionLocal to use test database session
        with patch("app.jobs.tasks.SessionLocal", return_value=db):
            with patch.object(db, "close"):  # Prevent closing test session
                process_import_job(str(test_import_job.id))

        db.refresh(test_import_job)
        assert test_import_job.status == "completed"
        assert test_import_job.processed_rows > 0
        assert test_import_job.imported_count > 0
        assert test_import_job.started_at is not None
        assert test_import_job.completed_at is not None

    def test_process_import_job_not_found(self, db, caplog):
        """Test processing non-existent job."""
        fake_id = uuid4()
        process_import_job(str(fake_id))

        # Check for error log about job not found
        assert "import job" in caplog.text.lower() and ("not found" in caplog.text.lower() or "failed" in caplog.text.lower())

    def test_process_import_job_with_errors(self, db, tenant_id, test_user, monkeypatch):
        """Test processing import with errors."""
        # Mock S3 client
        class MockS3Client:
            def download_file(self, key):
                return b"first_name,last_name,email\nJohn,Doe,invalid-email"

            def upload_file(self, content, key, content_type=None):
                return key

        monkeypatch.setattr("app.jobs.tasks.S3Client", MockS3Client)

        # Mock processor with errors
        from app.imports.processors import ProcessResult
        from app.imports.validators import ValidationError

        class MockProcessor:
            def requires_org_unit(self):
                return False

            def process_row(
                self, db, row, mapping, mode, tenant_id, user_id, org_unit_id=None
            ):
                return ProcessResult(
                    success=False,
                    errors=[
                        ValidationError(
                            row_number=1,
                            field="email",
                            error_type="validation",
                            message="Invalid email",
                            original_value="invalid-email",
                        )
                    ],
                )

        monkeypatch.setattr(
            "app.imports.processors.get_processor",
            lambda entity_type: MockProcessor(),
        )
        monkeypatch.setattr(
            "app.jobs.tasks.enqueue_email_notification", lambda **kwargs: None
        )

        job = ImportJob(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
            entity_type="people",
            file_name="test.csv",
            file_format="csv",
            file_path="imports/test/test.csv",
            file_size=100,
            status="queued",
            mapping_config={
                "email": {"target_field": "email"},
            },
        )
        db.add(job)
        db.commit()

        # Mock SessionLocal to use test database session
        with patch("app.jobs.tasks.SessionLocal", return_value=db):
            with patch.object(db, "close"):  # Prevent closing test session
                process_import_job(str(job.id))

        db.refresh(job)
        assert job.status == "completed"
        assert job.error_count > 0
        assert job.error_file_path is not None

        # Check errors were stored
        from sqlalchemy import select
        errors = db.execute(
            select(ImportError).where(ImportError.import_job_id == job.id)
        ).scalars().all()
        assert len(errors) > 0

    def test_process_import_job_exception_handling(self, db, tenant_id, test_user, monkeypatch):
        """Test exception handling during processing."""
        # Mock S3 client to raise exception
        class MockS3Client:
            def download_file(self, key):
                raise Exception("S3 error")

        monkeypatch.setattr("app.jobs.tasks.S3Client", MockS3Client)

        job = ImportJob(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
            entity_type="people",
            file_name="test.csv",
            file_format="csv",
            file_path="imports/test/test.csv",
            file_size=100,
            status="queued",
            mapping_config={},  # Add empty mapping to avoid KeyError
        )
        db.add(job)
        db.commit()

        # Mock SessionLocal to use test database session
        with patch("app.jobs.tasks.SessionLocal", return_value=db):
            with patch.object(db, "close"):  # Prevent closing test session
                process_import_job(str(job.id))

        # Refresh from database to get updated status
        db.refresh(job)
        # The job should be marked as failed after exception
        assert job.status == "failed"
        assert job.completed_at is not None

    def test_process_import_job_progress_updates(self, db, tenant_id, test_user, monkeypatch):
        """Test that progress is updated during processing."""
        # Mock S3 client with many rows
        class MockS3Client:
            def download_file(self, key):
                rows = ["first_name,last_name,email"]
                rows.extend(
                    [f"John{i},Doe{i},john{i}@test.com" for i in range(250)]
                )
                return "\n".join(rows).encode()

            def upload_file(self, content, key, content_type=None):
                return key

        monkeypatch.setattr("app.jobs.tasks.S3Client", MockS3Client)

        # Mock processor
        from app.imports.processors import ProcessResult

        class MockProcessor:
            def requires_org_unit(self):
                return False

            def process_row(
                self, db, row, mapping, mode, tenant_id, user_id, org_unit_id=None
            ):
                return ProcessResult(success=True, errors=[])

        monkeypatch.setattr(
            "app.imports.processors.get_processor",
            lambda entity_type: MockProcessor(),
        )
        monkeypatch.setattr(
            "app.jobs.tasks.enqueue_email_notification", lambda **kwargs: None
        )

        job = ImportJob(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
            entity_type="people",
            file_name="test.csv",
            file_format="csv",
            file_path="imports/test/test.csv",
            file_size=100,
            status="queued",
            mapping_config={
                "first_name": {"target_field": "first_name"},
            },
        )
        db.add(job)
        db.commit()

        # Mock SessionLocal to use test database session
        with patch("app.jobs.tasks.SessionLocal", return_value=db):
            with patch.object(db, "close"):  # Prevent closing test session
                process_import_job(str(job.id))

        db.refresh(job)
        assert job.processed_rows == 250
        assert job.imported_count == 250

    def test_process_import_job_email_notification(self, db, tenant_id, test_user, monkeypatch):
        """Test email notification is sent."""
        # Mock S3 client
        class MockS3Client:
            def download_file(self, key):
                return b"first_name,last_name,email\nJohn,Doe,john@test.com"

            def upload_file(self, content, key, content_type=None):
                return key

        monkeypatch.setattr("app.jobs.tasks.S3Client", MockS3Client)

        # Mock processor
        from app.imports.processors import ProcessResult

        class MockProcessor:
            def requires_org_unit(self):
                return False

            def process_row(
                self, db, row, mapping, mode, tenant_id, user_id, org_unit_id=None
            ):
                return ProcessResult(success=True, errors=[])

        monkeypatch.setattr(
            "app.imports.processors.get_processor",
            lambda entity_type: MockProcessor(),
        )

        # Track email calls
        email_calls = []

        def mock_enqueue_email(**kwargs):
            email_calls.append(kwargs)

        monkeypatch.setattr(
            "app.jobs.tasks.enqueue_email_notification", mock_enqueue_email
        )

        job = ImportJob(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=test_user.id,
            entity_type="people",
            file_name="test.csv",
            file_format="csv",
            file_path="imports/test/test.csv",
            file_size=100,
            status="queued",
            mapping_config={
                "first_name": {"target_field": "first_name"},
            },
        )
        db.add(job)
        db.commit()

        # Mock SessionLocal to use test database session
        with patch("app.jobs.tasks.SessionLocal", return_value=db):
            with patch.object(db, "close"):  # Prevent closing test session
                process_import_job(str(job.id))

        assert len(email_calls) == 1
        assert email_calls[0]["email"] == test_user.email
        assert "completed" in email_calls[0]["subject"].lower()

