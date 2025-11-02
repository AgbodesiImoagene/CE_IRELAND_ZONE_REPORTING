# CE Ireland Zone Church Reporting Platform

A unified backend platform for managing church operations across Registry, Finance, Cells, and Reports portals. Built with FastAPI, PostgreSQL, and designed for multi-tenant, hierarchical access control.

## 🎯 Project Overview

The CE Ireland Zone Church Reporting Platform replaces fragmented spreadsheets with a secure, centralized system for:

- **Member & First-Timer Management** (Registry Portal)
- **Financial Records** (Finance Portal) - offerings, tithes, partnerships
- **Cell Ministry Reporting** (Cells Portal)
- **Zone-wide Dashboards & Analytics** (Reports Portal)

Each portal operates on its own subdomain (`registry.zone.ce.church`, `finance.zone.ce.church`, etc.) and connects to this unified backend API.

## 🏗️ Architecture

### Technology Stack

- **Backend Framework**: FastAPI (Python 3.12)
- **Database**: PostgreSQL 15+ with Row-Level Security (RLS)
- **Cache/Queue**: Redis
- **Object Storage**: MinIO (S3-compatible, for exports/receipts)
- **Background Jobs**: RQ (Redis Queue)
- **Database Migrations**: Alembic
- **Code Formatting**: Black

### Project Structure

```
ce_ireland_zone_reporting/
├── apps/
│   └── api/                    # FastAPI backend application
│       ├── app/
│       │   ├── auth/           # Authentication, 2FA, OAuth SSO
│       │   ├── common/         # Shared models, database setup
│       │   ├── core/           # Middleware, metrics, errors, RLS
│       │   ├── jobs/           # Background job processing (RQ)
│       │   ├── users/          # User management, invitations
│       │   └── main.py         # FastAPI app entry point
│       ├── alembic/            # Database migrations
│       ├── tests/              # Test suite
│       └── requirements.txt    # Production dependencies
├── docs/                       # Product requirements, architecture docs
├── infra/                      # Infrastructure as code
│   └── docker-compose.yml     # Local development environment
├── Makefile                   # Development commands
└── pyproject.toml            # Black formatting config
```

## ✨ Features

### ✅ Implemented

- **Authentication & Authorization**
  - Email/password authentication with 2FA (SMS/Email)
  - OAuth SSO (Google, Facebook)
  - JWT-based session management (access + refresh tokens)
  - Role-Based Access Control (RBAC) with organizational scopes
  - Top-down user provisioning (Zonal Pastor → Group Pastor → Church Pastor → Coordinators)

- **Database & Security**
  - PostgreSQL Row-Level Security (RLS) for tenant and scope isolation
  - Alembic migrations with autogenerate
  - IAM models (Users, Roles, Permissions, OrgUnits, Assignments)
  - Audit logging

- **Background Jobs**
  - RQ (Redis Queue) for asynchronous email/SMS delivery
  - Outbox pattern for reliable notification delivery
  - Separate queues per job type (emails, sms, imports, exports)

- **Observability**
  - Structured JSON logging (CloudWatch-compatible)
  - AWS Embedded Metric Format (EMF) for metrics
  - Database query instrumentation
  - Redis operation instrumentation
  - Error tracking and business metrics

- **Middleware & Security**
  - Request ID tracking
  - Security headers (HSTS, X-Frame-Options, etc.)
  - Request/response logging
  - Optional rate limiting (sliding window)
  - Optional slow connection rejection
  - GZip compression
  - CORS configuration

- **Testing**
  - Pytest test suite with async support
  - SQLite for fast unit tests
  - PostgreSQL support for RLS testing
  - Fixtures for database, test users, authentication

### 🚧 In Progress / Planned

- **Backend Modules** (to be implemented)
  - Registry Module (members, first-timers, attendance, departments)
  - Finance Module (offerings, tithes, partnerships, batches, reconciliation)
  - Cells Module (cell meetings, reports, testimonies)
  - Reports Module (dashboards, analytics, exports)
  - Imports/Exports Module (legacy data migration, report generation)
  - Audit Module (immutable audit log queries)

- **Test Coverage**
  - Set up pytest-cov for coverage reporting
  - Achieve comprehensive test coverage across all modules

- **Frontend** (to be built)
  - Next.js + React frontend applications
  - Tailwind CSS + shadcn/ui components
  - Separate frontends per portal (Registry, Finance, Cells, Reports)

- **Production Infrastructure** (to be built)
  - Deployment tooling (Terraform, CloudFormation, or similar)
  - CI/CD pipelines
  - Production monitoring and alerting
  - Secrets management
  - High availability setup

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.12+ (for local development)
- PostgreSQL 15+ (if running database locally)

### Local Development

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd ce_ireland_zone_reporting
   ```

2. **Start services**
   ```bash
   make up
   ```
   This starts:
   - PostgreSQL (port 5432)
   - Redis (port 6379)
   - MinIO (ports 9000, 9001)
   - API server (port 8000)
   - Background worker

3. **Run database migrations**
   ```bash
   make migrate
   ```

4. **Seed permissions**
   ```bash
   make seed
   ```

5. **Access services**
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - MinIO Console: http://localhost:9001 (minio/minio123)

### Environment Variables

Create a `.env` file in the repository root:

```env
# Database
POSTGRES_URL=postgresql+psycopg://app:app@db:5432/app
REDIS_URL=redis://redis:6379/0

