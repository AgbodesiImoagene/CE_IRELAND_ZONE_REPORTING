Here’s a battle-tested way to structure a **Cursor-friendly implementation guide** so you (and AI-in-the-loop) can build fast without losing rigor. Use this as `IMPLEMENTATION_GUIDE.md` at the repo root.

---

# Implementation Guide (Cursor-Optimized)

## 0) How to use this guide in Cursor

* Keep this file open while prompting; Cursor will pull sections into context.
* Use the **Tasks** blocks as issue tickets. Copy/paste into Cursor’s task panel.
* Put code scaffolds here so Cursor can autocomplete consistent patterns.
* Add a short **`.cursorrules`** (below) to bias responses toward our stack, naming, and style.

---

## 1) Tech Stack & Environments

**Backend:** FastAPI (Python 3.11+), Postgres 15+, Redis
**Frontends:** Next.js (React), Tailwind
**Workers:** Celery (Redis broker) or RQ
**Storage:** S3-compatible (MinIO in dev)
**Infra (dev):** Docker Compose

**Envs**

* `dev`: hot-reload, verbose logs
* `staging`: prod-like, seeded data
* `prod`: hardened, observability enabled

**Make targets**

```makefile
# Makefile (excerpt)
up:        ## start stack
\tdocker compose up -d
down:      ## stop stack
\tdocker compose down
logs:      ## tail app logs
\tdocker compose logs -f api
migrate:   ## alembic upgrade head
\tdocker compose exec api alembic upgrade head
seed:      ## seed dev data
\tdocker compose exec api python -m app.scripts.seed
test:      ## run tests
\tdocker compose exec api pytest -q
```

---

## 2) Repository Layout (monorepo)

```
.
├─ apps/
│  ├─ api/                 # FastAPI service
│  │  ├─ app/
│  │  │  ├─ core/          # config, security, rls helpers
│  │  │  ├─ auth/          # JWT/2FA, sessions
│  │  │  ├─ registry/      # members, first-timers, attendance
│  │  │  ├─ finance/       # funds, entries, batches, partnerships
│  │  │  ├─ cells/         # cells, cell_reports
│  │  │  ├─ reports/       # summary queries, exports
│  │  │  ├─ imports/       # CSV mapper & jobs
│  │  │  ├─ audit/         # immutable logs
│  │  │  ├─ common/        # deps: db, cache, s3, utils, schemas
│  │  │  └─ main.py
│  │  ├─ alembic/          # migrations
│  │  └─ tests/            # unit/integration
│  ├─ web-registry/        # Next.js app (portal)
│  ├─ web-finance/
│  ├─ web-cells/
│  └─ web-reports/
├─ packages/
│  ├─ ui/                  # shared React UI kit (shadcn setup)
│  └─ tsconfig/
├─ infra/
│  ├─ docker-compose.yml
│  ├─ nginx/               # subdomain routing (dev)
│  └─ terraform/           # cloud (later)
├─ docs/
│  ├─ PRD.md               # condensed PRD (you have this)
│  ├─ ADR/                 # architecture decision records
│  └─ ERD.png
└─ IMPLEMENTATION_GUIDE.md
```

---

## 3) Configuration & Secrets

* **.env.example** (root) – copy to `.env` for dev.

```dotenv
POSTGRES_URL=postgresql+psycopg://app:app@db:5432/app
REDIS_URL=redis://redis:6379/0
S3_ENDPOINT=http://minio:9000
S3_BUCKET=ce-exports
S3_ACCESS_KEY=minio
S3_SECRET_KEY=minio123
JWT_SECRET=change-me
TENANT_ID=ireland-zone-uuid
```

* Secrets in prod: use AWS Secrets Manager / SSM.
* Cursor tip: keep `.env.example` small & clear so AI suggests correct env vars.

---

## 4) Database & Migrations

### 4.1 Migrations

* Use **Alembic**. One migration per feature PR.
* Naming: `YYYYMMDDHHMM_module_change`.

### 4.2 RLS core (must-have)

* Every table: `tenant_id uuid`, `org_unit_id uuid` when applicable.
* Session bootstrap (set at request start):

  * `app.tenant_id`, `app.user_id`, `app.perms text[]`.
