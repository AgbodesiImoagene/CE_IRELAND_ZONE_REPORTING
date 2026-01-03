# Business Metrics Catalog

This document describes all business metrics emitted by the application. Metrics are emitted using the structured `MetricsService` which ensures consistent naming and metadata.

## Metric Categories

Metrics are organized into categories:
- **user**: User management operations
- **report**: Report generation and viewing
- **cell**: Cell and cell report operations
- **finance**: Finance entries, batches, and lookups
- **registry**: People, first-timers, attendance, departments
- **import**: Data import operations
- **iam**: Identity and access management operations
- **security**: Security and authentication events
- **data_quality**: Data validation and quality metrics

## Usage

All metrics should be emitted using `MetricsService` helper methods:

```python
from app.core.business_metrics import BusinessMetric
from app.core.metrics_service import MetricsService

# Emit a user metric
MetricsService.emit_user_metric(
    metric_name=BusinessMetric.USER_CREATED,
    tenant_id=tenant_id,
    actor_id=creator_id,
    role_id=str(request.role_id),
)
```

## Metric Catalog

### User Metrics

| Metric Name | Description | Metadata |
|------------|-------------|----------|
| `UserCreated` | User account created | `actor_id`, `user_id`, `role_id` |
| `UserUpdated` | User account updated | `actor_id`, `user_id` |
| `UserDisabled` | User account disabled | `actor_id`, `user_id` |
| `UserEnabled` | User account enabled | `actor_id`, `user_id` |
| `UserLogin` | User logged in | `user_id` |
| `UserLogout` | User logged out | `user_id` |
| `UserPasswordChanged` | User changed their password | `user_id` |
| `UserPasswordReset` | Admin reset user password | `actor_id`, `user_id` |
| `UserInvitationCreated` | User invitation created | `actor_id`, `email` |
| `UserInvitationAccepted` | User invitation accepted | `user_id` |

### Security Metrics

| Metric Name | Description | Metadata |
|------------|-------------|----------|
| `UserLoginFailed` | Failed login attempt | `email` (hashed), `reason` |
| `User2FASent` | 2FA code sent | `user_id`, `delivery_method` |
| `User2FAVerified` | 2FA code verified | `user_id` |
| `PermissionDenied` | Permission check failed | `user_id`, `permission`, `resource` |
| `OAuthLogin` | OAuth/SSO login successful | `user_id`, `provider` |
| `OAuthStarted` | OAuth flow initiated | `provider` |
| `OAuthCompleted` | OAuth flow completed | `user_id`, `provider` |
| `OAuthFailed` | OAuth flow failed | `provider`, `error_type` |

### Report Metrics

| Metric Name | Description | Metadata |
|------------|-------------|----------|
| `ReportQueryExecuted` | Report query executed | `user_id`, `report_type` |
| `ReportExportCreated` | Report export job created | `user_id`, `report_type` |
| `ReportExportCompleted` | Export job completed | `user_id`, `export_id`, `format`, `row_count` |
| `ReportExportFailed` | Export job failed | `user_id`, `export_id`, `error_type` |
| `ReportExportDownloaded` | Export file downloaded | `user_id`, `export_id` |
| `ReportDashboardViewed` | Dashboard viewed | `user_id`, `report_type` |
| `ReportTemplateCreated` | Report template created | `user_id` |
| `ReportScheduleCreated` | Report schedule created | `user_id` |
| `SearchExecuted` | Search performed | `user_id`, `entity_type`, `result_count` |
| `FilterApplied` | Filter applied | `user_id`, `entity_type`, `filter_count` |

### Cell Metrics

| Metric Name | Description | Metadata |
|------------|-------------|----------|
| `CellCreated` | Cell created | `actor_id`, `cell_id` |
| `CellUpdated` | Cell updated | `actor_id`, `cell_id` |
| `CellDeleted` | Cell deleted | `actor_id`, `cell_id` |
| `CellReportCreated` | Cell report created | `actor_id`, `cell_id`, `attendance` |
| `CellReportUpdated` | Cell report updated | `actor_id`, `cell_id` |
| `CellReportApproved` | Cell report approved | `actor_id`, `cell_id` |
| `CellReportReviewed` | Cell report reviewed | `actor_id`, `cell_id`, `status` |
| `CellReportDeleted` | Cell report deleted | `actor_id`, `cell_id` |

### Finance Metrics

| Metric Name | Description | Metadata |
|------------|-------------|----------|
| `FinanceEntryCreated` | Finance entry created | `actor_id`, `org_unit_id` |
| `FinanceEntryUpdated` | Finance entry updated | `actor_id`, `org_unit_id` |
| `FinanceEntryDeleted` | Finance entry deleted | `actor_id`, `org_unit_id` |
| `FinanceEntryVerified` | Finance entry verified | `actor_id`, `org_unit_id`, `entry_id` |
| `FinanceEntryReconciled` | Finance entry reconciled | `actor_id`, `org_unit_id`, `entry_id` |
| `FinanceBatchCreated` | Finance batch created | `actor_id`, `org_unit_id` |
| `FinanceBatchLocked` | Finance batch locked | `actor_id`, `org_unit_id` |
| `FinanceBatchUnlocked` | Finance batch unlocked | `actor_id`, `org_unit_id` |
| `FinanceBatchVerified` | Finance batch verified | `actor_id`, `org_unit_id`, `verification_number` |
| `FinanceFundCreated` | Fund created | `actor_id` |
| `FinancePartnershipCreated` | Partnership created | `actor_id` |

