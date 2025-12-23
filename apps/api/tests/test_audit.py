"""Tests for audit logging utilities."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from app.common.audit import create_audit_log
from app.common.models import AuditLog


class TestCreateAuditLog:
    """Test audit log creation."""

    def test_create_audit_log_minimal(self, db: Session, tenant_id: str):
        """Test creating audit log with minimal data."""
        actor_id = uuid4()

        audit_log = create_audit_log(
            db=db,
            actor_id=actor_id,
            action="test_action",
        )

        assert audit_log is not None
        assert audit_log.actor_id == actor_id
        assert audit_log.action == "test_action"
        assert audit_log.tenant_id == UUID(tenant_id)
        assert audit_log.entity_type is None
        assert audit_log.entity_id is None
        assert audit_log.before_json is None
        assert audit_log.after_json is None
        assert audit_log.ip is None
        assert audit_log.user_agent is None

        # Verify it was added to database
        db.refresh(audit_log)
        assert audit_log.id is not None

    def test_create_audit_log_full_data(self, db: Session, tenant_id: str):
        """Test creating audit log with all data."""
        actor_id = uuid4()
        entity_id = uuid4()
        before_data = {"name": "Old Name"}
        after_data = {"name": "New Name"}

        audit_log = create_audit_log(
            db=db,
            actor_id=actor_id,
            action="update",
            entity_type="people",
            entity_id=entity_id,
            before_json=before_data,
            after_json=after_data,
            ip="192.168.1.1",
            user_agent="Mozilla/5.0",
        )

        assert audit_log.actor_id == actor_id
        assert audit_log.action == "update"
        assert audit_log.entity_type == "people"
        assert audit_log.entity_id == entity_id
        assert audit_log.before_json == before_data
        assert audit_log.after_json == after_data
        assert audit_log.ip == "192.168.1.1"
        assert audit_log.user_agent == "Mozilla/5.0"
        assert audit_log.tenant_id == UUID(tenant_id)

    def test_create_audit_log_no_actor(self, db: Session, tenant_id: str):
        """Test creating audit log without actor (system action)."""
        audit_log = create_audit_log(
            db=db,
            actor_id=None,
            action="system.maintenance",
        )

        assert audit_log.actor_id is None
        assert audit_log.action == "system.maintenance"
        assert audit_log.tenant_id == UUID(tenant_id)

    def test_create_audit_log_with_entity_only(self, db: Session, tenant_id: str):
        """Test creating audit log with entity info only."""
        entity_id = uuid4()

        audit_log = create_audit_log(
            db=db,
            actor_id=uuid4(),
            action="delete",
            entity_type="people",
            entity_id=entity_id,
        )

        assert audit_log.entity_type == "people"
        assert audit_log.entity_id == entity_id
        assert audit_log.before_json is None
        assert audit_log.after_json is None

    def test_create_audit_log_with_json_only(self, db: Session, tenant_id: str):
        """Test creating audit log with JSON snapshots only."""
        before_data = {"field": "old_value"}
        after_data = {"field": "new_value"}

        audit_log = create_audit_log(
            db=db,
            actor_id=uuid4(),
            action="update",
            before_json=before_data,
            after_json=after_data,
        )

        assert audit_log.before_json == before_data
        assert audit_log.after_json == after_data
        assert audit_log.entity_type is None
        assert audit_log.entity_id is None

    def test_create_audit_log_with_request_info(self, db: Session, tenant_id: str):
        """Test creating audit log with IP and user agent."""
        audit_log = create_audit_log(
            db=db,
            actor_id=uuid4(),
            action="login",
            ip="10.0.0.1",
            user_agent="Mozilla/5.0 (Windows NT 10.0)",
        )

        assert audit_log.ip == "10.0.0.1"
        assert audit_log.user_agent == "Mozilla/5.0 (Windows NT 10.0)"
        assert audit_log.tenant_id == UUID(tenant_id)

    def test_create_audit_log_persists_to_db(self, db: Session, tenant_id: str):
        """Test that audit log is persisted to database."""
        actor_id = uuid4()
        action = "test_persist"

        audit_log = create_audit_log(
            db=db,
            actor_id=actor_id,
            action=action,
        )

        # Commit to ensure it's persisted
        db.commit()

        # Query from database
        retrieved = db.query(AuditLog).filter_by(id=audit_log.id).first()

        assert retrieved is not None
        assert retrieved.actor_id == actor_id
        assert retrieved.action == action
        assert retrieved.tenant_id == UUID(tenant_id)

