# IAM Access Control Flow Endpoints

This document describes the new endpoints added to support access control flow operations.

## New Endpoints

### 1. Get Effective Permissions for Org Unit

**Endpoint**: `GET /iam/users/{user_id}/effective-permissions?org_unit_id={org_unit_id}`

**Description**: Get the effective permissions a user has at a specific org unit. This is useful for:
- Troubleshooting access issues
- Verifying permissions before operations
- Understanding what a user can do at a specific location

**Permissions Required**: `system.users.read`

**Response**:
```json
{
  "user_id": "uuid",
  "org_unit_id": "uuid",
  "permissions": ["registry.people.create", "registry.people.read", ...],
  "applicable_assignments": [
    {
      "assignment_id": "uuid",
      "role_id": "uuid",
      "role_name": "Church Administrator",
      "org_unit_id": "uuid",
      "org_unit_name": "Main Church",
      "scope_type": "self"
    }
  ]
}
```

**Example**:
```bash
GET /api/v1/iam/users/123e4567-e89b-12d3-a456-426614174000/effective-permissions?org_unit_id=456e7890-e89b-12d3-a456-426614174001
```

### 2. Bulk Create Assignments

**Endpoint**: `POST /iam/assignments/bulk`

**Description**: Create multiple org assignments in a single request. Useful for:
- Assigning multiple users to the same role/org
- Setting up new churches with multiple staff
- Bulk user provisioning

**Permissions Required**: `system.users.assign`

**Request**:
```json
{
  "assignments": [
    {
      "user_id": "uuid",
      "org_unit_id": "uuid",
      "role_id": "uuid",
      "scope_type": "self",
      "custom_org_unit_ids": null
    },
    {
      "user_id": "uuid",
      "org_unit_id": "uuid",
      "role_id": "uuid",
      "scope_type": "subtree",
      "custom_org_unit_ids": null
    }
  ]
}
```

**Response**:
```json
{
  "created": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "org_unit_id": "uuid",
      "role_id": "uuid",
      "scope_type": "self",
      "org_unit": {...},
      "role": {...}
    }
  ],
  "failed": [
    {
      "assignment": {...},
      "error": "Assignment already exists"
    }
  ],
  "total_requested": 2,
  "total_created": 1,
  "total_failed": 1
}
```

**Notes**:
- Maximum 100 assignments per request
- Each assignment is validated independently
- Failed assignments don't prevent successful ones
- All successful assignments are created in a single transaction

## Use Cases

### Use Case 1: Troubleshooting Access Issues

**Scenario**: User reports they can't create a person record at a specific church.

**Solution**:
1. Call `GET /iam/users/{user_id}/effective-permissions?org_unit_id={church_id}`
2. Check if `registry.people.create` is in the permissions list
3. Review applicable_assignments to see which role/assignment grants access
4. If missing, check if assignment scope covers the org unit

### Use Case 2: Bulk User Setup

**Scenario**: Setting up a new church with 5 staff members.

**Solution**:
1. Create assignments for all 5 users in one request:
```json
{
  "assignments": [
    {"user_id": "...", "org_unit_id": "church_id", "role_id": "pastor_role", "scope_type": "self"},
    {"user_id": "...", "org_unit_id": "church_id", "role_id": "admin_role", "scope_type": "self"},
    ...
  ]
}
```

### Use Case 3: Permission Verification

**Scenario**: Before allowing an operation, verify user has permission at target org.

**Solution**:
1. Call effective-permissions endpoint
2. Check if required permission exists in response
3. Proceed or deny based on result

## Implementation Details

### Effective Permissions Logic

The `get_effective_permissions_for_org` method:
1. Gets all assignments for the user
2. Filters assignments that grant access to target org unit:
   - `self`: Exact match
   - `subtree`: Target is descendant of assigned org
   - `custom_set`: Target is in custom units list
3. Collects permissions from applicable assignments
4. Returns union of all permissions

### Bulk Assignment Logic

The `create_bulk_assignments` method:
1. Validates creator has `system.users.assign` permission
2. Processes each assignment independently
3. Creates successful assignments
4. Collects errors for failed assignments
5. Returns summary with created and failed items

## Related Endpoints

- `GET /users/{user_id}/permissions` - Get all permissions (across all orgs)
- `GET /users/{user_id}/assignments` - Get all assignments
- `POST /users/{user_id}/assignments` - Create single assignment
- `GET /iam/org-units/{org_unit_id}/assignments` - Get assignments for org unit

