"""Models package - exports all models for backward compatibility.

This module maintains backward compatibility by re-exporting all models
from the split model files. Existing imports like:
    from app.common.models import User, People, Base
will continue to work.

Models are organized into:
- base: Base class, metadata, and enums
- iam: Identity and Access Management models
- registry: Registry domain models (people, services, attendance, etc.)
- finance: Finance domain models (funds, batches, entries, partnerships, etc.)
- cells: Cells domain models (cells, cell reports)
"""

from __future__ import annotations

# Export Base and metadata first (required by other models)
from app.common.models.base import (
    Base,
    metadata,
    NAMING_CONVENTION,
    # Enums
    OrgUnitType,
    ScopeType,
    TwoFADelivery,
    Gender,
    MaritalStatus,
    MembershipStatus,
    FirstTimerStatus,
    ServiceType,
    DepartmentRoleEnum,
    # Finance Enums
    PaymentMethod,
    VerifiedStatus,
    BatchStatus,
    PartnershipCadence,
    PartnershipStatus,
    SourceType,
    # Cells Enums
    MeetingDay,
    MeetingType,
    CellReportStatus,
)

# Export IAM models
from app.common.models.iam import (
    User,
    Role,
    Permission,
    RolePermission,
    OrgUnit,
    OrgAssignment,
    OrgAssignmentUnit,
    UserIdentity,
    UserSecret,
    LoginSession,
    OutboxNotification,
    UserInvitation,
    UserInvitationUnit,
    AuditLog,
)

# Export Registry models
from app.common.models.registry import (
    People,
    Membership,
    FirstTimer,
    Service,
    Attendance,
    Department,
    DepartmentRole,
)

# Export Finance models
from app.common.models.finance import (
    Fund,
    PartnershipArm,
    Batch,
    FinanceEntry,
    Partnership,
)

# Export Cells models
from app.common.models.cells import (
    Cell,
    CellReport,
)

# Make everything available for backward compatibility
__all__ = [
    # Base
    "Base",
    "metadata",
    "NAMING_CONVENTION",
    # Enums
    "OrgUnitType",
    "ScopeType",
    "TwoFADelivery",
    "Gender",
    "MaritalStatus",
    "MembershipStatus",
    "FirstTimerStatus",
    "ServiceType",
    "DepartmentRoleEnum",
    # Finance Enums
    "PaymentMethod",
    "VerifiedStatus",
    "BatchStatus",
    "PartnershipCadence",
    "PartnershipStatus",
    "SourceType",
    # Cells Enums
    "MeetingDay",
    "MeetingType",
    "CellReportStatus",
    # IAM models
    "User",
    "Role",
    "Permission",
    "RolePermission",
    "OrgUnit",
    "OrgAssignment",
    "OrgAssignmentUnit",
    "UserIdentity",
    "UserSecret",
    "LoginSession",
    "OutboxNotification",
    "UserInvitation",
    "UserInvitationUnit",
    "AuditLog",
    # Registry models
    "People",
    "Membership",
    "FirstTimer",
    "Service",
    "Attendance",
    "Department",
    "DepartmentRole",
    # Finance models
    "Fund",
    "PartnershipArm",
    "Batch",
    "FinanceEntry",
    "Partnership",
    # Cells models
    "Cell",
    "CellReport",
]

