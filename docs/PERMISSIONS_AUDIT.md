# Permissions Matrix Audit Report

## Summary

This document audits the permissions matrix CSV against actual permissions checked in the codebase.

## Findings

### 1. Permissions Used in Code but Missing from CSV

These permissions are actively checked in the code but are **NOT** in the permissions_matrix.csv:

#### System Permissions (IAM)
- `system.org_units.create` ✅ Used in IAM service
- `system.org_units.read` ✅ Used in IAM routes
- `system.org_units.update` ✅ Used in IAM service
- `system.org_units.delete` ✅ Used in IAM service
- `system.roles.create` ✅ Used in IAM service
- `system.roles.read` ✅ Used in IAM routes
- `system.roles.update` ✅ Used in IAM service
- `system.roles.delete` ✅ Used in IAM service
- `system.permissions.read` ✅ Used in IAM routes
- `system.users.read` ✅ Used in user routes
- `system.users.update` ✅ Used in user service
- `system.users.disable` ✅ Used in user service
- `system.users.reset_password` ✅ Used in user service

#### Reports Permissions
- `reports.query.execute` ✅ Used in reports service
- `reports.dashboards.read` ✅ Used in reports service
- `reports.exports.create` ✅ Used in reports service
- `reports.templates.create` ✅ Used in reports service
- `reports.schedules.create` ✅ Used in reports service

### 2. Permissions in CSV but Not Directly Checked

These permissions are in the CSV but are used via `validate_org_access_for_operation()` which takes the permission as a parameter:

#### Registry Permissions (Used via validate_org_access_for_operation)
- `registry.people.create` ✅ Used in registry service
- `registry.people.update` ✅ Used in registry service
- `registry.people.delete` ✅ Used in registry service (implied)
- `registry.people.merge` ✅ Used in registry service
- `registry.people.read` ✅ Used via RLS
- `registry.people.export` ✅ Used via RLS
- `registry.firsttimers.create` ✅ Used in registry service
- `registry.firsttimers.update` ✅ Used in registry service
- `registry.firsttimers.delete` ✅ Used in registry service (implied)
- `registry.firsttimers.read` ✅ Used via RLS
- `registry.firsttimers.export` ✅ Used via RLS
- `registry.attendance.create` ✅ Used in registry service
- `registry.attendance.update` ✅ Used in registry service
- `registry.attendance.delete` ✅ Used in registry service (implied)
- `registry.attendance.read` ✅ Used via RLS
- `registry.attendance.export` ✅ Used via RLS
- `registry.departments.create` ✅ Used in registry service
- `registry.departments.update` ✅ Used in registry service
- `registry.departments.delete` ✅ Used in registry service
- `registry.departments.read` ✅ Used via RLS
- `registry.cells.assign` ⚠️ Not found in code - may be future feature
- `registry.admin_notes.*` ⚠️ Not found in code - may be future feature

#### Finance Permissions (Used via validate_org_access_for_operation)
- `finance.batches.create` ✅ Used in finance service
- `finance.batches.update` ✅ Used in finance service
- `finance.batches.delete` ✅ Used in finance service
- `finance.batches.lock` ✅ Used in finance service
- `finance.batches.unlock` ✅ Used in finance service
- `finance.batches.read` ✅ Used via RLS
- `finance.entries.create` ✅ Used in finance service
- `finance.entries.update` ✅ Used in finance service
- `finance.entries.delete` ✅ Used in finance service
- `finance.entries.read` ✅ Used via RLS
- `finance.entries.export` ✅ Used via RLS
- `finance.verify` ✅ Used in finance service
- `finance.lookups.manage` ✅ Used in finance service

#### Cells Permissions (Used via validate_org_access_for_operation)
- `cells.manage` ✅ Used in cells service
- `cells.reports.create` ✅ Used in cells service
- `cells.reports.update` ✅ Used in cells service
- `cells.reports.delete` ✅ Used in cells service
- `cells.reports.approve` ✅ Used in cells service
- `cells.reports.read` ✅ Used via RLS
- `cells.reports.export` ✅ Used via RLS

#### Reports Permissions (Used via RLS or future features)
- `reports.view` ✅ Used via RLS
- `reports.export` ✅ Used via RLS
- `reports.schedule` ⚠️ Not directly checked - may be via RLS

#### System Permissions (Future features or implicit)
- `system.scopes.assign` ✅ Used in IAM service (as `system.users.assign`)
- `system.users.create` ✅ Used in user service
- `system.settings.manage` ⚠️ Not found in code - may be future feature
- `system.exports.full_pii` ⚠️ Not found in code - may be future feature

## Recommendations

### 1. Add Missing System Permissions to CSV

The following system permissions need to be added to the CSV for all roles:

```
system.org_units.create
system.org_units.read
system.org_units.update
system.org_units.delete
system.roles.create
system.roles.read
system.roles.update
system.roles.delete
system.permissions.read
system.users.read
system.users.update
system.users.disable
system.users.reset_password
```

### 2. Add Missing Reports Permissions to CSV

The following reports permissions need to be added:

```
reports.query.execute
reports.dashboards.read
reports.exports.create
reports.templates.create
reports.schedules.create
```

### 3. Verify Future Features

The following permissions are in CSV but not found in code - verify if they're planned:
- `registry.cells.assign`
- `registry.admin_notes.*`
- `system.settings.manage`
- `system.exports.full_pii`

## Permission Usage Patterns

### Direct Permission Checks
- `require_permission()` - Direct permission check
- `require_iam_permission()` - IAM-specific permission check

### Permission + Org Access Checks
- `validate_org_access_for_operation()` - Checks both permission AND org scope access

### RLS-Based Permissions
Some permissions are enforced via Row-Level Security (RLS) policies rather than explicit checks:
- `*.read` permissions (mostly)
- `*.export` permissions (mostly)

## Next Steps

1. ✅ Update permissions_matrix.csv with missing system permissions
2. ✅ Update permissions_matrix.csv with missing reports permissions
3. ⚠️ Verify future feature permissions or remove them
4. 📝 Document which permissions use RLS vs explicit checks

