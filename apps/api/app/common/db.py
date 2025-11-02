from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
import os

from app.core.config import settings

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql+psycopg://app:app@db:5432/app")

engine = create_engine(POSTGRES_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

# Import database instrumentation to register event listeners
# This automatically instruments all queries on this engine
try:
    from app.core import db_instrumentation  # noqa: F401
except ImportError:
    # Instrumentation not available, skip
    pass


def _is_postgresql_connection(connection) -> bool:
    """Check if the connection is to PostgreSQL."""
    try:
        return connection.dialect.name == "postgresql"
    except (AttributeError, TypeError):
        return False


@event.listens_for(Session, "after_begin")
def set_rls_defaults(session, transaction, connection):  # noqa: ARG001
    """
    Set default RLS session variables when a transaction begins.

    This ensures RLS variables are set even if not explicitly set by middleware.
    For unauthenticated/public endpoints, only tenant_id is set.

    Note:
        This is a no-op for non-PostgreSQL databases (e.g., SQLite).
        RLS is PostgreSQL-specific and not supported in SQLite.
    """
    if not settings.enable_rls:
        return

    # Skip RLS operations for non-PostgreSQL databases (e.g., SQLite)
    if not _is_postgresql_connection(connection):
        return

    # Set default tenant_id (can be overridden by middleware)
    tenant_id_str = str(settings.tenant_id)
    connection.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id_str}'"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
