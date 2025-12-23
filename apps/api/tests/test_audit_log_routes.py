"""Tests for audit log routes."""

from __future__ import annotations

from uuid import UUID, uuid4
from fastapi.testclient import TestClient
import pytest


class TestAuditLogRoutes:
    """Tests for audit log routes."""

    def test_list_audit_logs_success(
        self, client: TestClient, iam_user, iam_token, test_org_unit, db
    ):
        """Test listing audit logs."""
        from app.common.audit import create_audit_log

        # Create an audit log
        log = create_audit_log(
            db=db,
            actor_id=iam_user.id,
            action="create",
            entity_type="org_units",
            entity_id=test_org_unit.id,
            after_json={"name": "Test Org"},
        )
        db.commit()

        response = client.get(
            "/api/v1/iam/audit-logs",
            headers={"Authorization": f"Bearer {iam_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert len(data["items"]) >= 1

    def test_list_audit_logs_with_filters(
        self, client: TestClient, iam_user, iam_token, test_org_unit, db
    ):
        """Test listing audit logs with filters."""
        from app.common.audit import create_audit_log

        # Create audit logs
        log1 = create_audit_log(
            db=db,
            actor_id=iam_user.id,
            action="create",
            entity_type="org_units",
            entity_id=test_org_unit.id,
        )
        log2 = create_audit_log(
            db=db,
            actor_id=iam_user.id,
            action="update",
            entity_type="roles",
            entity_id=uuid4(),
        )
        db.commit()

        # Filter by entity_type
        response = client.get(
            "/api/v1/iam/audit-logs",
            headers={"Authorization": f"Bearer {iam_token}"},
            params={"entity_type": "org_units"},
        )
        assert response.status_code == 200
        data = response.json()
        assert all(item["entity_type"] == "org_units" for item in data["items"])

    def test_list_audit_logs_with_actor_filter(
        self, client: TestClient, iam_user, iam_token, test_user, test_org_unit, db
    ):
        """Test listing audit logs filtered by actor."""
        from app.common.audit import create_audit_log

        # Create logs by different actors
        log1 = create_audit_log(
            db=db,
            actor_id=iam_user.id,
            action="create",
            entity_type="org_units",
            entity_id=test_org_unit.id,
        )
        log2 = create_audit_log(
            db=db,
            actor_id=test_user.id,
            action="create",
            entity_type="org_units",
            entity_id=test_org_unit.id,
        )
        db.commit()

        # Filter by actor_id
        response = client.get(
            "/api/v1/iam/audit-logs",
            headers={"Authorization": f"Bearer {iam_token}"},
            params={"actor_id": str(iam_user.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert all(
            item["actor_id"] == str(iam_user.id) for item in data["items"]
        )

    def test_list_audit_logs_pagination(
        self, client: TestClient, iam_user, iam_token, test_org_unit, db
    ):
        """Test pagination of audit logs."""
        from app.common.audit import create_audit_log

        # Create multiple logs
        for i in range(5):
            create_audit_log(
                db=db,
                actor_id=iam_user.id,
                action="create",
                entity_type="org_units",
                entity_id=test_org_unit.id,
            )
        db.commit()

        # Get first page
        response1 = client.get(
            "/api/v1/iam/audit-logs",
            headers={"Authorization": f"Bearer {iam_token}"},
            params={"page": 1, "per_page": 2},
        )
        assert response1.status_code == 200
        data1 = response1.json()
        assert len(data1["items"]) == 2
        assert data1["page"] == 1

        # Get second page
        response2 = client.get(
            "/api/v1/iam/audit-logs",
            headers={"Authorization": f"Bearer {iam_token}"},
            params={"page": 2, "per_page": 2},
        )
        assert response2.status_code == 200
        data2 = response2.json()
        assert len(data2["items"]) == 2
        assert data2["page"] == 2
        assert data1["items"][0]["id"] != data2["items"][0]["id"]

    def test_list_audit_logs_unauthorized(self, client: TestClient):
        """Test listing audit logs without auth."""
        response = client.get("/api/v1/iam/audit-logs")
        assert response.status_code == 401

    def test_list_audit_logs_forbidden(
        self, client: TestClient, test_user, test_org_unit, db
    ):
        """Test listing audit logs without permission."""
        from app.auth.utils import create_access_token

        token = create_access_token(
            {"sub": str(test_user.id), "user_id": str(test_user.id)}
        )

        response = client.get(
            "/api/v1/iam/audit-logs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    def test_get_audit_log_success(
        self, client: TestClient, iam_user, iam_token, test_org_unit, db
    ):
        """Test getting a single audit log."""
        from app.common.audit import create_audit_log

        log = create_audit_log(
            db=db,
            actor_id=iam_user.id,
            action="create",
            entity_type="org_units",
            entity_id=test_org_unit.id,
            after_json={"name": "Test Org"},
        )
        db.commit()

        response = client.get(
            f"/api/v1/iam/audit-logs/{log.id}",
            headers={"Authorization": f"Bearer {iam_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(log.id)
        assert data["action"] == "create"
        assert data["entity_type"] == "org_units"

    def test_get_audit_log_not_found(
        self, client: TestClient, iam_token
    ):
        """Test getting non-existent audit log."""
        fake_id = uuid4()
        response = client.get(
            f"/api/v1/iam/audit-logs/{fake_id}",
            headers={"Authorization": f"Bearer {iam_token}"},
        )
        assert response.status_code == 404

    def test_get_audit_log_unauthorized(self, client: TestClient, test_org_unit, db):
        """Test getting audit log without auth."""
        from app.common.audit import create_audit_log
        from app.common.models import User
        from app.auth.utils import hash_password

        # Create a user and log
        user = User(
            id=uuid4(),
            tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
            email="test@example.com",
            password_hash=hash_password("testpass123"),
            is_active=True,
        )
        db.add(user)
        db.flush()

        log = create_audit_log(
            db=db,
            actor_id=user.id,
            action="create",
            entity_type="org_units",
            entity_id=test_org_unit.id,
        )
        db.commit()

        response = client.get(f"/api/v1/iam/audit-logs/{log.id}")
        assert response.status_code == 401

    def test_get_audit_log_forbidden(
        self, client: TestClient, test_user, test_org_unit, db
    ):
        """Test getting audit log without permission."""
        from app.common.audit import create_audit_log
        from app.auth.utils import create_access_token

        log = create_audit_log(
            db=db,
            actor_id=test_user.id,
            action="create",
            entity_type="org_units",
            entity_id=test_org_unit.id,
        )
        db.commit()

        token = create_access_token(
            {"sub": str(test_user.id), "user_id": str(test_user.id)}
        )

        response = client.get(
            f"/api/v1/iam/audit-logs/{log.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

