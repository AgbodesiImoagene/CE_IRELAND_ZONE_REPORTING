"""Import service layer for file imports."""

from __future__ import annotations

import logging
from typing import Optional, Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from sqlalchemy import select

from app.common.audit import create_audit_log
from app.common.models import ImportJob, OrgAssignment
from app.imports.parsers import detect_file_format, get_parser, ImportFormat
from app.imports.mappers import auto_map_columns, suggest_mappings
from app.imports.validators import validate_business_rules
from app.imports.s3_utils import S3Client

logger = logging.getLogger(__name__)


class ImportService:
    """Service for managing import jobs."""

    @staticmethod
    def upload_file(
        db: Session,
        user_id: UUID,
        tenant_id: UUID,
        file_content: bytes,
        filename: str,
        entity_type: str,
        import_mode: str = "create_only",
    ) -> ImportJob:
        """
        Upload file and create import job.

        Args:
            db: Database session
            user_id: User ID
            tenant_id: Tenant ID
            file_content: File content as bytes
            filename: Original filename
            entity_type: Entity type (people, memberships, etc.)
            import_mode: Import mode (create_only, update_existing)

        Returns:
            Created ImportJob
        """
        # Detect file format
        file_format = detect_file_format(file_content, filename)
        if file_format == ImportFormat.UNKNOWN:
            raise ValueError(f"Unsupported file format: {filename}")

        # Upload to S3
        s3_client = S3Client()
        file_key = f"imports/{tenant_id}/{uuid4()}/{filename}"
        s3_client.upload_file(file_content, file_key)

        # Extract user's primary org_unit_id from their assignments
        default_org_unit_id = None
        assignment = db.execute(
            select(OrgAssignment)
            .where(
                OrgAssignment.user_id == user_id,
                OrgAssignment.tenant_id == tenant_id,
            )
            .limit(1)
        ).scalar_one_or_none()
        if assignment:
            default_org_unit_id = assignment.org_unit_id

        # Create import job
        job = ImportJob(
            id=uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            entity_type=entity_type,
            file_name=filename,
            file_format=file_format.value,
            file_path=file_key,
            file_size=len(file_content),
            status="pending",
            import_mode=import_mode,
            default_org_unit_id=default_org_unit_id,
        )
        db.add(job)
        db.flush()

        # Audit log
        create_audit_log(
            db,
            user_id,
            "create",
            "import_jobs",
            job.id,
            None,
            {
                "id": str(job.id),
                "entity_type": entity_type,
                "file_name": filename,
                "file_format": file_format.value,
                "file_size": len(file_content),
                "import_mode": import_mode,
            },
        )

        db.commit()
        db.refresh(job)

        return job

    @staticmethod
    def create_preview(
        db: Session,
        job_id: UUID,
        tenant_id: UUID,
        mapping_config: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Create preview with auto-mapped columns.

        Args:
            db: Database session
            job_id: Import job ID
            tenant_id: Tenant ID
            mapping_config: Optional manual mapping configuration

        Returns:
            Preview data with sample rows and mappings
        """
        job = db.get(ImportJob, job_id)
        if not job or job.tenant_id != tenant_id:
            raise ValueError(f"Import job {job_id} not found")

        # Download file from S3
        s3_client = S3Client()
        file_content = s3_client.download_file(job.file_path)

        # Parse file
        parser = get_parser(ImportFormat(job.file_format))
        headers = parser.parse_headers(file_content)
        total_rows = parser.get_row_count(file_content)

        # Auto-map columns if no mapping provided
        if not mapping_config:
            auto_mappings = auto_map_columns(headers, job.entity_type)
            mapping_config = {
                source: {
                    "target_field": mapping.target_field,
                    "coercion_type": None,
                    "required": mapping.required,
                }
                for source, mapping in auto_mappings.items()
            }
            # Build mapping_dict from ColumnMapping objects
            mapping_dict = {
                source: mapping.target_field
                for source, mapping in auto_mappings.items()
            }
        else:
            # Convert mapping config to dict format
            # mapping_config values are dicts with "target_field" key
            mapping_dict = {}
            for source, mapping in mapping_config.items():
                if isinstance(mapping, dict):
                    mapping_dict[source] = mapping.get("target_field")
                elif hasattr(mapping, "target_field"):
                    mapping_dict[source] = mapping.target_field

        # Parse sample rows (first 10)
        sample_rows = []
        error_counts = {
            "required": 0,
            "coercion": 0,
            "reference": 0,
            "constraint": 0,
            "business": 0,
        }

        row_count = 0
        for row in parser.parse_rows(file_content, limit=10):
            row_count += 1
            row["_row_number"] = row_count

            # Apply mapping and coercion
            mapped_row = {}
            for source_col, target_field in mapping_dict.items():
                if source_col in row:
                    value = row[source_col]
                    # Get coercion type from mapping config if available
                    coercion_type = None
                    if mapping_config and source_col in mapping_config:
                        coercion_type = mapping_config[source_col].get("coercion_type")
                    
                    # Coerce value based on target field type or mapping config
                    if coercion_type:
                        from app.imports.coercers import coerce_value
                        coercion_hints = {}
                        # Handle enum coercion
                        if coercion_type == "enum":
                            from app.common.models import Gender, MaritalStatus, MembershipStatus, FirstTimerStatus
                            enum_map = {
                                "gender": Gender,
                                "marital_status": MaritalStatus,
                                "membership_status": MembershipStatus,
                                "first_timer_status": FirstTimerStatus,
                            }
                            if target_field in enum_map:
                                coercion_hints["enum_class"] = enum_map[target_field]
                        
                        result = coerce_value(value, coercion_type, coercion_hints)
                        if result.success:
                            mapped_row[target_field] = result.coerced_value
                        else:
                            mapped_row[target_field] = value  # Keep original on failure
                    else:
                        # Infer coercion type from target field name
                        if target_field in ["dob", "join_date", "baptism_date", "service_date"]:
                            from app.imports.coercers import coerce_value
                            result = coerce_value(value, "date")
                            mapped_row[target_field] = result.coerced_value if result.success else value
                        elif target_field == "email":
                            from app.imports.coercers import coerce_value
                            result = coerce_value(value, "email")
                            mapped_row[target_field] = result.coerced_value if result.success else value
                        elif target_field == "phone":
                            from app.imports.coercers import coerce_value
                            result = coerce_value(value, "phone")
                            mapped_row[target_field] = result.coerced_value if result.success else value
                        elif target_field == "gender":
                            from app.imports.coercers import coerce_value
                            from app.common.models import Gender
                            result = coerce_value(value, "enum", {"enum_class": Gender})
                            mapped_row[target_field] = result.coerced_value if result.success else value
                        elif target_field == "marital_status":
                            from app.imports.coercers import coerce_value
                            from app.common.models import MaritalStatus
                            result = coerce_value(value, "enum", {"enum_class": MaritalStatus})
                            mapped_row[target_field] = result.coerced_value if result.success else value
                        else:
                            mapped_row[target_field] = value

            sample_rows.append(mapped_row)

        # Get mapping suggestions
        suggestions = suggest_mappings(headers, job.entity_type)

        # Update job
        job.status = "previewing"
        job.mapping_config = mapping_config
        job.total_rows = total_rows
        db.commit()

        return {
            "job_id": job_id,
            "total_rows": total_rows,
            "sample_rows": sample_rows,
            "mapping_suggestions": suggestions,
            "validation_summary": error_counts,
            "warnings": [],
        }

    @staticmethod
    def update_mapping(
        db: Session,
        job_id: UUID,
        tenant_id: UUID,
        mapping_config: dict[str, Any],
    ) -> ImportJob:
        """
        Update column mapping configuration.

        Args:
            db: Database session
            job_id: Import job ID
            tenant_id: Tenant ID
            mapping_config: Updated mapping configuration

        Returns:
            Updated ImportJob
        """
        job = db.get(ImportJob, job_id)
        if not job or job.tenant_id != tenant_id:
            raise ValueError(f"Import job {job_id} not found")

        job.mapping_config = mapping_config
        job.status = "mapping"
        db.commit()
        db.refresh(job)

        return job

    @staticmethod
    def validate_preview(
        db: Session, job_id: UUID, tenant_id: UUID
    ) -> dict[str, Any]:
        """
        Validate all rows in the import file.

        Args:
            db: Database session
            job_id: Import job ID
            tenant_id: Tenant ID

        Returns:
            Validation results
        """
        job = db.get(ImportJob, job_id)
        if not job or job.tenant_id != tenant_id:
            raise ValueError(f"Import job {job_id} not found")

        if not job.mapping_config:
            raise ValueError("Mapping configuration not set")

        # Download file from S3
        s3_client = S3Client()
        file_content = s3_client.download_file(job.file_path)

        # Parse file
        parser = get_parser(ImportFormat(job.file_format))
        all_errors = []
        error_counts = {
            "required": 0,
            "coercion": 0,
            "reference": 0,
            "constraint": 0,
            "business": 0,
        }

        # Build mapping dict
        mapping_dict = {
            source: config.get("target_field")
            for source, config in job.mapping_config.items()
        }

        row_count = 0
        for row in parser.parse_rows(file_content):
            row_count += 1
            row["_row_number"] = row_count

            # Apply mapping
            mapped_row = {}
            for source_col, target_field in mapping_dict.items():
                if source_col in row:
                    mapped_row[target_field] = row[source_col]

            # Validate business rules
            business_errors = validate_business_rules(job.entity_type, mapped_row)
            all_errors.extend(business_errors)
            for error in business_errors:
                error_counts[error.error_type] = error_counts.get(
                    error.error_type, 0
                ) + 1

            if len(all_errors) >= 100:  # Limit to first 100 errors
                break

        # Update job
        job.status = "validating"
        job.validation_errors = [error.__dict__ for error in all_errors[:100]]
        db.commit()

        return {
            "job_id": job_id,
            "total_errors": len(all_errors),
            "errors_by_type": error_counts,
            "sample_errors": [
                {
                    "row_number": e.row_number,
                    "field": e.field,
                    "error_type": e.error_type,
                    "message": e.message,
                    "original_value": e.original_value,
                    "suggestion": e.suggestion,
                }
                for e in all_errors[:100]
            ],
        }

    @staticmethod
    def get_job_status(
        db: Session, job_id: UUID, tenant_id: UUID
    ) -> Optional[ImportJob]:
        """Get import job status."""
        job = db.get(ImportJob, job_id)
        if not job or job.tenant_id != tenant_id:
            return None
        return job

    @staticmethod
    def download_error_report(
        db: Session, job_id: UUID, tenant_id: UUID
    ) -> Optional[bytes]:
        """Download error report CSV."""
        job = db.get(ImportJob, job_id)
        if not job or job.tenant_id != tenant_id:
            return None

        if not job.error_file_path:
            return None

        s3_client = S3Client()
        return s3_client.download_file(job.error_file_path)

