"""Tests for Row-Level Security (RLS) functionality."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.common.models import User
from app.core.config import settings
from app.core.rls import _is_postgresql, clear_rls_context, set_rls_context

from tests.conftest import USE_POSTGRES


class TestRLSDatabaseDetection:
    """Test RLS database dialect detection."""

    def test_is_postgresql_detects_sqlite(self, db: Session):
        """Test that SQLite is correctly detected."""
        # Tests can use SQLite or PostgreSQL
        assert _is_postgresql(db) is USE_POSTGRES

    def test_is_postgresql_handles_no_bind(self):
        """Test that missing bind is handled gracefully."""

        # Create a mock session without bind
        class MockSession:
            pass

        mock_db = MockSession()
        assert _is_postgresql(mock_db) is False


class TestRLSContextSetting:
    """Test RLS context setting and clearing."""

    def test_set_rls_context_with_user_and_permissions(
        self, db: Session, tenant_id: str
    ):
        """Test setting RLS context with user ID and permissions."""
        user_id = uuid4()
        tenant_uuid = UUID(tenant_id)
        permissions = ["users.read", "users.create"]

        # Should not raise (SQLite will skip the actual SQL)
        set_rls_context(
            db=db,
            tenant_id=tenant_uuid,
            user_id=user_id,
            permissions=permissions,
        )

        # Verify no errors occurred (for SQLite, operations are skipped)
        assert True

    def test_set_rls_context_without_user(self, db: Session, tenant_id: str):
        """Test setting RLS context without user ID (unauthenticated)."""
        tenant_uuid = UUID(tenant_id)

        # Should not raise
        set_rls_context(
            db=db,
            tenant_id=tenant_uuid,
            user_id=None,
            permissions=None,
        )

        assert True

    def test_set_rls_context_without_permissions(self, db: Session, tenant_id: str):
        """Test setting RLS context without permissions."""
        user_id = uuid4()
        tenant_uuid = UUID(tenant_id)

        set_rls_context(
            db=db,
            tenant_id=tenant_uuid,
            user_id=user_id,
            permissions=None,
        )

        assert True

    def test_clear_rls_context(self, db: Session):
        """Test clearing RLS context."""
        # Should not raise
        clear_rls_context(db)

        assert True

    def test_rls_context_disabled_when_flag_off(
        self, db: Session, tenant_id: str, monkeypatch
    ):
        """Test that RLS operations are skipped when enable_rls is False."""
        user_id = uuid4()
        tenant_uuid = UUID(tenant_id)

        # Disable RLS
        original_value = settings.enable_rls
        monkeypatch.setattr(settings, "enable_rls", False)

        try:
            # Should complete without errors (operations skipped)
            set_rls_context(
                db=db,
                tenant_id=tenant_uuid,
                user_id=user_id,
                permissions=["test.permission"],
            )

            clear_rls_context(db)
        finally:
            monkeypatch.setattr(settings, "enable_rls", original_value)

        assert True


class TestRLSIntegration:
    """Test RLS integration with database queries (note: actual enforcement requires PostgreSQL)."""

    def test_rls_context_with_query(self, db: Session, tenant_id: str, test_user):
        """Test that setting RLS context doesn't break queries."""
        tenant_uuid = UUID(tenant_id)

        # Set RLS context
        set_rls_context(
            db=db,
            tenant_id=tenant_uuid,
            user_id=test_user.id,
            permissions=["users.read"],
        )

        # Query should still work (RLS not enforced in SQLite)
        user = db.get(User, test_user.id)
        assert user is not None
        assert user.email == test_user.email

    def test_rls_context_does_not_break_operations(self, db: Session, tenant_id: str):
        """Test that RLS context setting doesn't interfere with database operations."""
        tenant_uuid = UUID(tenant_id)
        user_id = uuid4()

        # Set context
        set_rls_context(
            db=db,
            tenant_id=tenant_uuid,
            user_id=user_id,
            permissions=["test.permission"],
        )

        # Database operations should still work
        user = User(
            id=user_id,
            tenant_id=tenant_uuid,
            email="test@example.com",
        )
        db.add(user)
        db.commit()

        # Query should work
        found = db.get(User, user_id)
        assert found is not None
        assert found.email == "test@example.com"

        # Clear context
        clear_rls_context(db)

        # Should still work after clearing
        found_after = db.get(User, user_id)
        assert found_after is not None

    def test_set_rls_context_with_empty_permissions(self, db: Session, tenant_id: str):
        """Test setting RLS context with empty permissions list."""
        tenant_uuid = UUID(tenant_id)
        user_id = uuid4()

        set_rls_context(
            db=db,
            tenant_id=tenant_uuid,
            user_id=user_id,
            permissions=[],
        )

        assert True

    def test_clear_rls_context_handles_errors(self, db: Session, monkeypatch):
        """Test that clear_rls_context handles errors gracefully."""
        from unittest.mock import Mock, patch

        # Mock execute to raise an error
        with patch.object(db, "execute", side_effect=Exception("DB error")):
            # Should not raise, should handle error gracefully
            from app.core.rls import clear_rls_context
            clear_rls_context(db)

        assert True

    def test_is_postgresql_handles_attribute_error(self):
        """Test that _is_postgresql handles AttributeError gracefully."""
        from app.core.rls import _is_postgresql

        # Create a mock session that raises AttributeError
        class MockSession:
            @property
            def bind(self):
                raise AttributeError("No bind")

        mock_db = MockSession()
        result = _is_postgresql(mock_db)
        assert result is False

    def test_is_postgresql_handles_type_error(self):
        """Test that _is_postgresql handles TypeError gracefully."""
        from app.core.rls import _is_postgresql

        # Create a mock session that raises TypeError
        class MockSession:
            @property
            def bind(self):
                raise TypeError("Type error")

        mock_db = MockSession()
        result = _is_postgresql(mock_db)
        assert result is False

    def test_set_rls_context_with_special_characters_in_permissions(
        self, db: Session, tenant_id: str
    ):
        """Test setting RLS context with special characters in permissions."""
        tenant_uuid = UUID(tenant_id)
        user_id = uuid4()
        permissions = ["test.permission", "another_permission", "permission-with-dash"]

        set_rls_context(
            db=db,
            tenant_id=tenant_uuid,
            user_id=user_id,
            permissions=permissions,
        )

        assert True
