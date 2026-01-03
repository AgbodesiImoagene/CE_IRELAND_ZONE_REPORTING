"""Tests for import API routes."""

from __future__ import annotations

from io import BytesIO
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.common.models import ImportJob, Permission, RolePermission, User
from app.imports.parsers import ImportFormat


@pytest.fixture
def import_permissions(db, tenant_id, test_role):
    """Create import permissions."""
    perms = [
        ("imports.create", "Create imports"),
        ("imports.execute", "Execute imports"),
        ("imports.read", "Read imports"),
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


@pytest.fixture
def import_user(db, tenant_id, test_role, test_org_unit, import_permissions):
    """Create a user with import permissions."""
    from app.common.models import OrgAssignment
    from app.auth.utils import hash_password

    user = User(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        email="import@test.com",
        password_hash=hash_password("testpass123"),
        is_active=True,
    )
    db.add(user)
    db.flush()

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
def import_auth_headers(import_user):
    """Create auth headers for import user."""
    from app.auth.utils import create_access_token

    token = create_access_token(
        {"sub": str(import_user.id), "user_id": str(import_user.id)}
    )
    return {"Authorization": f"Bearer {token}"}


class TestImportUpload:
    """Test import file upload."""

    def test_upload_file_success(self, client: TestClient, import_user, import_permissions, import_auth_headers, monkeypatch):
        """Test successful file upload."""
        # Mock S3 client
        class MockS3Client:
            def upload_file(self, file_content, key):
                return key

        monkeypatch.setattr("app.imports.service.S3Client", MockS3Client)

        # Upload file
        csv_content = b"first_name,last_name,email\nJohn,Doe,john@test.com"
        response = client.post(
            "/api/v1/imports/upload",
            headers=import_auth_headers,
            files={"file": ("test.csv", BytesIO(csv_content), "text/csv")},
            params={"entity_type": "people", "import_mode": "create_only"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["entity_type"] == "people"
        assert data["file_format"] == "csv"
        assert data["status"] == "pending"

    def test_upload_file_too_large(self, client: TestClient, import_user, import_permissions, import_auth_headers):
        """Test file size limit."""
        # Upload large file (101MB)
        large_content = b"x" * (101 * 1024 * 1024)
        response = client.post(
            "/api/v1/imports/upload",
            headers=import_auth_headers,
            files={"file": ("large.csv", BytesIO(large_content), "text/csv")},
            params={"entity_type": "people"},
        )

        assert response.status_code == 413

    def test_upload_file_invalid_format(self, client: TestClient, import_user, import_permissions, import_auth_headers, monkeypatch):
        """Test upload with unsupported format."""
        # Mock S3 client
        class MockS3Client:
            def upload_file(self, file_content, key):
                return key

        monkeypatch.setattr("app.imports.service.S3Client", MockS3Client)
        
        # Mock detect_file_format to return UNKNOWN for .txt files
        from app.imports.parsers import ImportFormat
        original_detect = None
        def mock_detect(file_content, filename):
            if filename.endswith('.txt'):
                return ImportFormat.UNKNOWN
            # Import here to avoid circular import
            from app.imports.parsers import detect_file_format as orig
            return orig(file_content, filename)
        
        monkeypatch.setattr("app.imports.service.detect_file_format", mock_detect)

        # Upload unsupported file
        response = client.post(
            "/api/v1/imports/upload",
            headers=import_auth_headers,
            files={"file": ("test.txt", BytesIO(b"plain text"), "text/plain")},
            params={"entity_type": "people"},
        )

        assert response.status_code == 400


class TestImportJobStatus:
    """Test getting import job status."""

    def test_get_job_status_success(self, client: TestClient, import_user, import_permissions, import_auth_headers, db, tenant_id, monkeypatch):
        """Test getting job status."""
        # Mock S3 client
        class MockS3Client:
            def upload_file(self, file_content, key):
                return key

        monkeypatch.setattr("app.imports.service.S3Client", MockS3Client)

        # Create job
        csv_content = b"first_name,last_name,email\nJohn,Doe,john@test.com"
        job = ImportJob(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=import_user.id,
            entity_type="people",
            file_name="test.csv",
            file_format="csv",
            file_path="imports/test/test.csv",
            file_size=len(csv_content),
            status="pending",
        )
        db.add(job)
        db.commit()

        headers = import_auth_headers

        # Get status
        response = client.get(
            f"/api/v1/imports/jobs/{job.id}",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(job.id)
        assert data["status"] == "pending"

    def test_get_job_status_not_found(self, client: TestClient, import_user, import_permissions, import_auth_headers):
        """Test getting non-existent job."""
        headers = import_auth_headers

        # Get status
        fake_id = uuid4()
        response = client.get(
            f"/api/v1/imports/jobs/{fake_id}",
            headers=headers,
        )

        assert response.status_code == 404


class TestImportPreview:
    """Test import preview."""

    def test_create_preview_success(self, client: TestClient, import_user, import_permissions, import_auth_headers, db, tenant_id, monkeypatch):
        """Test creating preview."""
        # Mock S3 client
        class MockS3Client:
            def upload_file(self, file_content, key):
                return key

            def download_file(self, key):
                return b"first_name,last_name,email\nJohn,Doe,john@test.com"

        monkeypatch.setattr("app.imports.service.S3Client", MockS3Client)

        # Create job
        csv_content = b"first_name,last_name,email\nJohn,Doe,john@test.com"
        job = ImportJob(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=import_user.id,
            entity_type="people",
            file_name="test.csv",
            file_format="csv",
            file_path="imports/test/test.csv",
            file_size=len(csv_content),
            status="pending",
        )
        db.add(job)
        db.commit()

        headers = import_auth_headers

        # Create preview
        response = client.post(
            f"/api/v1/imports/jobs/{job.id}/preview",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_rows"] == 1
        assert len(data["sample_rows"]) > 0

    def test_create_preview_with_mapping(self, client: TestClient, import_user, import_permissions, import_auth_headers, db, tenant_id, monkeypatch):
        """Test creating preview with custom mapping."""
        # Mock S3 client
        class MockS3Client:
            def upload_file(self, file_content, key):
                return key

            def download_file(self, key):
                return b"first_name,last_name,email\nJohn,Doe,john@test.com"

        monkeypatch.setattr("app.imports.service.S3Client", MockS3Client)

        # Create job
        csv_content = b"first_name,last_name,email\nJohn,Doe,john@test.com"
        job = ImportJob(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=import_user.id,
            entity_type="people",
            file_name="test.csv",
            file_format="csv",
            file_path="imports/test/test.csv",
            file_size=len(csv_content),
            status="pending",
        )
        db.add(job)
        db.commit()

        headers = import_auth_headers

        # Create preview with mapping (using proper schema structure)
        mapping = {
            "mapping_config": {
                "first_name": {
                    "source_column": "first_name",
                    "target_field": "first_name",
                    "coercion_type": None,
                    "required": True,
                    "default_value": None,
                }
            }
        }
        response = client.post(
            f"/api/v1/imports/jobs/{job.id}/preview",
            headers=headers,
            json=mapping,
        )

        assert response.status_code == 200


class TestImportMapping:
    """Test updating import mapping."""

    def test_update_mapping_success(self, client: TestClient, import_user, import_permissions, import_auth_headers, db, tenant_id, monkeypatch):
        """Test updating mapping."""
        # Mock S3 client
        class MockS3Client:
            def upload_file(self, file_content, key):
                return key

        monkeypatch.setattr("app.imports.service.S3Client", MockS3Client)

        # Create job
        csv_content = b"first_name,last_name,email\nJohn,Doe,john@test.com"
        job = ImportJob(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=import_user.id,
            entity_type="people",
            file_name="test.csv",
            file_format="csv",
            file_path="imports/test/test.csv",
            file_size=len(csv_content),
            status="previewing",
        )
        db.add(job)
        db.commit()

        headers = import_auth_headers

        # Update mapping (using proper schema structure)
        mapping = {
            "mapping_config": {
                "first_name": {
                    "source_column": "first_name",
                    "target_field": "first_name",
                    "coercion_type": None,
                    "required": True,
                    "default_value": None,
                }
            }
        }
        response = client.patch(
            f"/api/v1/imports/jobs/{job.id}/mapping",
            headers=headers,
            json=mapping,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "mapping"


class TestImportValidation:
    """Test import validation."""

    def test_validate_preview_success(self, client: TestClient, import_user, import_permissions, import_auth_headers, db, tenant_id, monkeypatch):
        """Test validating preview."""
        # Mock S3 client
        class MockS3Client:
            def upload_file(self, file_content, key):
                return key

            def download_file(self, key):
                return b"first_name,last_name,email\nJohn,Doe,john@test.com"

        monkeypatch.setattr("app.imports.service.S3Client", MockS3Client)

        # Create job with mapping
        csv_content = b"first_name,last_name,email\nJohn,Doe,john@test.com"
        job = ImportJob(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=import_user.id,
            entity_type="people",
            file_name="test.csv",
            file_format="csv",
            file_path="imports/test/test.csv",
            file_size=len(csv_content),
            status="mapping",
            mapping_config={
                "first_name": {"target_field": "first_name", "required": True},
            },
        )
        db.add(job)
        db.commit()

        headers = import_auth_headers

        # Validate
        response = client.post(
            f"/api/v1/imports/jobs/{job.id}/validate",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "total_errors" in data
        assert "errors_by_type" in data


class TestImportExecute:
    """Test executing import."""

    def test_execute_import_success(self, client: TestClient, import_user, import_permissions, import_auth_headers, db, tenant_id, monkeypatch):
        """Test executing import."""
        # Mock S3 client
        class MockS3Client:
            def upload_file(self, file_content, key):
                return key

        monkeypatch.setattr("app.imports.service.S3Client", MockS3Client)
        
        # Mock queue
        mock_queue = type("MockQueue", (), {
            "enqueue": lambda self, func, *args: None
        })()
        monkeypatch.setattr("app.imports.routes.imports_queue", mock_queue)

        # Create job
        csv_content = b"first_name,last_name,email\nJohn,Doe,john@test.com"
        job = ImportJob(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=import_user.id,
            entity_type="people",
            file_name="test.csv",
            file_format="csv",
            file_path="imports/test/test.csv",
            file_size=len(csv_content),
            status="validating",
            mapping_config={
                "first_name": {"target_field": "first_name", "required": True},
            },
        )
        db.add(job)
        db.commit()

        headers = import_auth_headers

        # Execute
        response = client.post(
            f"/api/v1/imports/jobs/{job.id}/execute",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"

    def test_execute_import_invalid_status(self, client: TestClient, import_user, import_permissions, import_auth_headers, db, tenant_id, monkeypatch):
        """Test executing import with invalid status."""
        # Mock S3 client
        class MockS3Client:
            def upload_file(self, file_content, key):
                return key

        monkeypatch.setattr("app.imports.service.S3Client", MockS3Client)

        # Create job with invalid status
        csv_content = b"first_name,last_name,email\nJohn,Doe,john@test.com"
        job = ImportJob(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=import_user.id,
            entity_type="people",
            file_name="test.csv",
            file_format="csv",
            file_path="imports/test/test.csv",
            file_size=len(csv_content),
            status="completed",
        )
        db.add(job)
        db.commit()

        headers = import_auth_headers

        # Execute
        response = client.post(
            f"/api/v1/imports/jobs/{job.id}/execute",
            headers=headers,
        )

        assert response.status_code == 400

    def test_execute_import_no_mapping(self, client: TestClient, import_user, import_permissions, import_auth_headers, db, tenant_id, monkeypatch):
        """Test executing import without mapping."""
        # Mock S3 client
        class MockS3Client:
            def upload_file(self, file_content, key):
                return key

        monkeypatch.setattr("app.imports.service.S3Client", MockS3Client)

        # Create job without mapping
        csv_content = b"first_name,last_name,email\nJohn,Doe,john@test.com"
        job = ImportJob(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=import_user.id,
            entity_type="people",
            file_name="test.csv",
            file_format="csv",
            file_path="imports/test/test.csv",
            file_size=len(csv_content),
            status="previewing",
            mapping_config=None,
        )
        db.add(job)
        db.commit()

        headers = import_auth_headers

        # Execute
        response = client.post(
            f"/api/v1/imports/jobs/{job.id}/execute",
            headers=headers,
        )

        assert response.status_code == 400


class TestImportErrorReport:
    """Test downloading error report."""

    def test_download_error_report_success(self, client: TestClient, import_user, import_permissions, import_auth_headers, db, tenant_id, monkeypatch):
        """Test downloading error report."""
        # Mock S3 client
        class MockS3Client:
            def upload_file(self, file_content, key):
                return key

            def download_file(self, key):
                return b"row_number,column_name,error_type,error_message\n1,email,validation,Invalid email"

        monkeypatch.setattr("app.imports.service.S3Client", MockS3Client)

        # Create job with error file
        csv_content = b"first_name,last_name,email\nJohn,Doe,john@test.com"
        job = ImportJob(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=import_user.id,
            entity_type="people",
            file_name="test.csv",
            file_format="csv",
            file_path="imports/test/test.csv",
            file_size=len(csv_content),
            status="completed",
            error_file_path="imports/test/errors.csv",
        )
        db.add(job)
        db.commit()

        headers = import_auth_headers

        # Download error report
        response = client.get(
            f"/api/v1/imports/jobs/{job.id}/errors",
            headers=headers,
        )

        assert response.status_code == 200
        # Content-Type may include charset
        assert "text/csv" in response.headers["content-type"]

    def test_download_error_report_not_found(self, client: TestClient, import_user, import_permissions, import_auth_headers, db, tenant_id, monkeypatch):
        """Test downloading error report when not available."""
        # Mock S3 client
        class MockS3Client:
            def upload_file(self, file_content, key):
                return key

        monkeypatch.setattr("app.imports.service.S3Client", MockS3Client)

        # Create job without error file
        csv_content = b"first_name,last_name,email\nJohn,Doe,john@test.com"
        job = ImportJob(
            id=uuid4(),
            tenant_id=UUID(tenant_id),
            user_id=import_user.id,
            entity_type="people",
            file_name="test.csv",
            file_format="csv",
            file_path="imports/test/test.csv",
            file_size=len(csv_content),
            status="completed",
            error_file_path=None,
        )
        db.add(job)
        db.commit()

        headers = import_auth_headers

        # Download error report
        response = client.get(
            f"/api/v1/imports/jobs/{job.id}/errors",
            headers=headers,
        )

        assert response.status_code == 404


class TestListImportJobs:
    """Test listing import jobs."""

    def test_list_import_jobs_success(self, client: TestClient, import_user, import_permissions, import_auth_headers, db, tenant_id, monkeypatch):
        """Test listing import jobs."""
        # Mock S3 client
        class MockS3Client:
            def upload_file(self, file_content, key):
                return key

        monkeypatch.setattr("app.imports.service.S3Client", MockS3Client)

        # Create jobs
        csv_content = b"first_name,last_name,email\nJohn,Doe,john@test.com"
        for i in range(3):
            job = ImportJob(
                id=uuid4(),
                tenant_id=UUID(tenant_id),
                user_id=import_user.id,
                entity_type="people",
                file_name=f"test{i}.csv",
                file_format="csv",
                file_path=f"imports/test/test{i}.csv",
                file_size=len(csv_content),
                status="pending",
            )
            db.add(job)
        db.commit()

        headers = import_auth_headers

        # List jobs
        response = client.get(
            "/api/v1/imports/jobs",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    def test_list_import_jobs_with_pagination(self, client: TestClient, import_user, import_permissions, import_auth_headers, db, tenant_id, monkeypatch):
        """Test listing import jobs with pagination."""
        # Mock S3 client
        class MockS3Client:
            def upload_file(self, file_content, key):
                return key

        monkeypatch.setattr("app.imports.service.S3Client", MockS3Client)

        # Create jobs
        csv_content = b"first_name,last_name,email\nJohn,Doe,john@test.com"
        for i in range(5):
            job = ImportJob(
                id=uuid4(),
                tenant_id=UUID(tenant_id),
                user_id=import_user.id,
                entity_type="people",
                file_name=f"test{i}.csv",
                file_format="csv",
                file_path=f"imports/test/test{i}.csv",
                file_size=len(csv_content),
                status="pending",
            )
            db.add(job)
        db.commit()

        headers = import_auth_headers

        # List jobs with limit
        response = client.get(
            "/api/v1/imports/jobs",
            headers=headers,
            params={"limit": 2, "offset": 0},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
