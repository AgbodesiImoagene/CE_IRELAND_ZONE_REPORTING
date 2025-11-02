# Development Guide

## Getting Started

### Setup

1. **Clone and start services**
   ```bash
   make up
   ```

2. **Run migrations**
   ```bash
   make migrate
   ```

3. **Seed initial data**
   ```bash
   make seed
   ```

### Environment Setup

Create a `.env` file in the repository root. See main README for required variables.

## Development Workflow

### Code Formatting

This project uses [Black](https://github.com/psf/black) for code formatting.

```bash
# Format code (local)
make format

# Check formatting
make format-check

# Format in Docker
make format-docker
```

Configuration is in `pyproject.toml`:
- Line length: 79 characters
- Preview features enabled
- Python 3.11+ target

### Running Tests

```bash
# SQLite tests (fast)
make test

# PostgreSQL tests (RLS testing)
make test-pg

# Verbose output
make test-verbose
```

### Database Migrations

```bash
# Create new migration
docker compose -f infra/docker-compose.yml exec api alembic revision --autogenerate -m "description"

# Apply migrations
make migrate

# Rollback
docker compose -f infra/docker-compose.yml exec api alembic downgrade -1
```

### API Development

- **API Server**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

The API automatically reloads on code changes (hot reload enabled).

### Background Workers

```bash
# Start worker
make worker

# Or manually
docker compose -f infra/docker-compose.yml exec worker python -m app.jobs.cli emails sms
```

Workers process:
- Email notifications
- SMS notifications (when configured)
- Outbox notifications
- Future: imports, exports, summaries

## Architecture Decisions

### Row-Level Security (RLS)

RLS is implemented at the database level for tenant and scope isolation. See [RLS_README.md](../apps/api/app/core/RLS_README.md) for details.

**Key Points**:
- PostgreSQL-specific (SQLite tests skip RLS)
- Session variables set per transaction
- Policies enforce tenant + permission + scope checks
- Use `get_db_with_rls` dependency for authenticated endpoints

### Observability

The platform uses:
- **Structured JSON Logging**: CloudWatch-compatible format
- **AWS EMF Metrics**: Embedded metrics in logs for CloudWatch
- **Instrumentation**: Automatic timing for DB queries and Redis ops
- **Error Tracking**: Global exception handlers with correlation IDs

Metrics are emitted automatically via:
- SQLAlchemy event listeners (database queries)
- Redis client wrapper (Redis operations)
- Middleware (HTTP requests/responses)

### Background Jobs

Uses RQ (Redis Queue) for simplicity and reliability:
- Separate queues per job type
- Outbox pattern for guaranteed delivery
- Retry logic built-in
- Simple monitoring via RQ dashboard

## Adding New Features

### 1. Database Changes

1. Update models in `app/common/models.py`
2. Create migration: `alembic revision --autogenerate -m "description"`
3. Review migration file
4. Apply: `make migrate`

### 2. New API Endpoints

1. Create router in appropriate module (e.g., `app/users/routes.py`)
2. Add schemas in `schemas.py`
3. Implement service logic in `service.py`
4. Use `get_db_with_rls` for authenticated endpoints
5. Add tests in `tests/`

### 3. Background Jobs

1. Define task in `app/jobs/tasks.py`
2. Add queue configuration in `app/jobs/queue.py` if needed
3. Enqueue via helper functions or directly
4. Add tests

### 4. RLS Policies

For new tenant tables:
1. Enable RLS in migration: `ALTER TABLE ... ENABLE ROW LEVEL SECURITY`
2. Create policies in migration (see RLS_README.md)
3. Use `get_db_with_rls` dependency
4. Test with PostgreSQL

## Testing Guidelines

### Unit Tests
- Test business logic in isolation
- Mock external dependencies
- Use SQLite for speed

### Integration Tests
- Test API endpoints end-to-end
- Use real database (SQLite or PostgreSQL)
- Test authentication/authorization

### RLS Tests
- Use PostgreSQL (`make test-pg`)
- Test with different user scopes
- Verify tenant isolation

## Code Organization

```
app/
├── auth/          # Authentication, 2FA, OAuth, sessions
├── common/        # Shared models, database setup
├── core/          # Middleware, metrics, errors, RLS, instrumentation
├── jobs/          # Background job processing
├── users/         # User management, invitations
└── main.py        # FastAPI app setup
```

Follow this structure when adding new modules.

## Debugging

### Logs

```bash
# API logs
make logs

# All services
docker compose -f infra/docker-compose.yml logs -f
```

### Database Access

```bash
# PostgreSQL shell
docker compose -f infra/docker-compose.yml exec db psql -U app -d app

# Redis CLI
docker compose -f infra/docker-compose.yml exec redis redis-cli
```

### API Shell

```bash
make api-shell
```

## Performance Considerations

- **Database Queries**: All queries are instrumented automatically
- **Redis Operations**: All Redis ops are timed and logged
- **Connection Pooling**: PostgreSQL connection pool configured
- **Rate Limiting**: Optional middleware available (disabled by default)

## Security Best Practices

- Always use `get_db_with_rls` for authenticated endpoints
- Set appropriate RLS policies for new tables
- Validate user permissions in service layer
- Use parameterized queries (SQLAlchemy handles this)
- Never expose sensitive data in logs (redaction implemented)
- Use environment variables for secrets (not committed)

## Future Improvements

See main README roadmap for planned features:
- Test coverage reporting
- Additional backend modules (Registry, Finance, Cells, Reports)
- Frontend applications
- Production infrastructure

