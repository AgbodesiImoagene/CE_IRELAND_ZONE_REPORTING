"""Tests for Row-Level Security (RLS) functions."""

from __future__ import annotations

from unittest.mock import patch, MagicMock
from uuid import UUID, uuid4

import pytest

from app.core.rls import set_rls_context, clear_rls_context


class TestRLSContext:
    """Tests for RLS context setting."""

    def test_set_rls_context_with_user_and_permissions(self, db):
        """Test setting RLS context with user and permissions."""
        tenant_id = uuid4()
        user_id = uuid4()
        permissions = ["system.users.read", "system.users.create"]

        with patch("app.core.rls.settings") as mock_settings:
            mock_settings.enable_rls = True
            with patch("app.core.rls._is_postgresql", return_value=True):
                with patch.object(db, "execute") as mock_execute:
                    set_rls_context(db, tenant_id, user_id, permissions)

                    # Should execute 3 SET LOCAL statements
                    assert mock_execute.call_count == 3

    def test_set_rls_context_without_user(self, db):
        """Test setting RLS context without user."""
        tenant_id = uuid4()

        with patch("app.core.rls.settings") as mock_settings:
            mock_settings.enable_rls = True
            with patch("app.core.rls._is_postgresql", return_value=True):
                with patch.object(db, "execute") as mock_execute:
                    set_rls_context(db, tenant_id, None, None)

                    # Should execute tenant_id SET LOCAL and empty perms array
                    # (user_id is skipped when None, but perms are always set)
                    assert mock_execute.call_count == 2

    def test_set_rls_context_without_permissions(self, db):
        """Test setting RLS context without permissions."""
        tenant_id = uuid4()
        user_id = uuid4()

        with patch("app.core.rls.settings") as mock_settings:
            mock_settings.enable_rls = True
            with patch("app.core.rls._is_postgresql", return_value=True):
                with patch.object(db, "execute") as mock_execute:
                    set_rls_context(db, tenant_id, user_id, None)

                    # Should execute tenant_id and user_id SET LOCAL
                    # and empty perms array
                    assert mock_execute.call_count == 3

    def test_set_rls_context_rls_disabled(self, db):
        """Test that RLS context is not set when RLS is disabled."""
        tenant_id = uuid4()
        user_id = uuid4()

        with patch("app.core.rls.settings") as mock_settings:
            mock_settings.enable_rls = False
            with patch.object(db, "execute") as mock_execute:
                set_rls_context(db, tenant_id, user_id, ["perm1"])

                # Should not execute any SET LOCAL statements
                mock_execute.assert_not_called()

    def test_set_rls_context_sqlite(self, db):
        """Test that RLS context is not set for SQLite."""
        tenant_id = uuid4()
        user_id = uuid4()

        with patch("app.core.rls.settings") as mock_settings:
            mock_settings.enable_rls = True
            with patch("app.core.rls._is_postgresql", return_value=False):
                with patch.object(db, "execute") as mock_execute:
                    set_rls_context(db, tenant_id, user_id, ["perm1"])

                    # Should not execute any SET LOCAL statements
                    mock_execute.assert_not_called()


class TestClearRLSContext:
    """Tests for clearing RLS context."""

    def test_clear_rls_context(self, db):
        """Test clearing RLS context."""
        with patch("app.core.rls.settings") as mock_settings:
            mock_settings.enable_rls = True
            with patch("app.core.rls._is_postgresql", return_value=True):
                with patch.object(db, "execute") as mock_execute:
                    clear_rls_context(db)

                    # Should execute 3 SET LOCAL statements to clear
                    assert mock_execute.call_count == 3

    def test_clear_rls_context_rls_disabled(self, db):
        """Test that RLS context is not cleared when RLS is disabled."""
        with patch("app.core.rls.settings") as mock_settings:
            mock_settings.enable_rls = False
            with patch.object(db, "execute") as mock_execute:
                clear_rls_context(db)

                # Should not execute any SET LOCAL statements
                mock_execute.assert_not_called()

    def test_clear_rls_context_sqlite(self, db):
        """Test that RLS context is not cleared for SQLite."""
        with patch("app.core.rls.settings") as mock_settings:
            mock_settings.enable_rls = True
            with patch("app.core.rls._is_postgresql", return_value=False):
                with patch.object(db, "execute") as mock_execute:
                    clear_rls_context(db)

                    # Should not execute any SET LOCAL statements
                    mock_execute.assert_not_called()

    def test_clear_rls_context_exception_handling(self, db):
        """Test that exceptions during clearing are handled gracefully."""
        with patch("app.core.rls.settings") as mock_settings:
            mock_settings.enable_rls = True
            with patch("app.core.rls._is_postgresql", return_value=True):
                with patch.object(db, "execute", side_effect=Exception("DB error")):
                    # Should not raise exception
                    clear_rls_context(db)
