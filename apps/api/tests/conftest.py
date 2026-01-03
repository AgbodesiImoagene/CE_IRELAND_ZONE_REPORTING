from __future__ import annotations

from typing import Generator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.common.models import (
    Base,
    User,
    Role,
    Permission,
    OrgUnit,
    OrgAssignment,
)
from app.auth.utils import hash_password
import os

# Support optional PostgreSQL testing for RLS tests
# Default to SQLite for speed, use POSTGRES_TEST_URL env var for PostgreSQL
USE_POSTGRES = os.getenv("USE_POSTGRES", "false").lower() == "true"
POSTGRES_TEST_URL = os.getenv(
    "POSTGRES_TEST_URL",
    "postgresql+psycopg://app:app@localhost:5432/test_app",
)

if USE_POSTGRES:
    # Use PostgreSQL for RLS testing
    TEST_DB_URL = POSTGRES_TEST_URL
    engine = create_engine(TEST_DB_URL, pool_pre_ping=True)
else:
    # Use in-memory SQLite for tests (faster than Postgres for unit tests)
    TEST_DB_URL = "sqlite:///:memory:"
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _truncate_all_tables(db: Session) -> None:
    """Truncate all tables in PostgreSQL to ensure clean test state.

    Uses CASCADE to handle foreign key constraints automatically.
    Temporarily disables RLS triggers during truncation.
    """
    if not USE_POSTGRES:
        return  # SQLite handles cleanup differently

    # Get all table names from metadata
    tables = list(Base.metadata.tables.keys())

    if not tables:
        return

    try:
        # Temporarily disable RLS triggers to allow truncation
        # This is safe because we're in a test environment
        db.execute(text("SET session_replication_role = 'replica';"))

        # Build TRUNCATE command with all tables and CASCADE
        # CASCADE handles foreign key dependencies automatically
        table_names = ", ".join(f'"{table}"' for table in tables)
        db.execute(text(f"TRUNCATE TABLE {table_names} " "RESTART IDENTITY CASCADE;"))

        # Re-enable triggers
        db.execute(text("SET session_replication_role = 'origin';"))
        db.commit()
    except Exception as e:
        db.rollback()
        # If bulk truncation fails, log error but don't fail test
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            f"Failed to truncate tables: {e}. "
            "Database may contain leftover test data."
        )


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """
    Create a fresh database for each test with proper cleanup.

    Supports both SQLite (default) and PostgreSQL (for RLS testing).
    Set USE_POSTGRES=true and POSTGRES_TEST_URL to use PostgreSQL.

    For PostgreSQL:
    - Truncates all tables after each test to ensure clean state
    - Uses CASCADE to handle foreign key constraints
    - Temporarily disables RLS triggers during truncation

    For SQLite:
    - Drops and recreates tables after each test (in-memory database)
    """
    if USE_POSTGRES:
        # For PostgreSQL, create tables and set up RLS
        try:
            # Create all tables
            Base.metadata.create_all(bind=engine)
            # Run migrations for RLS setup (helpers and policies)
            # Note: Alembic config is set up in conftest or via env
            from alembic.config import Config
            from alembic import command
            from unittest.mock import patch

            alembic_cfg = Config("alembic.ini")
            # Set the database URL for migrations
            alembic_cfg.set_main_option("sqlalchemy.url", POSTGRES_TEST_URL)

            # Prevent Alembic from reconfiguring logging during migrations
            # This preserves pytest's caplog handlers
            with patch("logging.config.fileConfig"):
                # Run migrations
                command.upgrade(alembic_cfg, "head")
        except Exception as e:
            # If migrations fail, still try to create tables directly
            try:
                Base.metadata.create_all(bind=engine)
            except Exception as inner_e:
                raise RuntimeError(
                    f"Failed to create PostgreSQL tables: {inner_e}"
                ) from e

        # For PostgreSQL, use regular session and truncate after each test
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            # Always truncate all tables after test to ensure clean state
            # This happens even if test fails
            try:
                _truncate_all_tables(db)
            except Exception:
                # If truncation fails, try with a fresh connection
                try:
                    db.close()
                except Exception:
                    pass
                try:
                    fresh_conn = engine.connect()
                    fresh_db = Session(bind=fresh_conn)
                    _truncate_all_tables(fresh_db)
                    fresh_db.close()
                    fresh_conn.close()
                except Exception:
                    # Log but don't fail - cleanup will happen next test
                    pass
            finally:
                # Always close the session
                try:
                    db.close()
                except Exception:
                    pass
    else:
        # SQLite: SQLAlchemy will automatically convert PostgreSQL ENUMs to
        # VARCHAR for SQLite. Uuid types should work as SQLAlchemy 2.0 handles
        # cross-platform types.
        try:
            Base.metadata.create_all(bind=engine)
        except Exception as e:
            raise RuntimeError(f"Failed to create tables: {e}") from e

        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
            # Drop and recreate tables for SQLite (in-memory, so this is fast)
            Base.metadata.drop_all(bind=engine)
            Base.metadata.create_all(bind=engine)


