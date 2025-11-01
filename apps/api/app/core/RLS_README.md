# Row-Level Security (RLS) Implementation

This document explains how RLS is implemented and how to use it.

## Overview

RLS enforces data access restrictions at the database level by filtering rows based on:
- **Tenant isolation**: All queries are scoped to a single tenant
- **User permissions**: Users can only access data if they have the required permission
- **Organizational scope**: Users can only access data within their assigned organizational scope

## Database Compatibility

**Important**: RLS is PostgreSQL-specific and does **not** work with SQLite.

- **PostgreSQL**: Full RLS support with session variables and policies
- **SQLite**: RLS operations are automatically skipped (no-op). This allows tests to run with SQLite without errors, but RLS enforcement is disabled.

The RLS module automatically detects the database dialect and skips operations for non-PostgreSQL databases. This means:
- ✅ Tests can use SQLite without RLS errors
- ✅ Production uses PostgreSQL with full RLS enforcement
- ⚠️ RLS is **not enforced** when using SQLite (for testing only)

## Configuration

RLS can be toggled via the `ENABLE_RLS` environment variable (defaults to `True`):

```bash
# Disable RLS (useful for testing or development)
ENABLE_RLS=false
```

When disabled, RLS session variables are not set, allowing unrestricted access (for testing only).

## How It Works

### 1. Session Variables

When RLS is enabled, PostgreSQL session variables are set on each request:

- `app.tenant_id`: UUID of the current tenant
- `app.user_id`: UUID of the current user (NULL for unauthenticated)
- `app.perms`: Text array of permission codes for the current user

These are set using `SET LOCAL`, which means they only apply to the current transaction.

### 2. Helper Functions

Three PostgreSQL functions are created via migration:

- **`has_perm(text)`**: Checks if a permission exists in the session's `app.perms` array
- **`has_org_access(uuid)`**: Checks if the current user has access to an org unit (handles `self`, `subtree`, and `custom_set` scopes)
- **`is_descendant_org(uuid, uuid)`**: Checks if one org unit is a descendant of another (for `subtree` scope)

### 3. RLS Policies

RLS policies are created on tenant tables to filter rows. Example:

```sql
CREATE POLICY users_select_policy ON users
FOR SELECT
USING (
    tenant_id = current_setting('app.tenant_id', true)::uuid
)
```

## Usage in Code

### For Authenticated Endpoints

Use `get_db_with_rls` instead of `get_db`:

```python
from app.auth.dependencies import get_db_with_rls

@router.get("/users/me")
async def get_me(db: Session = Depends(get_db_with_rls)):
    # RLS context is automatically set
    # User can only see their own data (based on policies)
    user = db.query(User).filter(User.id == user_id).first()
    return user
```

### For Unauthenticated Endpoints

Use `get_db` directly. The default tenant_id will be set automatically:

```python
from app.common.db import get_db

@router.get("/public/data")
async def get_public_data(db: Session = Depends(get_db)):
    # Only tenant_id is set, no user/permissions
    data = db.query(PublicData).all()
    return data
```

### Manual RLS Context Setup

You can also set RLS context manually:

```python
from app.core.rls import set_rls_context
from uuid import UUID

# In your endpoint
set_rls_context(
    db=db,
    tenant_id=UUID(settings.tenant_id),
    user_id=current_user_id,
    permissions=["users.read", "users.create"]
)
```

## Adding RLS to New Tables

1. **Enable RLS on the table** (in a migration):

```python
op.execute("ALTER TABLE your_table ENABLE ROW LEVEL SECURITY")
```

2. **Create policies**:

```python
op.execute("""
    CREATE POLICY your_table_select_policy ON your_table
    FOR SELECT
    USING (
        tenant_id = current_setting('app.tenant_id', true)::uuid
        AND has_perm('your.domain.read') = true
        AND has_org_access(org_unit_id) = true
    )
""")
```

3. **Use `get_db_with_rls` in your endpoints** that query this table.

## Testing with RLS

When testing, you can:

1. **Disable RLS globally**: Set `ENABLE_RLS=false` in your test environment
2. **Set RLS context manually in tests**:

```python
from app.core.rls import set_rls_context

def test_something(db):
    set_rls_context(
        db=db,
        tenant_id=test_tenant_id,
        user_id=test_user_id,
        permissions=["test.permission"]
    )
    # Now queries will respect RLS
    result = db.query(SomeModel).all()
```

## Migration Files

- `202511011258_rls_helpers.py`: Creates helper functions
- `202511011300_rls_policies.py`: Enables RLS and creates policies on existing tables

## Notes

- RLS policies only work when RLS is enabled on the table (`ALTER TABLE ... ENABLE ROW LEVEL SECURITY`)
- Session variables are set per-transaction using `SET LOCAL`
- The `enable_rls` config flag controls whether session variables are set (doesn't disable RLS on tables)
- Policies are enforced by PostgreSQL, not by application code

