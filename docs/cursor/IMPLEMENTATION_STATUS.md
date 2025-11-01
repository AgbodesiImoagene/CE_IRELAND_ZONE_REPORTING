# Implementation Status Summary

## Overview
This document provides a status summary of the CE Ireland Zone Church Reporting Platform backend implementation. The project follows a modular monolith architecture using FastAPI, PostgreSQL, and implements RBAC with organizational scopes.

---

## ✅ Completed Components

### 1. Project Infrastructure
- **Repository structure**: Monorepo layout with `apps/api`, `packages/`, `infra/`, `docs/`
- **Docker setup**: `docker-compose.yml` with Postgres, Redis, MinIO, and API service
- **Makefile**: Commands for `up`, `down`, `logs`, `migrate`, `seed`, `test`
- **Environment**: `.env.example` template (blocked from auto-creation, but content provided)

### 2. Database Schema & Migrations
- **SQLAlchemy models**: Complete IAM models in `app/common/models.py`
  - `User`, `Role`, `Permission`, `RolePermission`
  - `OrgUnit`, `OrgAssignment`, `OrgAssignmentUnit`
  - `UserIdentity` (for SSO), `UserSecret` (2FA config), `LoginSession` (refresh tokens)
  - `OutboxNotification` (for async email/SMS), `AuditLog`
  - Enums: `OrgUnitType`, `ScopeType`, `TwoFADelivery`
- **Alembic**: Configured for autogenerate migrations
  - Target metadata: `Base.metadata` from models
  - Migration created: `21b0d0d20401_iam_schema.py`
- **Note**: Uses SQLAlchemy 2.0 `Uuid` type (cross-platform compatible with SQLite)

### 3. Authentication & Authorization Core
- **Password hashing**: `pwdlib` with recommended algorithm (Argon2/bcrypt)
- **JWT tokens**: 
  - Access tokens (30 min expiry) + Refresh tokens (7 days)
  - Both include random nonce for uniqueness
  - Token rotation on refresh
- **2FA**: 
  - SMS/Email delivery (currently prints to console in dev)
  - 6-digit numeric codes, 5-minute expiry
  - Codes stored as SHA256 hash
- **Session management**: Refresh tokens stored in `login_sessions` table with expiry

### 4. Auth Endpoints (`/api/v1/auth/*`)
- `POST /login` → Returns `requires_2fa=True, user_id`
- `POST /2fa/send` → Sends code via SMS/email
- `POST /2fa/verify` → Returns access + refresh tokens
- `POST /refresh` → Rotates refresh token, returns new tokens
- `POST /logout` → Revokes refresh token
- `GET /me` → Returns user info with roles, permissions, org assignments

### 5. OAuth SSO (Google & Facebook)
- **Routes**: `/api/v1/auth/oauth/{provider}/start` and `/callback`
- **Identity linking**: 
  - Links OAuth identity to existing user by email
  - Creates new user if email not found
  - Supports both Google and Facebook
- **Service**: `OAuthService` handles all OAuth operations
- **Configuration**: OAuth credentials via env vars (see `OAUTH_SETUP.md`)
- **Note**: Still requires 2FA after OAuth login

### 6. Roles & Permissions
- **Seeding script**: `app/scripts/seed_permissions.py`
  - Reads from `docs/permissions_matrix.csv`
  - Creates roles and permissions, links them via `role_permissions`
- **Permission structure**: Dot-notation (e.g., `registry.people.read`, `finance.batches.lock`)
- **Default roles**: Zonal Pastor, Group Pastor, Church Pastor, Finance Officer, Cell Leader, etc.

### 7. Testing Infrastructure
- **Test suite**: Comprehensive unit + integration tests
  - `test_auth_utils.py`: Password, JWT, 2FA code utilities
  - `test_auth_service.py`: Service layer (auth, sessions, permissions)
  - `test_auth_routes.py`: API endpoint integration tests
  - `test_oauth_service.py`: OAuth identity linking tests
  - `test_oauth_routes.py`: OAuth endpoint tests (mocked)
- **Fixtures**: `conftest.py` with db, client, test users, roles, permissions
- **Test DB**: In-memory SQLite (fast, isolated per test)
- **Fixes applied**:
  - `tenant_id` fixture returns valid UUID: `"12345678-1234-5678-1234-567812345678"`
  - Refresh token uniqueness via nonce
  - Boolean column comparisons use `.is_(True)`

---

## 🚧 Remaining Tasks (In Progress / Pending)

### 1. User Provisioning (HIGH PRIORITY)
**Status**: Not started
**Location**: Plan todo "provisioning"
**Requirements**:
- `POST /users/invitations` - Create invitation with email, role, org assignments, 2FA delivery method
- Invitation token generation (signed, short-lived)
- Email/SMS delivery via `outbox_notifications` table
- User activation flow: follow link → set password → mandatory 2FA enrollment
- `POST /users` - Direct user creation (for onsite, requires temporary password)
- Permission checks: Creator must have `system.users.create` and can only assign roles/scopes within their effective scope
- Integration with SSO: If user signs in via OAuth with invited email, link identity and proceed to 2FA

### 2. RLS (Row-Level Security) Implementation (HIGH PRIORITY)
**Status**: Not started
**Location**: Plan todo "rls-session"
**Requirements**:
- Postgres session settings: `SET app.tenant_id = ...`, `SET app.user_id = ...`, `SET app.perms = ARRAY[...]`
- Helper functions:
  - `has_perm(text) RETURNS boolean`
  - `has_org_access(uuid) RETURNS boolean` (handles self/subtree/custom_set scopes)
