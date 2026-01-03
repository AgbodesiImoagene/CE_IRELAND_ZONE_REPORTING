"""Business metrics catalog with standardized naming.

This module defines all business metrics that can be emitted by the application.
Use the enum values to ensure consistent naming across the codebase.
"""

from enum import Enum


class MetricCategory(str, Enum):
    """Categories for grouping business metrics."""

    USER = "user"
    REPORT = "report"
    CELL = "cell"
    FINANCE = "finance"
    REGISTRY = "registry"
    IMPORT = "import"
    IAM = "iam"
    SECURITY = "security"
    DATA_QUALITY = "data_quality"


class BusinessMetric:
    """Catalog of all business metrics with standardized naming."""

    # User metrics
    USER_CREATED = "UserCreated"
    USER_UPDATED = "UserUpdated"
    USER_DISABLED = "UserDisabled"
    USER_ENABLED = "UserEnabled"
    USER_LOGIN = "UserLogin"
    USER_LOGOUT = "UserLogout"
    USER_PASSWORD_CHANGED = "UserPasswordChanged"
    USER_PASSWORD_RESET = "UserPasswordReset"
    USER_INVITATION_CREATED = "UserInvitationCreated"
    USER_INVITATION_ACCEPTED = "UserInvitationAccepted"

    # Security metrics
    USER_LOGIN_FAILED = "UserLoginFailed"
    USER_2FA_SENT = "User2FASent"
    USER_2FA_VERIFIED = "User2FAVerified"
    PERMISSION_DENIED = "PermissionDenied"
    OAUTH_LOGIN = "OAuthLogin"
    OAUTH_STARTED = "OAuthStarted"
    OAUTH_COMPLETED = "OAuthCompleted"
    OAUTH_FAILED = "OAuthFailed"

    # Report metrics
    REPORT_QUERY_EXECUTED = "ReportQueryExecuted"
    REPORT_EXPORT_CREATED = "ReportExportCreated"
    REPORT_EXPORT_COMPLETED = "ReportExportCompleted"
    REPORT_EXPORT_FAILED = "ReportExportFailed"
    REPORT_EXPORT_DOWNLOADED = "ReportExportDownloaded"
    REPORT_DASHBOARD_VIEWED = "ReportDashboardViewed"
    REPORT_TEMPLATE_CREATED = "ReportTemplateCreated"
    REPORT_SCHEDULE_CREATED = "ReportScheduleCreated"
    SEARCH_EXECUTED = "SearchExecuted"
    FILTER_APPLIED = "FilterApplied"

    # Cell metrics
    CELL_CREATED = "CellCreated"
    CELL_UPDATED = "CellUpdated"
    CELL_DELETED = "CellDeleted"
    CELL_REPORT_CREATED = "CellReportCreated"
    CELL_REPORT_UPDATED = "CellReportUpdated"
    CELL_REPORT_APPROVED = "CellReportApproved"
    CELL_REPORT_REVIEWED = "CellReportReviewed"
    CELL_REPORT_DELETED = "CellReportDeleted"

    # Finance metrics
    FINANCE_ENTRY_CREATED = "FinanceEntryCreated"
    FINANCE_ENTRY_UPDATED = "FinanceEntryUpdated"
    FINANCE_ENTRY_DELETED = "FinanceEntryDeleted"
    FINANCE_ENTRY_VERIFIED = "FinanceEntryVerified"
    FINANCE_ENTRY_RECONCILED = "FinanceEntryReconciled"
    FINANCE_BATCH_CREATED = "FinanceBatchCreated"
    FINANCE_BATCH_LOCKED = "FinanceBatchLocked"
    FINANCE_BATCH_UNLOCKED = "FinanceBatchUnlocked"
    FINANCE_BATCH_VERIFIED = "FinanceBatchVerified"
    FINANCE_FUND_CREATED = "FinanceFundCreated"
    FINANCE_PARTNERSHIP_CREATED = "FinancePartnershipCreated"

    # Registry metrics
    PERSON_CREATED = "PersonCreated"
    PERSON_UPDATED = "PersonUpdated"
    PERSON_DELETED = "PersonDeleted"
    PERSON_MERGED = "PersonMerged"
    FIRST_TIMER_CREATED = "FirstTimerCreated"
    FIRST_TIMER_CONVERTED = "FirstTimerConverted"
    FIRST_TIMER_STATUS_CHANGED = "FirstTimerStatusChanged"
    ATTENDANCE_RECORDED = "AttendanceRecorded"
    DEPARTMENT_CREATED = "DepartmentCreated"
    SERVICE_CREATED = "ServiceCreated"

    # Import metrics
    IMPORT_STARTED = "ImportStarted"
    IMPORT_COMPLETED = "ImportCompleted"
    IMPORT_FAILED = "ImportFailed"
    IMPORT_ROWS_PROCESSED = "ImportRowsProcessed"
    IMPORT_VALIDATION_ERROR = "ImportValidationError"

    # IAM metrics
    ROLE_CREATED = "RoleCreated"
    ROLE_UPDATED = "RoleUpdated"
    ROLE_DELETED = "RoleDeleted"
    PERMISSION_ASSIGNED = "PermissionAssigned"
    ASSIGNMENT_CREATED = "AssignmentCreated"
    ASSIGNMENT_UPDATED = "AssignmentUpdated"
    ASSIGNMENT_DELETED = "AssignmentDeleted"
    ORG_UNIT_CREATED = "OrgUnitCreated"
    ORG_UNIT_UPDATED = "OrgUnitUpdated"
    ORG_UNIT_DELETED = "OrgUnitDeleted"

    # Data Quality metrics
    VALIDATION_ERROR = "ValidationError"
    BUSINESS_RULE_VIOLATION = "BusinessRuleViolation"
    DUPLICATE_DETECTED = "DuplicateDetected"
    DATA_MERGE_ATTEMPTED = "DataMergeAttempted"

