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

# Run with coverage (SQLite - fast)
make test-cov              # Standard coverage report
make test-cov-verbose      # Coverage with verbose output
make test-cov-min          # Coverage with 80% minimum threshold (fails if below)

# Run with coverage (PostgreSQL - includes RLS tests)
make test-pg-cov           # PostgreSQL with coverage (includes all tests including RLS)
make test-pg-cov-verbose   # PostgreSQL coverage with verbose output
make test-pg-cov-min       # PostgreSQL coverage with 80% minimum threshold

# Or directly via Docker
docker compose -f infra/docker-compose.yml exec api pytest -v

# Run specific test file
docker compose -f infra/docker-compose.yml exec api pytest tests/test_auth_utils.py -v
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
- `test_metrics_emission.py` - OpenTelemetry metrics emission tests
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

## Test Coverage

Coverage is automatically included when running tests via pytest. Coverage configuration is in `apps/api/.coveragerc`.

### Coverage Reports

- **Terminal**: Shows missing lines in terminal output
- **HTML**: Detailed HTML report in `apps/api/htmlcov/index.html`
- **XML**: Machine-readable report in `apps/api/coverage.xml` (for CI/CD)

### Viewing Coverage Reports

```bash
# After running test-cov, open the HTML report
# From repo root
open apps/api/htmlcov/index.html

# Or via Docker
docker compose -f infra/docker-compose.yml exec api python -m http.server 8080 -d htmlcov
# Then visit http://localhost:8080
```

### Coverage Configuration

- **Source**: `app/` directory
- **Excludes**: Tests, migrations, venv, cache files
- **Threshold**: Currently set to 0% (no failure threshold)
  - Use `make test-cov-min` or `make test-pg-cov-min` to enforce 80% minimum threshold

### Complete Coverage (Recommended)

For complete coverage including RLS tests, use PostgreSQL:
```bash
# This includes all tests, including those requiring PostgreSQL (RLS)
make test-pg-cov
```

Note: SQLite tests (`make test-cov`) are faster but skip RLS tests. For full coverage reports, use PostgreSQL.

### Improving Coverage

When adding new features:
1. Write tests for all service layer functions
2. Write tests for all API endpoints
3. Test both success and error cases
4. Run `make test-cov` to see coverage gaps
5. Add tests to cover missing lines

## Notes

- **2FA Codes**: Printed to console in dev mode; tests verify structure without capturing actual codes
- **Mocking**: SMS/email delivery services are mocked in tests
- **Logging**: Alembic migrations skip logging configuration in tests to preserve pytest caplog handlers
- **RLS**: RLS tests require PostgreSQL - SQLite tests will skip RLS functionality
- **Linter Warnings**: Some linter warnings about imports are expected (IDE may not resolve all paths)
- **Alembic**: Migrations run automatically for PostgreSQL tests to set up RLS helpers and policies
- **Coverage**: Coverage reports are generated automatically and excluded from git (see `.gitignore`)