- RLS policies on all tenant tables:
  - `FOR SELECT USING (tenant_id = current_setting('app.tenant_id')::uuid AND has_perm('x.read') AND has_org_access(org_unit_id))`
  - Similar for INSERT/UPDATE/DELETE
- Middleware: Set session variables at request start (after auth, before DB operations)
- Test RLS enforcement (ensure denied access on scope violations)

### 3. Async Job Processing
**Status**: Partially implemented
**Current**: 2FA codes printed to console
**Needed**:
- Email/SMS delivery workers (Celery or RQ)
- Process `outbox_notifications` table
- Background job queues: `imports`, `exports`, `summaries`, `emails`
- Event triggers: attendance → refresh summaries, batch locked → refresh giving summaries

### 4. Domain Modules (NOT STARTED)
**From PRD, these modules need implementation**:

#### Registry Module
- People/Members CRUD
- First-timers management with status workflow
- Attendance recording (per service)
- Department memberships
- CSV import/export

#### Finance Module
- Funds, Partnership Arms (lookups)
- Finance entries (offerings, tithes)
- Batches (group entries per service)
- Dual control: batch lock requires 2 approvers
- Partnerships (pledge tracking)
- Reconciliations

#### Cells Module
- Cells CRUD
- Cell reports (date, attendance, offerings, testimonies)
- Approval workflow (submitted → reviewed → approved)
- Auto-mirror cell offerings to finance entries

#### Reports Module
- Dashboards: membership, attendance, finance, cells, zone overview
- Drill-down hierarchy: Zone → Group → Church → Cell → Member
- Exports: CSV, Excel, PDF (async for >10k rows)
- Scheduled reports: weekly, monthly, quarterly
- Materialized views for aggregations

### 5. Additional Security Features
- **Audit logging**: Table exists, but need to implement audit decorator/middleware
- **Step-up 2FA**: For sensitive actions (full-PII exports, batch unlock, delete/merge)
- **PII masking**: Finance views show masked contact info; click-to-reveal with audit
- **CSRF protection**: Proper state validation for OAuth (currently simplified)
- **Session timeout**: 30 min idle, 12h absolute

---

## 🔧 Technical Decisions Made

1. **SQLAlchemy 2.0**: Using `Uuid` type (not `PGUUID`) for cross-platform compatibility
2. **SQLite for tests**: Faster than Postgres, with SQLAlchemy handling type conversions
3. **Authlib for OAuth**: Using `AsyncOAuth2Client` for Google/Facebook
4. **JWT nonce**: Added random nonce to prevent token collisions
5. **2FA required for all users**: SMS/Email TOTP codes, not optional
6. **Email-based identity linking**: OAuth identities linked to users by email
7. **Modular monolith**: Single FastAPI app, but clear module boundaries

---

## 📝 Important Notes for Next Developer

### Configuration
- `TENANT_ID` must be a valid UUID string (currently `"12345678-1234-5678-1234-567812345678"` in config)
- OAuth credentials: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `FACEBOOK_CLIENT_ID`, `FACEBOOK_CLIENT_SECRET`
- See `.env.example` for all required variables

### Running Tests
```bash
make test
# or
docker compose -f infra/docker-compose.yml exec api pytest tests/ -v
```
- Tests use in-memory SQLite
- `tenant_id` fixture returns valid UUID
- Some linter warnings about imports are expected (IDE may not resolve paths)

### Database Migrations
```bash
make migrate
# or manually
docker compose -f infra/docker-compose.yml exec api alembic upgrade head
```

### Seeding Permissions
```bash
make seed
# Reads from docs/permissions_matrix.csv
# Creates roles, permissions, and role-permission mappings
```

### Known Issues / TODOs
1. **2FA delivery**: Currently prints to console (`print(f"[DEV] 2FA code...")`). Need async worker to process `outbox_notifications`
2. **OAuth state validation**: Currently simplified, needs proper CSRF protection for production
3. **Access token nonce**: User added nonce to access tokens too (was only on refresh tokens)
4. **SQLite enum compatibility**: SQLAlchemy should auto-convert, but watch for enum-related errors in tests

### Code Organization
- `app/auth/`: All authentication, OAuth, session management
- `app/common/`: Shared models, DB session, utilities
- `app/core/`: Configuration, settings
- `app/scripts/`: One-off scripts (seeding, etc.)
- Tests mirror app structure in `tests/`

---

## 📚 Reference Documents
- `docs/cursor/PRD.md`: Product requirements (condensed)
- `docs/cursor/IMPLEMENTATION_GUIDE.md`: Development guide with patterns
- `docs/roles_permissions.tex`: Detailed RBAC specification
- `docs/permissions_matrix.csv`: Role-to-permission mappings for seeding
- `apps/api/app/auth/OAUTH_SETUP.md`: OAuth configuration guide

---

## 🎯 Immediate Next Steps

1. **Implement user provisioning** (invitations + direct create)
2. **Implement RLS** (session settings + helper functions + policies)
3. **Set up async workers** (email/SMS delivery, summary refresh)
4. **Start Registry module** (people, first-timers, attendance)

---

**Last Updated**: Based on conversation ending with test fixes and refresh token nonce implementation.

