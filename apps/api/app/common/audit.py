"""Audit logging utility functions."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.common.models import AuditLog
from app.core.config import settings


def create_audit_log(
    db: Session,
    actor_id: Optional[UUID],
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[UUID] = None,
    before_json: Optional[dict] = None,
    after_json: Optional[dict] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditLog:
    """
    Create an audit log entry.

    Args:
        db: Database session
        actor_id: ID of the user performing the action
        action: Action being performed (e.g., "create", "update", "delete")
        entity_type: Type of entity (e.g., "people", "first_timers")
        entity_id: ID of the entity being acted upon
        before_json: JSON snapshot of entity before the action
        after_json: JSON snapshot of entity after the action
        ip: IP address of the request
        user_agent: User agent string of the request

    Returns:
        Created AuditLog instance
    """
    tenant_id = UUID(settings.tenant_id)

    audit_log = AuditLog(
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_json=before_json,
        after_json=after_json,
        ip=ip,
        user_agent=user_agent,
    )

    db.add(audit_log)
    db.flush()
    return audit_log

