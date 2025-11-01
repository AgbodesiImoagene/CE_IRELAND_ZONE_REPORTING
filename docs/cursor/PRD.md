---

# Christ Embassy Ireland Zone Church Reporting Platform

**Condensed Product Requirements for Developers**

---

## 1. Overview

A unified platform for the **Christ Embassy Ireland Zone** to manage:

* Member and first-timer registration
* Service attendance
* Financial records (offerings, tithes, partnerships)
* Cell ministry reporting
* Zone-wide leadership dashboards

Replaces spreadsheets with a secure, centralised record-keeping and reporting system spanning **Registry**, **Finance**, **Cells**, and **Reports** portals — all backed by a unified API.

---

## 2. System Portals

| Portal       | Purpose                                                 |
| ------------ | ------------------------------------------------------- |
| **Registry** | Manage members, first-timers, attendance, departments   |
| **Finance**  | Record offerings, tithes, partnerships, reconciliations |
| **Cells**    | Cell meetings, attendance, testimonies, offerings       |
| **Reports**  | Generate dashboards and exports across all scopes       |

Each portal runs on a subdomain (`registry.zone.ce.church`, etc.) and connects to a shared backend.

---

## 3. Roles & Access Model

### Hierarchy

**Zonal Pastor → Group Pastor → Church Pastor → Coordinators / Officers / Cell Leaders**

Each user has:

* **Role** → defines permissions
* **Org scope** → defines visibility (self, subtree, custom)

### Core Roles

| Role                          | Key Permissions                                          |
| ----------------------------- | -------------------------------------------------------- |
| **Zonal Pastor**              | Create groups/churches, manage pastors, view all reports |
| **Group Pastor**              | Manage churches in group, approve reports                |
| **Church Pastor/Coordinator** | Create service records, manage members                   |
| **Finance Officer**           | Enter offerings, lock/reconcile batches                  |
| **Registry Clerk**            | Enter first-timers, attendance, update member info       |
| **Cell Leader**               | Submit cell reports                                      |
| **Reports Viewer**            | View dashboards and exports                              |

### Security

* RBAC + org scope enforced at DB (Postgres RLS) and API level.
* Dual control for finance batch locking.
* All actions audited.

---

## 4. Functional Requirements (Condensed)

### Registry

* Create/edit **members** and **first-timers**
* Record **attendance** per service (linked to `service_id`)
* Track foundation school & baptism
* Maintain department memberships
* Import/export via CSV templates

### Finance

* Create **batches** per service/church
* Record **finance entries**: fund, partnership arm, method, giver
* Dual verification → lock batch → immutable
* Record and track **partnerships** (pledge, fulfilment)
* Reconcile verified batches
* Mirror cell offerings into finance entries automatically

### Cells

* Submit **cell reports** with date/time, attendance, offerings, testimonies
* Approve/review workflow (submitted → reviewed → approved)
* Missing submissions flagged in compliance dashboard

### Reports

* Dashboards: membership, attendance, finance, cells, assimilation
* Drill-down hierarchy: Zone → Group → Church → Cell → Member
* Exports (CSV, Excel, PDF) via background jobs
* Scheduled reports (weekly, monthly, quarterly)
* Data refresh within 5 minutes of new verified data

---

## 5. Non-Functional Requirements

### Security

* HTTPS + TLS 1.2+, Argon2/bcrypt password hashing
* RLS + permission checks for all CRUD operations
* AES-256 encryption at rest
* 2FA for pastors/finance roles
* Immutable audit logs for sensitive actions

### Reliability

* 99.9% uptime target
* Daily encrypted backups (30-day retention)
* RPO: 1 h, RTO: 2 h
* Graceful degradation if one module fails

### Performance

* P95 API latency ≤ 300 ms
* Reports ≤ 2 s; large exports async
* Supports 1 000 concurrent users
* Indexed aggregations + materialized views

### Maintainability

* Modular monolith (FastAPI + PostgreSQL)
* Shared schema per tenant (Ireland Zone)
* API spec documented via OpenAPI
* CI/CD with tests and schema migrations
* 80% code coverage target

### Usability

* Responsive UI (Next.js + Tailwind)
* Inline validation + contextual feedback
* WCAG 2.1 AA compliance

---

## 6. KPIs & Metrics

| Category     | KPI                                | Target        |
| ------------ | ---------------------------------- | ------------- |
| **Registry** | Membership completeness            | ≥ 95%         |
|              | First-timer conversion (to member) | ≥ 70%         |
|              | Attendance reporting compliance    | 100%          |
| **Finance**  | Batch entry within 48 h            | ≥ 95%         |
|              | Reconciliation accuracy            | ≤ 1% variance |
|              | Partnership fulfilment             | ≥ 85%         |
| **Cells**    | Weekly report submission           | ≥ 95%         |
|              | Offering reconciliation            | ≥ 95%         |
| **System**   | API error rate                     | ≤ 0.5%        |
|              | Uptime                             | ≥ 99.9%       |

---

## 7. Architecture Summary

### Tech Stack

* **Backend:** FastAPI (Python)
* **DB:** PostgreSQL (RLS enabled)
* **Cache / Queue:** Redis
* **Frontend:** Next.js / React
* **Storage:** S3-compatible (exports, receipts)
* **Workers:** Celery or RQ for async jobs
* **Deployment:** Docker containers (ECS/Kubernetes)

### Modules

1. Auth & Users
2. Registry
3. Finance
4. Cells
5. Reports
6. Imports / Exports
7. Audit

### Data Flow Highlights

* Attendance → updates daily summaries
* Cell report offerings → mirrored to finance entries
* Finance batches → locked, triggers dashboard refresh
* Imports validated → processed asynchronously

