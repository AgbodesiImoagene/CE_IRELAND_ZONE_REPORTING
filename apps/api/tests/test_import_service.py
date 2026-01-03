"""Tests for import service layer."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.common.models import ImportJob, People, Permission, RolePermission
from app.imports.service import ImportService
from app.imports.parsers import ImportFormat


@pytest.fixture
def import_permissions(db, tenant_id, test_role):
    """Create import permissions."""
    perms = [
        ("imports.create", "Create imports"),
        ("imports.execute", "Execute imports"),
        ("registry.people.create", "Create people"),
        ("cells.manage", "Manage cells"),
        ("cells.reports.create", "Create cell reports"),
        ("finance.entries.create", "Create finance entries"),
    ]

    created_perms = []
    for code, desc in perms:
        perm = Permission(id=uuid4(), code=code, description=desc)
        db.add(perm)
        db.flush()
        created_perms.append(perm)

        role_perm = RolePermission(role_id=test_role.id, permission_id=perm.id)
        db.add(role_perm)

    db.commit()
    return created_perms


class TestImportService:
    """Tests for ImportService."""

    def test_upload_file_csv(self, db, tenant_id, test_user, import_permissions, monkeypatch):
        """Test uploading a CSV file."""
        # Mock S3 client
        class MockS3Client:
            def upload_file(self, file_content, key):
                return key

            def download_file(self, key):
                return b"first_name,last_name,email\nJohn,Doe,john@test.com"

        monkeypatch.setattr("app.imports.service.S3Client", MockS3Client)

        csv_content = b"first_name,last_name,email\nJohn,Doe,john@test.com"
        job = ImportService.upload_file(
            db=db,
            user_id=test_user.id,
            tenant_id=UUID(tenant_id),
            file_content=csv_content,
            filename="test.csv",
            entity_type="people",
            import_mode="create_only",
        )

        assert job is not None
        assert job.entity_type == "people"
        assert job.file_format == "csv"
        assert job.status == "pending"

    def test_create_preview(self, db, tenant_id, test_user, test_org_unit, import_permissions, monkeypatch):
        """Test creating a preview."""
        # Mock S3 client
        class MockS3Client:
            def upload_file(self, file_content, key):
                return key

            def download_file(self, key):
                return b"first_name,last_name,email\nJohn,Doe,john@test.com"

        monkeypatch.setattr("app.imports.service.S3Client", MockS3Client)

        # Create import job
        csv_content = b"first_name,last_name,email\nJohn,Doe,john@test.com"
        job = ImportService.upload_file(
            db=db,
            user_id=test_user.id,
            tenant_id=UUID(tenant_id),
            file_content=csv_content,
            filename="test.csv",
            entity_type="people",
        )

        # Create preview
        preview = ImportService.create_preview(
            db=db,
            job_id=job.id,
            tenant_id=UUID(tenant_id),
        )

        assert preview is not None
        assert preview["total_rows"] == 1
        assert len(preview["sample_rows"]) > 0
        assert "mapping_suggestions" in preview

    def test_update_mapping(self, db, tenant_id, test_user, import_permissions, monkeypatch):
        """Test updating column mapping."""
        # Mock S3 client
        class MockS3Client:
            def upload_file(self, file_content, key):
                return key

            def download_file(self, key):
                return b"first_name,last_name,email\nJohn,Doe,john@test.com"

        monkeypatch.setattr("app.imports.service.S3Client", MockS3Client)

        # Create import job
        csv_content = b"first_name,last_name,email\nJohn,Doe,john@test.com"
        job = ImportService.upload_file(
            db=db,
            user_id=test_user.id,
            tenant_id=UUID(tenant_id),
            file_content=csv_content,
            filename="test.csv",
            entity_type="people",
        )

        # Update mapping
        mapping_config = {
            "first_name": {"target_field": "first_name", "required": True},
            "last_name": {"target_field": "last_name", "required": True},
        }
        updated_job = ImportService.update_mapping(
            db=db,
            job_id=job.id,
            tenant_id=UUID(tenant_id),
            mapping_config=mapping_config,
        )

        assert updated_job.mapping_config == mapping_config
        assert updated_job.status == "mapping"

    def test_get_job_status(self, db, tenant_id, test_user, import_permissions, monkeypatch):
        """Test getting job status."""
        # Mock S3 client
        class MockS3Client:
            def upload_file(self, file_content, key):
                return key

        monkeypatch.setattr("app.imports.service.S3Client", MockS3Client)

        # Create import job
        csv_content = b"first_name,last_name,email\nJohn,Doe,john@test.com"
        job = ImportService.upload_file(
            db=db,
            user_id=test_user.id,
            tenant_id=UUID(tenant_id),
            file_content=csv_content,
            filename="test.csv",
            entity_type="people",
        )

        # Get job status
        status = ImportService.get_job_status(db, job.id, UUID(tenant_id))
        assert status is not None
        assert status.id == job.id
        assert status.status == "pending"

    def test_upload_file_cells(self, db, tenant_id, test_user, test_org_unit, import_permissions, monkeypatch):
        """Test uploading a CSV file for cells."""
        # Mock S3 client
        class MockS3Client:
            def upload_file(self, file_content, key):
                return key

            def download_file(self, key):
                return b"name,venue,meeting_day\nAlpha Cell,Room 101,Monday"

        monkeypatch.setattr("app.imports.service.S3Client", MockS3Client)

        csv_content = b"name,venue,meeting_day\nAlpha Cell,Room 101,Monday"
        job = ImportService.upload_file(
            db=db,
            user_id=test_user.id,
            tenant_id=UUID(tenant_id),
            file_content=csv_content,
            filename="cells.csv",
            entity_type="cells",
            import_mode="create_only",
        )

        assert job is not None
        assert job.entity_type == "cells"
        assert job.file_format == "csv"
        assert job.status == "pending"

    def test_upload_file_finance_entries(self, db, tenant_id, test_user, test_org_unit, import_permissions, monkeypatch):
        """Test uploading a CSV file for finance entries."""
        # Mock S3 client
        class MockS3Client:
            def upload_file(self, file_content, key):
                return key

            def download_file(self, key):
                return b"fund_id,amount,transaction_date,external_giver_name\n123e4567-e89b-12d3-a456-426614174000,100.50,2024-01-15,Anonymous"

        monkeypatch.setattr("app.imports.service.S3Client", MockS3Client)

        csv_content = b"fund_id,amount,transaction_date,external_giver_name\n123e4567-e89b-12d3-a456-426614174000,100.50,2024-01-15,Anonymous"
        job = ImportService.upload_file(
            db=db,
            user_id=test_user.id,
            tenant_id=UUID(tenant_id),
            file_content=csv_content,
            filename="finance.csv",
            entity_type="finance_entries",
            import_mode="create_only",
        )

        assert job is not None
        assert job.entity_type == "finance_entries"
        assert job.file_format == "csv"
        assert job.status == "pending"

    def test_create_preview_cell_reports(self, db, tenant_id, test_user, test_org_unit, import_permissions, monkeypatch):
        """Test creating a preview for cell reports."""
        # Mock S3 client
        class MockS3Client:
            def upload_file(self, file_content, key):
                return key

            def download_file(self, key):
                return b"cell_id,report_date,attendance,offerings_total\n123e4567-e89b-12d3-a456-426614174000,2024-01-15,15,50.00"

        monkeypatch.setattr("app.imports.service.S3Client", MockS3Client)

        # Create import job
        csv_content = b"cell_id,report_date,attendance,offerings_total\n123e4567-e89b-12d3-a456-426614174000,2024-01-15,15,50.00"
        job = ImportService.upload_file(
            db=db,
            user_id=test_user.id,
            tenant_id=UUID(tenant_id),
            file_content=csv_content,
            filename="cell_reports.csv",
            entity_type="cell_reports",
        )

        # Create preview
        preview = ImportService.create_preview(
            db=db,
            job_id=job.id,
            tenant_id=UUID(tenant_id),
        )

        assert preview is not None
        assert preview["total_rows"] == 1
        assert len(preview["sample_rows"]) > 0
        assert "mapping_suggestions" in preview

    def test_validate_preview_success(self, db, tenant_id, test_user, import_permissions, monkeypatch):
        """Test validating preview."""
        # Mock S3 client
        class MockS3Client:
            def upload_file(self, file_content, key):
                return key

            def download_file(self, key):
                return b"first_name,last_name,email\nJohn,Doe,john@test.com"

        monkeypatch.setattr("app.imports.service.S3Client", MockS3Client)

        # Create import job
        csv_content = b"first_name,last_name,email\nJohn,Doe,john@test.com"
        job = ImportService.upload_file(
            db=db,
            user_id=test_user.id,
            tenant_id=UUID(tenant_id),
            file_content=csv_content,
            filename="test.csv",
            entity_type="people",
        )

        # Set mapping
        job.mapping_config = {
            "first_name": {"target_field": "first_name", "required": True},
        }
        db.commit()

        # Validate
        validation = ImportService.validate_preview(
            db=db,
            job_id=job.id,
            tenant_id=UUID(tenant_id),
        )

        assert validation is not None
        assert "total_errors" in validation
        assert "errors_by_type" in validation
        assert job.status == "validating"

    def test_validate_preview_no_mapping(self, db, tenant_id, test_user, import_permissions, monkeypatch):
        """Test validating preview without mapping."""
        # Mock S3 client
        class MockS3Client:
            def upload_file(self, file_content, key):
                return key

        monkeypatch.setattr("app.imports.service.S3Client", MockS3Client)

        # Create import job
        csv_content = b"first_name,last_name,email\nJohn,Doe,john@test.com"
        job = ImportService.upload_file(
            db=db,
            user_id=test_user.id,
            tenant_id=UUID(tenant_id),
            file_content=csv_content,
            filename="test.csv",
            entity_type="people",
        )

        # Validate without mapping
        with pytest.raises(ValueError, match="Mapping configuration not set"):
            ImportService.validate_preview(
                db=db,
                job_id=job.id,
                tenant_id=UUID(tenant_id),
            )

    def test_download_error_report_success(self, db, tenant_id, test_user, import_permissions, monkeypatch):
        """Test downloading error report."""
        # Mock S3 client
        class MockS3Client:
            def upload_file(self, file_content, key):
                return key

            def download_file(self, key):
                return b"row_number,column_name,error_type,error_message\n1,email,validation,Invalid"

        monkeypatch.setattr("app.imports.service.S3Client", MockS3Client)

        # Create import job with error file
        csv_content = b"first_name,last_name,email\nJohn,Doe,john@test.com"
        job = ImportService.upload_file(
            db=db,
            user_id=test_user.id,
            tenant_id=UUID(tenant_id),
            file_content=csv_content,
            filename="test.csv",
            entity_type="people",
        )

        job.error_file_path = "imports/test/errors.csv"
        db.commit()

        # Download error report
        content = ImportService.download_error_report(
            db=db,
            job_id=job.id,
            tenant_id=UUID(tenant_id),
        )

        assert content is not None
        assert b"error_message" in content

    def test_download_error_report_not_found(self, db, tenant_id, test_user, import_permissions, monkeypatch):
        """Test downloading error report when not available."""
        # Mock S3 client
        class MockS3Client:
            def upload_file(self, file_content, key):
                return key

        monkeypatch.setattr("app.imports.service.S3Client", MockS3Client)

        # Create import job without error file
        csv_content = b"first_name,last_name,email\nJohn,Doe,john@test.com"
        job = ImportService.upload_file(
            db=db,
            user_id=test_user.id,
            tenant_id=UUID(tenant_id),
            file_content=csv_content,
            filename="test.csv",
            entity_type="people",
        )

        # Download error report
        content = ImportService.download_error_report(
            db=db,
            job_id=job.id,
            tenant_id=UUID(tenant_id),
        )

        assert content is None

    def test_get_job_status_not_found(self, db, tenant_id, test_user, import_permissions):
        """Test getting non-existent job status."""
        fake_id = uuid4()
        status = ImportService.get_job_status(db, fake_id, UUID(tenant_id))
        assert status is None

    def test_get_job_status_wrong_tenant(self, db, tenant_id, test_user, import_permissions, monkeypatch):
        """Test getting job from different tenant."""
        # Mock S3 client
        class MockS3Client:
            def upload_file(self, file_content, key):
                return key

        monkeypatch.setattr("app.imports.service.S3Client", MockS3Client)

        # Create job
        csv_content = b"first_name,last_name,email\nJohn,Doe,john@test.com"
        job = ImportService.upload_file(
            db=db,
            user_id=test_user.id,
            tenant_id=UUID(tenant_id),
            file_content=csv_content,
            filename="test.csv",
            entity_type="people",
        )

        # Try to get with different tenant
        other_tenant = uuid4()
        status = ImportService.get_job_status(db, job.id, other_tenant)
        assert status is None