@pytest.fixture
def client(db: Session, tenant_id: str, monkeypatch) -> Generator[TestClient, None, None]:
    """Create a test client with dependency overrides."""
    # Set settings.tenant_id for tests
    from app.core.config import settings
    monkeypatch.setattr(settings, "tenant_id", tenant_id)

    def get_test_db():
        yield db

    from app.common.db import get_db

    app.dependency_overrides[get_db] = get_test_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def tenant_id() -> str:
    """Return a valid UUID string for testing."""
    # Use a fixed UUID for consistency across tests
    return "12345678-1234-5678-1234-567812345678"


@pytest.fixture
def test_org_unit(db: Session, tenant_id: str) -> OrgUnit:
    """Create a test org unit (church)."""
    org = OrgUnit(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        name="Test Church",
        type="church",
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@pytest.fixture
def test_role(db: Session, tenant_id: str) -> Role:
    """Create a test role."""
    role = Role(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        name="Test Role",
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


@pytest.fixture
def test_permission(db: Session) -> Permission:
    """Create a test permission."""
    perm = Permission(
        id=uuid4(),
        code="test.permission",
        description="Test permission",
    )
    db.add(perm)
    db.commit()
    db.refresh(perm)
    return perm


@pytest.fixture
def test_user(
    db: Session, tenant_id: str, test_role: Role, test_org_unit: OrgUnit
) -> User:
    """Create a test user with role assignment."""
    user = User(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        email="test@example.com",
        password_hash=hash_password("testpass123"),
        is_active=True,
        is_2fa_enabled=False,
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
def admin_role(db: Session, tenant_id: str) -> Role:
    """Create an admin role with user management permissions."""
    from app.common.models import Permission, RolePermission

    role = Role(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        name="Admin Role",
    )
    db.add(role)
    db.flush()

    # Create permissions
    permissions = [
        Permission(
            id=uuid4(),
            code="system.users.create",
            description="Create users",
        ),
        Permission(
            id=uuid4(),
            code="system.users.read",
            description="Read users",
        ),
        Permission(
            id=uuid4(),
            code="system.users.update",
            description="Update users",
        ),
        Permission(
            id=uuid4(),
            code="system.users.disable",
            description="Disable/enable users",
        ),
        Permission(
            id=uuid4(),
            code="system.users.reset_password",
            description="Reset user passwords",
        ),
        Permission(
            id=uuid4(),
            code="system.users.assign",
            description="Assign org scopes",
        ),
        Permission(
            id=uuid4(),
            code="system.audit.view",
            description="View audit logs",
        ),
    ]

    for perm in permissions:
        db.add(perm)
    db.flush()

    # Link permissions to role
    for perm in permissions:
        role_perm = RolePermission(
            role_id=role.id,
            permission_id=perm.id,
        )
        db.add(role_perm)

    db.commit()
    db.refresh(role)
    return role


@pytest.fixture
def admin_user(
    db: Session, tenant_id: str, admin_role: Role, test_org_unit: OrgUnit
) -> User:
    """Create an admin user with system.users.create permission."""
    user = User(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        email="admin@example.com",
        password_hash=hash_password("adminpass123"),
        is_active=True,
        is_2fa_enabled=False,
    )
    db.add(user)
    db.flush()

    assignment = OrgAssignment(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        user_id=user.id,
        org_unit_id=test_org_unit.id,
        role_id=admin_role.id,
        scope_type="self",
    )
    db.add(assignment)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def authenticated_user_token(test_user: User) -> str:
    """Login and return access token (bypasses 2FA for testing)."""
    # For testing, we'll create a session directly or use a test helper
    # In real flow, this would go through login -> 2FA -> tokens
    from app.auth.utils import create_access_token

    return create_access_token({"sub": str(test_user.id), "user_id": str(test_user.id)})


@pytest.fixture
def admin_token(admin_user: User) -> str:
    """Return access token for admin user."""
    from app.auth.utils import create_access_token

    return create_access_token(
        {"sub": str(admin_user.id), "user_id": str(admin_user.id)}
    )


@pytest.fixture
def iam_user(db, tenant_id, test_org_unit):
    """Create a user with IAM permissions."""
    from app.common.models import Permission, RolePermission, Role, OrgAssignment
    from app.auth.utils import hash_password

    # Create IAM permissions
    permissions = [
        Permission(
            id=uuid4(),
            code="system.org_units.read",
            description="Read org units",
        ),
        Permission(
            id=uuid4(),
            code="system.org_units.create",
            description="Create org units",
        ),
        Permission(
            id=uuid4(),
            code="system.org_units.update",
            description="Update org units",
        ),
        Permission(
            id=uuid4(),
            code="system.org_units.delete",
            description="Delete org units",
        ),
        Permission(
            id=uuid4(),
            code="system.roles.read",
            description="Read roles",
        ),
        Permission(
            id=uuid4(),
            code="system.roles.create",
            description="Create roles",
        ),
        Permission(
            id=uuid4(),
            code="system.roles.update",
            description="Update roles",
        ),
        Permission(
            id=uuid4(),
            code="system.roles.delete",
            description="Delete roles",
        ),
        Permission(
            id=uuid4(),
            code="system.permissions.read",
            description="Read permissions",
        ),
        Permission(
            id=uuid4(),
            code="system.roles.assign",
            description="Assign permissions to roles",
        ),
        Permission(
            id=uuid4(),
            code="system.audit.view",
            description="View audit logs",
        ),
    ]

    for perm in permissions:
        db.add(perm)
    db.flush()

    # Create IAM role
    iam_role = Role(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        name="IAM Role",
    )
    db.add(iam_role)
    db.flush()

    # Assign all permissions to role
    for perm in permissions:
        role_perm = RolePermission(
            role_id=iam_role.id,
            permission_id=perm.id,
        )
        db.add(role_perm)

    # Create user
    user = User(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        email="iam@example.com",
        password_hash=hash_password("testpass123"),
        is_active=True,
        is_2fa_enabled=False,
    )
    db.add(user)
    db.flush()

    # Assign role to user
    assignment = OrgAssignment(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        user_id=user.id,
        org_unit_id=test_org_unit.id,
        role_id=iam_role.id,
        scope_type="self",
    )
    db.add(assignment)
    db.commit()
    db.refresh(user)

    return user


@pytest.fixture
def iam_token(iam_user):
    """Return access token for IAM user."""
    from app.auth.utils import create_access_token

    return create_access_token(
        {"sub": str(iam_user.id), "user_id": str(iam_user.id)}
    )
