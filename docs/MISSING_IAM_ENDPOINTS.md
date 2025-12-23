# Missing IAM Endpoints

This document lists the IAM (Identity and Access Management) API endpoints that are currently missing from the implementation.

## Currently Implemented Endpoints

### Authentication
- ✅ `POST /api/v1/auth/login` - User login
- ✅ `POST /api/v1/auth/2fa/send` - Send 2FA code
- ✅ `POST /api/v1/auth/2fa/verify` - Verify 2FA code
- ✅ `POST /api/v1/auth/refresh` - Refresh access token
- ✅ `POST /api/v1/auth/logout` - Logout
- ✅ `GET /api/v1/auth/me` - Get current user info

### OAuth SSO
- ✅ `GET /api/v1/oauth/{provider}/start` - Start OAuth flow
- ✅ `GET /api/v1/oauth/{provider}/callback` - OAuth callback

### User Provisioning
- ✅ `POST /api/v1/users/invitations` - Create user invitation
- ✅ `POST /api/v1/users/activate` - Activate user from invitation
- ✅ `POST /api/v1/users` - Create user directly

---

## Missing Endpoints

### 1. User Management

**Missing CRUD operations:**
- ❌ `GET /api/v1/users` - List users (with filters: org_unit_id, role_id, is_active, search)
- ❌ `GET /api/v1/users/{user_id}` - Get user details
- ❌ `PATCH /api/v1/users/{user_id}` - Update user (email, is_active, is_2fa_enabled)
- ❌ `DELETE /api/v1/users/{user_id}` - Delete/deactivate user
- ❌ `POST /api/v1/users/{user_id}/disable` - Disable user account
- ❌ `POST /api/v1/users/{user_id}/enable` - Enable user account
- ❌ `POST /api/v1/users/{user_id}/reset-password` - Reset user password (admin action)
- ❌ `POST /api/v1/users/{user_id}/change-password` - Change own password (requires current password)

**Permissions required:**
- `system.users.read` - For GET operations
- `system.users.update` - For PATCH operations
- `system.users.disable` - For disable/enable operations
- `system.users.reset_password` - For password reset

---

### 2. Roles Management

**Missing CRUD operations:**
- ❌ `GET /api/v1/roles` - List roles (with filters: tenant_id)
- ❌ `GET /api/v1/roles/{role_id}` - Get role details with permissions
- ❌ `POST /api/v1/roles` - Create role
- ❌ `PATCH /api/v1/roles/{role_id}` - Update role name
- ❌ `DELETE /api/v1/roles/{role_id}` - Delete role (if no users assigned)

**Permissions required:**
- `system.roles.read` - For GET operations
- `system.roles.create` - For POST operations
- `system.roles.update` - For PATCH operations
- `system.roles.delete` - For DELETE operations

---

### 3. Permissions Management

**Missing read operations:**
- ❌ `GET /api/v1/permissions` - List all permissions (with optional filter by module)
- ❌ `GET /api/v1/permissions/{permission_id}` - Get permission details

**Note:** Permissions are typically seeded from CSV and not created via API, but read access is useful.

**Permissions required:**
- `system.permissions.read` - For GET operations

---

### 4. Role-Permission Assignments

**Missing operations:**
- ❌ `GET /api/v1/roles/{role_id}/permissions` - Get all permissions for a role
- ❌ `POST /api/v1/roles/{role_id}/permissions` - Assign permission(s) to role
- ❌ `DELETE /api/v1/roles/{role_id}/permissions/{permission_id}` - Remove permission from role
- ❌ `PUT /api/v1/roles/{role_id}/permissions` - Replace all permissions for a role (bulk update)

**Permissions required:**
- `system.roles.assign` - For all operations (as per PRD)

---

### 5. Organizational Units Management

**Missing CRUD operations:**
- ❌ `GET /api/v1/org-units` - List org units (with filters: type, parent_id, search)
- ❌ `GET /api/v1/org-units/{org_unit_id}` - Get org unit details
- ❌ `POST /api/v1/org-units` - Create org unit
- ❌ `PATCH /api/v1/org-units/{org_unit_id}` - Update org unit (name, parent_id)
- ❌ `DELETE /api/v1/org-units/{org_unit_id}` - Delete org unit (if no children, no records)
- ❌ `GET /api/v1/org-units/{org_unit_id}/children` - Get direct children of org unit
- ❌ `GET /api/v1/org-units/{org_unit_id}/tree` - Get org unit subtree (all descendants)
- ❌ `GET /api/v1/org-units/{org_unit_id}/ancestors` - Get org unit ancestors (path to root)

