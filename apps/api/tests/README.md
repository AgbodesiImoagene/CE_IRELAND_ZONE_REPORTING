# Test Suite

## Running Tests

```bash
# From repo root - SQLite (fast, default)
make test

# From repo root - PostgreSQL (for RLS testing)
make test-pg

# Verbose output
make test-verbose
make test-pg-verbose

# Or directly via Docker
docker compose -f infra/docker-compose.yml exec api pytest -v

# Run specific test file
docker compose -f infra/docker-compose.yml exec api pytest tests/test_auth_utils.py -v

# Run with coverage (when coverage is set up)
docker compose -f infra/docker-compose.yml exec api pytest --cov=app --cov-report=html
```

## Test Structure

### Authentication & Authorization
- `test_auth_utils.py` - Unit tests for password hashing, JWT, 2FA code generation
- `test_auth_service.py` - Service layer tests (authentication, sessions, user info)
- `test_auth_routes.py` - API endpoint integration tests
- `test_oauth_service.py` - OAuth service tests (identity linking, user creation)
- `test_oauth_routes.py` - OAuth endpoint tests (mocked OAuth flows)

### User Management
- `test_users_routes.py` - User management endpoint tests
- `test_users_service.py` - User service layer tests

### Observability
- `test_middleware.py` - Middleware tests (request ID, security headers, logging, rate limiting)
- `test_db_instrumentation.py` - Database query instrumentation tests
- `test_redis_instrumentation.py` - Redis operation instrumentation tests
- `test_metrics_emission.py` - EMF metrics emission tests
- `test_instrumentation_integration.py` - End-to-end instrumentation tests

### Background Jobs
- `test_jobs.py` - Background job processing tests

### Database & Security
- `test_rls.py` - Row-Level Security tests (PostgreSQL only)

### Utilities
- `test_seed_permissions.py` - Permission seeding script tests
- `conftest.py` - Shared fixtures (db, client, test users, etc.)

## Test Database

### SQLite (Default)
- **Use case**: Fast unit tests, general testing
- **Setup**: In-memory SQLite database
- **Benefits**: Fast, no external dependencies
- **Limitations**: No RLS support (tests using RLS require PostgreSQL)

Each test gets a fresh in-memory database instance. Tables are dropped and recreated between tests.

### PostgreSQL (Optional)
- **Use case**: RLS testing, production-like behavior
- **Setup**: Set `USE_POSTGRES=true` environment variable
- **Database**: Uses `POSTGRES_TEST_URL` (default: `postgresql+psycopg://app:app@localhost:5432/test_app`)
- **Benefits**: Full RLS support, production-like testing
- **Setup**: Tables are truncated (not dropped) between tests to preserve RLS policies

**Note**: The test database must be created manually before running PostgreSQL tests:
```bash
# Create test database
docker compose -f infra/docker-compose.yml exec db psql -U app -d postgres -c "CREATE DATABASE test_app;"
```

### Switching Between Databases

Tests automatically use SQLite by default. To use PostgreSQL:

```bash
# Via Makefile
make test-pg

# Via environment variable
USE_POSTGRES=true POSTGRES_TEST_URL=postgresql+psycopg://app:app@db:5432/test_app \
  docker compose -f infra/docker-compose.yml exec api pytest
```

## Test Fixtures

Available in `conftest.py`:

- `db` - Database session (SQLite or PostgreSQL based on `USE_POSTGRES`)
- `client` - FastAPI TestClient with dependency overrides
- `tenant_id` - Fixed tenant UUID for tests
- `test_org_unit` - Test org unit (church)
- `test_role` - Test role
- `test_permission` - Test permission
- `test_user` - Test user with role assignment
- `admin_role` - Admin role with permissions
- `admin_user` - Admin user
- `authenticated_user_token` - JWT access token for test user
- `admin_token` - JWT access token for admin user

## Notes

- **2FA Codes**: Printed to console in dev mode; tests verify structure without capturing actual codes
- **Mocking**: SMS/email delivery services are mocked in tests
- **Logging**: Alembic migrations skip logging configuration in tests to preserve pytest caplog handlers
- **RLS**: RLS tests require PostgreSQL - SQLite tests will skip RLS functionality
- **Linter Warnings**: Some linter warnings about imports are expected (IDE may not resolve all paths)
- **Alembic**: Migrations run automatically for PostgreSQL tests to set up RLS helpers and policies