* Helper SQL (functions) generated in an early migration:

  * `has_perm(text) returns boolean`
  * `has_org_access(uuid) returns boolean`
* Policies per table:

  * `FOR SELECT USING (tenant_id = current_setting('app.tenant_id')::uuid AND has_perm('x.read') AND has_org_access(org_unit_id))`
  * Similar for INSERT/UPDATE/DELETE with verb checks.

**Task**: Create migration `0001_base_schema_rls` (see PRD Data Model).

---

## 5) API Conventions

* **Versioning:** `/api/v1/...`
* **Auth:** Bearer JWT; 2FA where required.
* **Errors:** JSON `{code, message, details?}`
* **Pagination:** `?page=1&per_page=50` → `{items, page, per_page, total}`
* **Filtering:** use query params; whitelist per endpoint.
* **Idempotency (POST):** optional header `Idempotency-Key`.

**Example error schema**

```json
{
  "code": "VALIDATION_ERROR",
  "message": "fund_id is required",
  "details": {"field": "fund_id"}
}
```

---

## 6) Module Scopes & First Routes

### 6.1 Auth

* `POST /auth/login` → JWT + required 2FA state
* `POST /auth/2fa/verify`
* `GET /me` → perms + org assignments

### 6.2 Registry

* Members: `GET/POST/PATCH /members`, `GET /members/{id}`
* First-timers: `GET/POST/PATCH /first-timers`, `POST /first-timers/{id}/convert`
* Services: `GET/POST /services`
* Attendance: `GET/POST /attendance` (one per service)

### 6.3 Finance

* Funds & arms: `GET/POST /funds`, `GET/POST /partnership-arms`
* Batches: `GET/POST/PATCH /batches`, `POST /batches/{id}/lock`
* Entries: `GET/POST/PATCH /entries`
* Partnerships: `GET/POST /partnerships`

### 6.4 Cells

* Cells: `GET/POST/PATCH /cells`
* Reports: `GET/POST/PATCH /cell-reports`, `POST /cell-reports/{id}/approve`

### 6.5 Reports

* Dashboards: `GET /dashboards/{type}` (type: membership|attendance|finance|cells|overview)
* Exports: `POST /exports` → job id; `GET /exports/{id}` → URL when ready
* Scheduled: `POST /reports/schedules`

> Cursor tip: Scaffold these endpoints with Pydantic schemas; AI will replicate patterns consistently.

---

## 7) Background Jobs & Events

* Use Celery (`celery -A app.worker worker -l info`).
* Queues:

  * `imports`, `exports`, `summaries`, `emails`
* Event triggers:

  * on attendance create → refresh `summary_attendance_daily`
  * on batch locked → refresh `summary_giving_daily`
  * on cell_report submit/approve → insert mirrored `finance_entry` (source=`cell_report`) + refresh summaries

**Task**: Implement a minimal event dispatcher (in-process pub/sub).

---

## 8) Observability

* **Logging:** JSON logs with `request_id`, `user_id`, `org_unit_id`
* **Metrics:** Prometheus or StatsD (latency, error rate, job depth)
* **Audit:** append-only `audit_logs` on sensitive reads/writes

**Decorator snippet (Python)**

```python
def audit(action:str):
    def wrap(fn):
        @functools.wraps(fn)
        async def inner(*a, **kw):
            res = await fn(*a, **kw)
            await audit_log(action, entity_from(res), before_after=kw.get("_delta"))
            return res
        return inner
    return wrap
```

---

## 9) Frontend Portals (Next.js)

* Shared **UI kit** in `packages/ui` (shadcn, Tailwind tokens).
* **Auth guard** HOC reads JWT; fetches `/me`.
* **Data grid** standard component with filter + export button.
* **Form** standard component: zod schema + react-hook-form.

**Registry portal pages**

```
/members, /members/[id]
/first-timers
/attendance
/departments
```

**Finance portal pages**

```
/batches, /batches/[id]
/entries
/funds, /partnership-arms
```

**Cells portal pages**

```
/cells, /cells/[id]
/reports
```

**Reports portal pages**

```
/dashboards/overview
/dashboards/attendance
/dashboards/finance
/dashboards/cells
/exports
```

---

## 10) Security Controls