**Permissions required:**
- `system.org_units.read` - For GET operations
- `system.org_units.create` - For POST operations
- `system.org_units.update` - For PATCH operations
- `system.org_units.delete` - For DELETE operations

---

### 6. Organizational Assignments Management

**Missing operations:**
- ❌ `GET /api/v1/users/{user_id}/assignments` - Get all org assignments for a user
- ❌ `GET /api/v1/org-units/{org_unit_id}/assignments` - Get all assignments for an org unit
- ❌ `POST /api/v1/users/{user_id}/assignments` - Create org assignment for user
- ❌ `PATCH /api/v1/users/{user_id}/assignments/{assignment_id}` - Update org assignment (role, scope_type)
- ❌ `DELETE /api/v1/users/{user_id}/assignments/{assignment_id}` - Remove org assignment
- ❌ `POST /api/v1/users/{user_id}/assignments/{assignment_id}/units` - Add org unit to custom_set scope
- ❌ `DELETE /api/v1/users/{user_id}/assignments/{assignment_id}/units/{org_unit_id}` - Remove org unit from custom_set scope

**Permissions required:**
- `system.scopes.assign` - For all operations (as per PRD)
- `system.scopes.read` - For GET operations

---

### 7. User Invitations Management

**Missing operations:**
- ❌ `GET /api/v1/users/invitations` - List invitations (with filters: email, status, expires_before)
- ❌ `GET /api/v1/users/invitations/{invitation_id}` - Get invitation details
- ❌ `POST /api/v1/users/invitations/{invitation_id}/resend` - Resend invitation email
- ❌ `DELETE /api/v1/users/invitations/{invitation_id}` - Cancel/revoke invitation

**Permissions required:**
- `system.users.create` - Already checked for creation, but needs read/delete permissions

---

### 8. Audit Log Access

**Missing operations:**
- ❌ `GET /api/v1/audit-logs` - List audit logs (with filters: actor_id, entity_type, entity_id, date_range)
- ❌ `GET /api/v1/audit-logs/{log_id}` - Get audit log details

**Permissions required:**
- `system.audit.view` - For all operations

---

## Summary by Category

### High Priority (Core IAM Functionality)
1. **User Management CRUD** - Essential for user administration
2. **Roles Management CRUD** - Essential for role administration
3. **Org Units Management CRUD** - Essential for organizational hierarchy management
4. **Org Assignments Management** - Essential for assigning users to org units with scopes
5. **Role-Permission Assignments** - Essential for configuring role permissions

### Medium Priority (Administrative Features)
6. **User Invitations Management** - Helpful for managing pending invitations
7. **Permissions Listing** - Useful for viewing available permissions
8. **Audit Log Access** - Important for security and compliance

### Implementation Order Recommendation

1. **Phase 1: Org Units Management** (Foundation for other IAM features)
   - GET/POST/PATCH/DELETE org-units
   - Tree/children endpoints

2. **Phase 2: Roles & Permissions** (Role configuration)
   - GET/POST/PATCH/DELETE roles
   - GET permissions
   - Role-permission assignment endpoints

3. **Phase 3: User Management** (User administration)
   - GET/PATCH/DELETE users
   - User listing with filters
   - Password reset operations

4. **Phase 4: Org Assignments** (User-org relationships)
   - GET/POST/PATCH/DELETE assignments
   - Custom scope unit management

5. **Phase 5: Supporting Features** (Nice to have)
   - Invitations management
   - Audit log viewing

---

## Notes

- All endpoints should enforce RLS (Row-Level Security) based on user's org assignments
- All endpoints should check appropriate permissions before allowing operations
- All write operations should create audit log entries
- Delete operations should be soft-deletes where possible (set `is_active=false` for users)
- Bulk operations (e.g., bulk permission assignment) should be considered for efficiency
- Pagination should be implemented for list endpoints