# S3/MinIO
S3_ENDPOINT=http://minio:9000
S3_BUCKET=ce-exports
S3_ACCESS_KEY=minio
S3_SECRET_KEY=minio123

# Security
JWT_SECRET=your-secret-key-here
TENANT_ID=12345678-1234-5678-1234-567812345678
TENANT_NAME=CE Ireland Zone

# OAuth (optional)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
FACEBOOK_CLIENT_ID=
FACEBOOK_CLIENT_SECRET=
OAUTH_REDIRECT_BASE_URL=http://localhost:8000/api/v1/auth/oauth

# Email/SMS (optional, for dev mode)
SMTP_HOST=localhost
SMTP_PORT=1025
```

## 📚 Documentation

- **[Test Suite Guide](apps/api/tests/README.md)** - Running tests, test structure
- **[Development Guide](docs/DEVELOPMENT.md)** - Development workflow and guidelines
- **[OAuth Setup](apps/api/app/auth/OAUTH_SETUP.md)** - Configuring OAuth SSO
- **[RLS Guide](apps/api/app/core/RLS_README.md)** - Row-Level Security implementation
- **[Background Jobs](apps/api/app/jobs/README.md)** - Job processing with RQ
- **[Product Requirements](docs/cursor/PRD.md)** - Detailed feature specifications
- **[TODO List](TODO.md)** - Future work and roadmap items

## 🧪 Testing

### Run Tests

```bash
# SQLite tests (fast)
make test

# PostgreSQL tests (with RLS)
make test-pg

# Verbose output
make test-verbose
```

### Test Structure

- Unit tests for utilities, services
- Integration tests for API endpoints
- Database tests with both SQLite and PostgreSQL
- Test fixtures in `tests/conftest.py`

See [tests/README.md](apps/api/tests/README.md) for details.

## 🛠️ Development

### Code Formatting

```bash
# Format code
make format

# Check formatting (no changes)
make format-check

# Or in Docker
make format-docker
```

### Available Make Commands

```bash
make help              # Show all available commands
make up                # Start all services
make down              # Stop all services
make migrate           # Run database migrations
make seed              # Seed permissions
make test              # Run tests (SQLite)
make test-pg           # Run tests (PostgreSQL)
make api-shell         # Open shell in API container
make worker            # Start background worker
make logs              # Follow API logs
```

### Database Migrations

```bash
# Create new migration
docker compose -f infra/docker-compose.yml exec api alembic revision --autogenerate -m "description"

# Run migrations
make migrate

# Rollback one migration
docker compose -f infra/docker-compose.yml exec api alembic downgrade -1
```

## 🔒 Security Features

- **Row-Level Security (RLS)**: Database-level tenant and scope isolation
- **JWT Tokens**: Secure, stateless authentication
- **2FA**: Two-factor authentication via SMS/Email
- **OAuth SSO**: Google and Facebook integration
- **RBAC**: Fine-grained permission system with organizational scopes
- **Security Headers**: HSTS, X-Frame-Options, CSP, etc.
- **Rate Limiting**: Optional request rate limiting
- **Audit Logging**: Immutable audit trail

## 📊 Observability

The platform includes comprehensive observability:

- **Structured Logging**: JSON-formatted logs (CloudWatch-compatible)
- **Metrics**: AWS EMF format for CloudWatch Metrics
- **Instrumentation**: Automatic timing for database queries and Redis operations
- **Error Tracking**: Global exception handlers with correlation IDs
- **Request Tracking**: Request IDs propagated through all logs

## 🗄️ Database Schema

Key models:
- `User` - User accounts with 2FA
- `Role` - Permission groups
- `Permission` - Fine-grained permissions
- `OrgUnit` - Organizational hierarchy (Zone → Group → Church → Outreach)
- `OrgAssignment` - User-to-org assignments with scopes
- `UserIdentity` - OAuth identity linking
- `LoginSession` - Refresh token sessions
- `OutboxNotification` - Async notification queue

See `apps/api/app/common/models.py` for full schema.

## 🎯 Roadmap

### Phase 1: Core Backend (✅ Completed)
- [x] Authentication & Authorization
- [x] User Management
- [x] Database Schema & Migrations
- [x] RLS Implementation
- [x] Background Jobs
- [x] Observability Stack

### Phase 2: Backend Modules (🚧 Next)
- [ ] Registry Module
- [ ] Finance Module
- [ ] Cells Module
- [ ] Reports Module
- [ ] Imports/Exports Module
- [ ] Test Coverage Setup

### Phase 3: Frontend (📋 Planned)
- [ ] Next.js frontend setup
- [ ] Registry Portal UI
- [ ] Finance Portal UI
- [ ] Cells Portal UI
- [ ] Reports Portal UI

### Phase 4: Production (📋 Planned)
- [ ] Infrastructure as Code
- [ ] CI/CD Pipelines
- [ ] Production Monitoring
- [ ] Secrets Management
- [ ] High Availability Setup

## 📝 License

[Add license information here]

## 🤝 Contributing

[Add contribution guidelines here]

## 📞 Support

[Add support/contact information here]