* **Dual control:** `POST /batches/{id}/lock` requires second approver
* **Step-up 2FA:** for full-PII exports & unlocks
* **PII masking:** in Finance views; click-to-reveal audited
* **Rate limits:** exports & report generation endpoints

---

## 11) Testing Strategy

* **Unit:** schemas, services, utils
* **Integration:** API + DB (Testcontainers)
* **RLS tests:** ensure denied access on scope violations
* **Golden tests:** CSV import mapping, export contents
* **Performance smoke:** dashboards under 2s (seeded data)

**Pytest layout**

```
apps/api/tests/
├─ unit/
├─ integration/
└─ perf/
```

---

## 12) Data Import/Export

**Import flow**

1. Upload CSV → map columns → validate (dry-run)
2. Commit job → write rows → produce `import_errors` if any
3. Audit job & results

**Export**

* Async job writes to S3; return signed URL
* Footer metadata: scope, timestamp, generator, filters

---

## 13) Rollout Plan

1. **Phase 1:** Registry + Attendance + basic Reports
2. **Phase 2:** Finance (entries, batches, lock)
3. **Phase 3:** Cells + mirrored offerings
4. **Phase 4:** Scheduled reports, partnerships
5. **Phase 5:** Hardening: audit search, 2FA mandate, read replica

---

## 14) Cursor Prompts & Rules

**`.cursorrules` (root)**

```
- Prefer FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, Redis, Celery.
- Enforce Postgres RLS and org-scope checks in all DB access.
- For FastAPI handlers, always:
  - validate input with Pydantic models
  - set session context (tenant_id, user_id, perms)
  - call service layer (no DB in handlers)
- For queries, use parameterized SQL; add indexes when filtering by date/org.
- For Next.js pages, use server components for data fetch, Tailwind for styling, zod for validation.
- For tests, use Testcontainers; avoid mocking DB for integration tests.
```

**Starter prompt (example)**

> Scaffold `/api/v1/attendance` with Pydantic models, RLS-safe queries, and one-per-service constraint. Include unit + integration tests and Alembic migration.

---

## 15) Initial Task List (copy into issues)

* [ ] `0001_base_schema_rls` migration (core tables + helpers)
* [ ] Auth skeleton (JWT, `/me`, session context, perms hydration)
* [ ] Registry: services + attendance endpoints + tests
* [ ] Reports: `summary_attendance_daily` + refresh hooks
* [ ] Finance: funds/arms + entries + batches + lock dual control
* [ ] Cells: cells + reports + mirror offerings job
* [ ] Imports: CSV mapper + dry-run validate + commit
* [ ] Exports: async CSV (S3) + audit
* [ ] Frontends: auth shell + two list/detail screens per portal
* [ ] Observability: JSON logs + simple metrics endpoint

---

## 16) ADRs (Decision Records)

Create `docs/ADR/0001_modular_monolith.md`

```
Context: Zone-scale app with unified team.
Decision: Modular monolith; microservice-capable boundaries.
Consequences: simpler ops, faster delivery; reports can split later.
```

Create `docs/ADR/0002_rls_everywhere.md`

```
Context: Strict hierarchy and PII.
Decision: Postgres RLS on all tenant/org tables + API enforcement.
Consequences: safer by default; slightly more complexity in queries/migrations.
```

---

## 17) Appendix — Example Schemas (Pydantic)

```python
# apps/api/app/registry/schemas.py
class AttendanceCreate(BaseModel):
    service_id: UUID
    men: int = Field(ge=0)
    women: int = Field(ge=0)
    teens: int = Field(ge=0)
    kids: int = Field(ge=0)
    first_timers: int = Field(ge=0)
    new_converts: int = Field(ge=0)
    notes: str | None = None
```

```python
# apps/api/app/finance/schemas.py
class FinanceEntryCreate(BaseModel):
    transaction_date: date
    fund_id: UUID
    partnership_arm_id: UUID | None = None
    amount: Decimal = Field(gt=0)
    method: Literal["cash","kingspay","bank_transfer","pos","cheque","other"]
    person_id: UUID | None = None
    cell_id: UUID | None = None
    service_id: UUID | None = None
    external_giver_name: str | None = None
    reference: str | None = None
    comment: str | None = None
```

---