### Registry Metrics

| Metric Name | Description | Metadata |
|------------|-------------|----------|
| `PersonCreated` | Person record created | `actor_id`, `org_unit_id`, `entity_type` |
| `PersonUpdated` | Person record updated | `actor_id`, `org_unit_id`, `entity_type` |
| `PersonDeleted` | Person record deleted | `actor_id`, `org_unit_id`, `entity_type` |
| `PersonMerged` | Person records merged | `actor_id`, `org_unit_id` |
| `FirstTimerCreated` | First timer record created | `actor_id`, `org_unit_id` |
| `FirstTimerConverted` | First timer converted to member | `actor_id`, `org_unit_id` |
| `FirstTimerStatusChanged` | First-timer status changed | `actor_id`, `org_unit_id`, `old_status`, `new_status` |
| `AttendanceRecorded` | Attendance recorded | `actor_id`, `org_unit_id` |
| `DepartmentCreated` | Department created | `actor_id`, `org_unit_id` |
| `ServiceCreated` | Service created | `actor_id`, `org_unit_id` |

### Import Metrics

| Metric Name | Description | Metadata |
|------------|-------------|----------|
| `ImportStarted` | Import job started | `user_id`, `entity_type` |
| `ImportCompleted` | Import job completed | `user_id`, `entity_type`, `rows_processed` |
| `ImportFailed` | Import job failed | `user_id`, `entity_type` |
| `ImportRowsProcessed` | Rows processed in import | `user_id`, `entity_type`, `rows_processed` |
| `ImportValidationError` | Import validation failed | `user_id`, `entity_type`, `row_number`, `error_type` |

### IAM Metrics

| Metric Name | Description | Metadata |
|------------|-------------|----------|
| `RoleCreated` | Role created | `actor_id` |
| `RoleUpdated` | Role updated | `actor_id` |
| `RoleDeleted` | Role deleted | `actor_id` |
| `PermissionAssigned` | Permission assigned to role | `actor_id`, `role_id` |
| `AssignmentCreated` | Org assignment created | `actor_id`, `user_id`, `role_id` |
| `AssignmentUpdated` | Org assignment updated | `actor_id`, `assignment_id` |
| `AssignmentDeleted` | Org assignment deleted | `actor_id`, `assignment_id` |
| `OrgUnitCreated` | Org unit created | `actor_id` |
| `OrgUnitUpdated` | Org unit updated | `actor_id` |
| `OrgUnitDeleted` | Org unit deleted | `actor_id` |

### Data Quality Metrics

| Metric Name | Description | Metadata |
|------------|-------------|----------|
| `ValidationError` | Validation failed | `entity_type`, `field`, `error_type` |
| `BusinessRuleViolation` | Business rule violated | `entity_type`, `rule_name`, `context` |
| `DuplicateDetected` | Duplicate record detected | `entity_type`, `match_type` |
| `DataMergeAttempted` | Merge operation attempted | `actor_id`, `entity_type`, `source_count` |

## Implementation Status

### ✅ Implemented
- User metrics: `UserCreated`, `UserUpdated`, `UserDisabled`, `UserEnabled`
- Report metrics: `ReportDashboardViewed`, `ReportQueryExecuted`, `ReportExportCreated`
- Cell metrics: `CellReportCreated`

### 📝 To Be Implemented
- Remaining user metrics (login, logout, password operations)
- Remaining report metrics (templates, schedules)
- All finance metrics
- All registry metrics
- All import metrics
- All IAM metrics

## Adding New Metrics

1. Add metric name to `BusinessMetric` class in `app/core/business_metrics.py`
2. Use appropriate `MetricsService` helper method
3. Update this documentation
4. Emit metric in relevant service/route handler

## Best Practices

1. **Always use MetricsService**: Don't call `emit_business_metric` directly
2. **Use BusinessMetric enum**: Prevents typos and ensures consistency
3. **Include relevant metadata**: Add context that helps with analysis
4. **Emit on success**: Only emit metrics when operations succeed
5. **Don't break on failure**: Metric emission failures should not break requests

## Testing Metrics

**Do NOT emit real metrics in tests.** Instead, mock the metric emission functions:

```python
from unittest.mock import patch
from app.core.metrics_service import MetricsService

@patch("app.core.metrics_service.emit_business_metric")
def test_user_creation_emits_metric(mock_emit):
    """Test that user creation emits the correct metric."""
    # ... create user ...
    
    # Verify metric was emitted
    assert mock_emit.called
    call_args = mock_emit.call_args
    assert call_args[1]["metric_name"] == "UserCreated"
    assert call_args[1]["category"] == "user"
```

This approach:
- Prevents test metrics from polluting production metrics
- Keeps tests fast (no actual metric emission overhead)
- Allows verification that metrics are called correctly
- Follows the existing test pattern (see `tests/test_metrics_emission.py`)

