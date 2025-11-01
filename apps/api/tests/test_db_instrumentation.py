"""Tests for SQLAlchemy database instrumentation."""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

# Import to register event listeners
from app.core import db_instrumentation  # noqa: F401

from app.common.models import User
from tests.conftest import engine


class TestDatabaseInstrumentation:
    """Test SQLAlchemy event listener instrumentation."""

    def test_select_query_instrumentation(self, db: Session, caplog):
        """Test that SELECT queries emit metrics."""
        caplog.set_level(logging.INFO)
        
        with patch("app.core.db_instrumentation.emit_database_query") as mock_emit:
            # Execute a SELECT query
            stmt = select(User).limit(1)
            db.execute(stmt).fetchall()
            
            # Verify metric was emitted
            assert mock_emit.called
            call_args = mock_emit.call_args
            assert call_args[1]["operation"] == "SELECT"
            assert call_args[1]["success"] is True
            assert "duration_ms" in call_args[1]

    def test_insert_query_instrumentation(self, db: Session):
        """Test that INSERT queries emit metrics."""
        from app.core.config import settings
        from uuid import uuid4, UUID
        from app.auth.utils import hash_password
        
        with patch("app.core.db_instrumentation.emit_database_query") as mock_emit:
            # Execute an INSERT query
            user = User(
                id=uuid4(),
                tenant_id=UUID(settings.tenant_id),
                email="test@example.com",
                password_hash=hash_password("password"),
                is_active=True,
            )
            db.add(user)
            db.commit()
            
            # Verify metric was emitted
            assert mock_emit.called
            call_args = mock_emit.call_args
            assert call_args[1]["operation"] == "INSERT"
            assert call_args[1]["success"] is True

    def test_update_query_instrumentation(self, db: Session):
        """Test that UPDATE queries emit metrics."""
        from app.core.config import settings
        from uuid import uuid4, UUID
        from app.auth.utils import hash_password
        
        with patch("app.core.db_instrumentation.emit_database_query") as mock_emit:
            # Create a user first
            user = User(
                id=uuid4(),
                tenant_id=UUID(settings.tenant_id),
                email="test@example.com",
                password_hash=hash_password("password"),
                is_active=True,
            )
            db.add(user)
            db.commit()
            
            # Reset mock to count only UPDATE
            mock_emit.reset_mock()
            
            # Execute an UPDATE query
            user.is_active = False
            db.commit()
            
            # Verify metric was emitted
            assert mock_emit.called
            call_args = mock_emit.call_args
            assert call_args[1]["operation"] == "UPDATE"
            assert call_args[1]["success"] is True

    def test_delete_query_instrumentation(self, db: Session):
        """Test that DELETE queries emit metrics."""
        from app.core.config import settings
        from uuid import uuid4, UUID
        from app.auth.utils import hash_password
        
        with patch("app.core.db_instrumentation.emit_database_query") as mock_emit:
            # Create a user first
            user = User(
                id=uuid4(),
                tenant_id=UUID(settings.tenant_id),
                email="test@example.com",
                password_hash=hash_password("password"),
                is_active=True,
            )
            db.add(user)
            db.commit()
            
            # Reset mock to count only DELETE
            mock_emit.reset_mock()
            
            # Execute a DELETE query
            db.delete(user)
            db.commit()
            
            # Verify metric was emitted
            assert mock_emit.called
            call_args = mock_emit.call_args
            assert call_args[1]["operation"] == "DELETE"
            assert call_args[1]["success"] is True

    def test_query_duration_captured(self, db: Session):
        """Test that query duration is accurately measured."""
        import time
        
        with patch("app.core.db_instrumentation.emit_database_query") as mock_emit:
            # Execute a query
            stmt = select(User).limit(1)
            db.execute(stmt).fetchall()
            
            # Verify duration is a positive number
            call_args = mock_emit.call_args
            duration_ms = call_args[1]["duration_ms"]
            assert duration_ms >= 0
            assert isinstance(duration_ms, (int, float))

    def test_operation_type_detection(self, db: Session):
        """Test that operation types are correctly detected."""
        from app.core.db_instrumentation import _get_operation_type
        
        assert _get_operation_type("SELECT * FROM users") == "SELECT"
        assert _get_operation_type("INSERT INTO users VALUES (...)") == "INSERT"
        assert _get_operation_type("UPDATE users SET ...") == "UPDATE"
        assert _get_operation_type("DELETE FROM users") == "DELETE"
        assert _get_operation_type("SET LOCAL app.tenant_id = '...'") == "SET"
        assert _get_operation_type("CREATE TABLE ...") == "CREATE"
        assert _get_operation_type("UNKNOWN COMMAND") == "OTHER"

    def test_set_local_command_instrumentation(self, db: Session):
        """Test that SET LOCAL commands are instrumented."""
        # Skip for SQLite (SET LOCAL is PostgreSQL-specific)
        if "sqlite" in str(engine.url).lower():
            pytest.skip("SET LOCAL is PostgreSQL-specific")
        
        with patch("app.core.db_instrumentation.emit_database_query") as mock_emit:
            # Execute a SET LOCAL command
            db.execute(text("SET LOCAL app.tenant_id = 'test'"))
            db.commit()
            
            # Verify metric was emitted
            assert mock_emit.called
            call_args = mock_emit.call_args
            assert call_args[1]["operation"] == "SET"

    def test_query_timing_uses_perf_counter(self, db: Session):
        """Test that timing uses perf_counter for accuracy."""
        # Create a counter that increments for each call
        # This handles cases where multiple queries happen (e.g., PostgreSQL
        # migrations, RLS setup, etc.)
        call_count = [0]

        def perf_counter_side_effect():
            """Return incrementing values for perf_counter calls."""
            result = 1000.0 + (call_count[0] * 0.5)
            call_count[0] += 1
            return result

        with patch(
            "time.perf_counter", side_effect=perf_counter_side_effect
        ):
            with patch(
                "app.core.db_instrumentation.emit_database_query"
            ) as mock_emit:
                stmt = select(User).limit(1)
                db.execute(stmt).fetchall()

                # Verify perf_counter was used
                assert mock_emit.called

                # Verify duration calculation (0.5s = 500ms)
                # Find the call for our SELECT query (may be multiple calls)
                call_args_list = mock_emit.call_args_list
                # The SELECT query should have 0.5s duration (500ms)
                select_calls = [
                    call
                    for call in call_args_list
                    if call[1].get("operation") == "SELECT"
                ]
                assert (
                    len(select_calls) > 0
                ), "No SELECT query was instrumented"

                # Check that at least one SELECT call has ~500ms duration
                durations = [
                    call[1]["duration_ms"] for call in select_calls
                ]
                assert any(
                    abs(d - 500.0) < 1.0 for d in durations
                ), f"Expected ~500ms duration, got {durations}"

    def test_instrumentation_doesnt_break_queries(self, db: Session):
        """Test that instrumentation doesn't interfere with query execution."""
        from app.core.config import settings
        from uuid import uuid4, UUID
        from app.auth.utils import hash_password
        
        # Execute queries even if metrics fail
        with patch(
            "app.core.db_instrumentation.emit_database_query",
            side_effect=Exception("Metric emission failed"),
        ):
            user = User(
                id=uuid4(),
                tenant_id=UUID(settings.tenant_id),
                email="test@example.com",
                password_hash=hash_password("password"),
                is_active=True,
            )
            db.add(user)
            db.commit()  # Should succeed despite metric failure
            
            # Verify user was created
            stmt = select(User).where(User.email == "test@example.com")
            result = db.execute(stmt).scalar_one_or_none()
            assert result is not None
            assert result.email == "test@example.com"

    def test_multiple_queries_all_instrumented(self, db: Session):
        """Test that multiple queries in sequence are all instrumented."""
        from app.core.config import settings
        from uuid import uuid4, UUID
        from app.auth.utils import hash_password
        
        with patch("app.core.db_instrumentation.emit_database_query") as mock_emit:
            # Create user (INSERT)
            user = User(
                id=uuid4(),
                tenant_id=UUID(settings.tenant_id),
                email="test@example.com",
                password_hash=hash_password("password"),
                is_active=True,
            )
            db.add(user)
            db.commit()
            
            # Query user (SELECT)
            stmt = select(User).where(User.email == "test@example.com")
            db.execute(stmt).scalar_one()
            
            # Update user (UPDATE)
            user.is_active = False
            db.commit()
            
            # Delete user (DELETE)
            db.delete(user)
            db.commit()
            
            # Verify all operations were instrumented
            assert mock_emit.call_count >= 4
            operations = [
                call[1]["operation"] for call in mock_emit.call_args_list
            ]
            assert "INSERT" in operations
            assert "SELECT" in operations
            assert "UPDATE" in operations
            assert "DELETE" in operations