### Scalability

* Stateless containers → horizontal scaling
* Read replicas for analytics load
* Terraform-managed infrastructure

### Observability

* Structured JSON logs
* Metrics: latency, job queue depth, failed logins
* Alerts on downtime, slow queries, failed jobs

---

## 8. Data Model (Simplified)

### Core Entities

| Table                              | Purpose / Key Fields                           |
| ---------------------------------- | ---------------------------------------------- |
| `org_units`                        | region → zone → group → church → outreach      |
| `users`                            | auth, role assignments, 2FA                    |
| `people`                           | members and first-timers                       |
| `memberships`                      | join date, status, foundation/baptism          |
| `services`                         | service name/date/time                         |
| `attendance`                       | counts (men, women, teens, kids, etc.)         |
| `departments` / `department_roles` | ministry units & assignments                   |
| `cells`                            | cell info, leader, venue                       |
| `cell_reports`                     | date/time, attendance, offerings, meeting type |
| `funds`                            | tithes, offerings, partnership, etc.           |
| `partnership_arms`                 | Healing School, Rhapsody, etc.                 |
| `finance_entries`                  | fund, amount, giver, service/cell, method      |
| `batches`                          | grouped finance entries per service            |
| `partnerships`                     | pledge tracking and fulfilment                 |
| `audit_logs`                       | user, action, entity, timestamp                |

### Summary Tables (Materialized Views)

* `summary_attendance_daily`
* `summary_giving_daily`
* `summary_cells_weekly`
* `summary_members_status`

### Key Notes

* One attendance record per `(service, church)`
* Cell offerings auto-insert finance entry with `source_type='cell_report'`
* Finance entries immutable once batch locked
* Triggers refresh materialized summaries for reports

---

## 9. Reporting Requirements

### Dashboards

* **Membership:** totals, growth, demographics
* **Attendance:** trends, service comparisons
* **Finance:** funds by type, partnership fulfilment, giving trends
* **Cells:** compliance, attendance, outreach results
* **Zone Overview:** multi-level roll-up, KPI summaries

### Exports

* CSV, Excel, PDF
* Async for > 10 k rows
* Metadata logged in `exports` table

### Scheduled Reports

* Weekly summary (attendance + finance + cells)
* Monthly church overview
* Quarterly zone KPI report
* Generated by worker → emailed + logged

### Drill-Down Hierarchy

```
Zone → Group → Church → Cell → Member
Zone → Group → Church → Service
```

Access restricted by assigned scope.

---

## 10. Key Workflows

### Registry

1. Clerk enters first-timers → follow-up pipeline (New → Contacted → Returned → Member)
2. Attendance per service recorded → updates summary tables
3. Member details editable (audited changes)

### Finance

1. Officer enters offerings/tithes → batch created
2. Second user verifies + locks batch → immutable
3. Reconciled batches populate reports

### Cells

1. Leader submits cell report (attendance, testimonies, offering)
2. System mirrors offering to Finance
3. Compliance check weekly; missing reports flagged

### Reports

1. Pastors view dashboards → drill into scope
2. Export or schedule recurring delivery
3. All report views/exports logged

### Admin

* Zonal Pastor provisions users & scopes
* Import legacy spreadsheets → validation → audit logged

---

## 11. Risks & Assumptions (Condensed)

| Risk                           | Impact | Mitigation                           |
| ------------------------------ | ------ | ------------------------------------ |
| Poor data quality from imports | Medium | Validation + review dashboards       |
| Low user adoption              | Medium | Training + mobile access             |
| Connectivity issues            | Medium | Offline or lightweight sync mode     |
| Misconfigured permissions      | High   | Role templates + periodic audits     |
| Financial entry errors         | Medium | Dual control + validation            |
| Slow large reports             | Medium | Materialized views + async jobs      |
| Data loss                      | High   | Daily backups + multi-region storage |
| Staff turnover                 | Medium | Training + backup roles              |

**Assumptions:**

* Stable internet access across churches
* Manual entry for offerings (no payment processing)
* Hierarchical structure remains consistent
* Dedicated IT admin for maintenance

---

## 12. Lookups / Reference Enums

| Type                    | Values                                            |
| ----------------------- | ------------------------------------------------- |
| **Service Type**        | Sunday, Midweek, Special                          |
| **Meeting Type**        | Prayer & Planning, Bible Study, Outreach          |
| **Payment Method**      | Cash, KingsPay, Bank Transfer, POS, Cheque, Other |
| **Verification Status** | Draft, Verified, Reconciled, Locked               |
| **First-Timer Status**  | New, Contacted, Returned, Member                  |
| **Partnership Cadence** | Weekly, Monthly, Quarterly, Annual                |
| **Org Unit Type**       | Region, Zone, Group, Church, Outreach             |

---

## 13. KPIs Formulas (Reference)

* **Membership Growth:**
  `(NewMembers / StartingMembers) × 100`
* **First-Timer Retention:**
  `(Returned / TotalFirstTimers) × 100`
* **Partnership Fulfilment:**
  `(TotalGiven / Pledged) × 100`
* **Per-Capita Giving:**
  `(TotalGiving / AvgAttendance)`
* **Cell Compliance:**
  `(ReportsSubmitted / ExpectedReports) × 100`

---

## 14. References

* [Christ Embassy Official Website](https://www.christembassy.org)
* [Loveworld Partnership Arms](https://loveworldinc.org/partnership-arms)
* [Data Protection Commission Ireland](https://www.dataprotection.ie)

---

**End of Document**
*Christ Embassy Ireland Zone Church Reporting Platform — PRD (Developer Version)*

---
