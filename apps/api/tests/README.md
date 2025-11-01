# Test Suite

## Running Tests

```bash
# From repo root
make test

# Or directly
docker compose -f infra/docker-compose.yml exec api pytest -v

# Run specific test file
docker compose -f infra/docker-compose.yml exec api pytest tests/test_auth_utils.py -v

# Run with coverage
docker compose -f infra/docker-compose.yml exec api pytest --cov=app --cov-report=html
```

## Test Structure

- `test_auth_utils.py` - Unit tests for password hashing, JWT, 2FA code generation
- `test_auth_service.py` - Service layer tests (authentication, sessions, user info)
- `test_auth_routes.py` - API endpoint integration tests
- `test_oauth_service.py` - OAuth service tests (identity linking, user creation)
- `test_oauth_routes.py` - OAuth endpoint tests (mocked OAuth flows)
- `conftest.py` - Shared fixtures (db, client, test users, etc.)

## Test Database

Tests use in-memory SQLite for speed. Each test gets a fresh database instance.

## Notes

- 2FA codes are printed to console in dev mode; in tests we verify structure without capturing actual codes
- Mock delivery services for SMS/email in production tests
- Some linter warnings about imports are expected (IDE may not resolve all paths)

