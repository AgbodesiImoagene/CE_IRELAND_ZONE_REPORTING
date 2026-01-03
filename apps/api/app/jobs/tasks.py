"""Background job tasks for email/SMS delivery and notification processing."""

from __future__ import annotations

import csv
import logging
from datetime import datetime, timedelta, timezone
from io import StringIO
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.db import SessionLocal
from app.common.models import OutboxNotification, UserSecret, User, ImportJob, ImportError
from app.core.business_metrics import BusinessMetric
from app.core.config import settings
from app.core.metrics_service import MetricsService
from app.imports.parsers import get_parser, ImportFormat
from app.imports.s3_utils import S3Client
from app.jobs.notifications import enqueue_email_notification
from app.jobs.queue import emails_queue, sms_queue, exports_queue

logger = logging.getLogger(__name__)


def _get_notification_queue(notification: OutboxNotification):
    """
    Determine the correct queue for a notification based on its type and delivery method.

    Args:
        notification: OutboxNotification instance

    Returns:
        Queue instance (emails_queue or sms_queue)
    """
    if notification.type == "2fa_code":
        payload = notification.payload
        delivery_method = payload.get("delivery_method", "email")
        return sms_queue if delivery_method == "sms" else emails_queue
    else:
        # Most notifications are emails (invitations, etc.)
        return emails_queue


def _schedule_retry(notification: OutboxNotification, db: Session) -> bool:
    """
    Schedule a retry for a failed notification with exponential backoff.

    Args:
        notification: OutboxNotification instance that failed
        db: Database session

    Returns:
        True if retry was scheduled, False if max retries reached
    """
    max_retries = settings.max_notification_retries

    if notification.retry_count >= max_retries:
        logger.warning(
            f"Notification {notification.id} exceeded max retries ({max_retries})"
        )
        notification.delivery_state = "failed"
        notification.last_error = (
            f"Delivery failed after {notification.retry_count} retries"
        )
        db.commit()
        return False

    # Calculate exponential backoff: 2^retry_count seconds
    # First retry: 1s, second: 2s, third: 4s, etc.
    delay_seconds = 2 ** (notification.retry_count)

    # Increment retry count
    notification.retry_count += 1

    # Keep as pending so it can be retried
    notification.delivery_state = "pending"
    notification.last_error = (
        f"Scheduling retry {notification.retry_count}/{max_retries} "
        f"in {delay_seconds}s"
    )
    db.commit()

    # Determine correct queue
    queue = _get_notification_queue(notification)

    # Schedule retry with exponential backoff
    try:
        queue.enqueue_in(
            timedelta(seconds=delay_seconds),
            "app.jobs.tasks.process_outbox_notification",
            str(notification.id),
            job_id=f"{notification.id}-retry-{notification.retry_count}",
        )
        logger.info(
            f"Scheduled retry {notification.retry_count}/{max_retries} for "
            f"notification {notification.id} in {delay_seconds}s"
        )
        return True
    except Exception as e:
        logger.error(
            f"Failed to schedule retry for notification {notification.id}: {str(e)}",
            exc_info=True,
        )
        # If scheduling fails, mark as failed
        notification.delivery_state = "failed"
        notification.last_error = f"Failed to schedule retry: {str(e)}"
        db.commit()
        return False


def send_email(
    to_email: str, subject: str, body: str, html_body: str | None = None
) -> bool:
    """
    Send an email.

    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Plain text email body
        html_body: Optional HTML email body

    Returns:
        True if sent successfully, False otherwise
    """
    try:
        # For development: print to console if SMTP not configured
        if not settings.smtp_host or settings.smtp_host == "localhost":
            logger.info(f"[DEV] Email to {to_email}: {subject}")
            logger.info(f"[DEV] Body: {body}")
            return True

        # Import here to avoid dependency if not using emails
        # Import at top level for better testability
        import smtplib  # noqa: PLC0415
        from email.mime.text import MIMEText  # noqa: PLC0415
        from email.mime.multipart import MIMEMultipart  # noqa: PLC0415

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        from_addr = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
        msg["From"] = from_addr
        msg["To"] = to_email

        # Add plain text and HTML parts
        text_part = MIMEText(body, "plain")
        msg.attach(text_part)

        if html_body:
            html_part = MIMEText(html_body, "html")
            msg.attach(html_part)

        # Send email
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)

        logger.info(f"Email sent to {to_email}: {subject}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}", exc_info=True)
        return False


def send_sms(to_number: str, message: str) -> bool:
    """
    Send an SMS message.

    Args:
        to_number: Recipient phone number
        message: SMS message text

    Returns:
        True if sent successfully, False otherwise

    Note:
        Currently prints to console in dev mode.
        Implement actual SMS provider integration (Twilio, AWS SNS, etc.) for production.
    """
    try:
        # For development: print to console
        logger.info(f"[DEV] SMS to {to_number}: {message}")

        # TODO: Implement actual SMS provider integration
        # if settings.sms_provider == "twilio":
        #     # Twilio implementation
        #     pass
        # elif settings.sms_provider == "aws-sns":
        #     # AWS SNS implementation
        #     pass

        return True

    except Exception as e:
        logger.error(f"Failed to send SMS to {to_number}: {str(e)}", exc_info=True)
        return False


def process_outbox_notification(notification_id: str) -> bool:
    """
    Process a single outbox notification (email or SMS delivery).

    Args:
        notification_id: UUID of the outbox notification

    Returns:
        True if processed successfully, False otherwise
    """
    db = SessionLocal()  # type: ignore
    try:
        notification = db.execute(
            select(OutboxNotification).where(
                OutboxNotification.id == UUID(notification_id)
            )
        ).scalar_one_or_none()

        if not notification:
            logger.warning(f"Notification {notification_id} not found")
            return False

        if notification.delivery_state != "pending":
            logger.info(f"Notification {notification_id} already processed")
            return True

        # Process based on notification type
        success = False
        if notification.type == "user_invitation":
            success = _process_invitation_notification(db, notification)
        elif notification.type == "2fa_code":
            success = _process_2fa_notification(db, notification)
            if success:
                # Look up user by email from payload to update UserSecret
                payload = notification.payload
                email = payload.get("email")
                if email:
                    user = db.execute(
                        select(User).where(User.email == email.lower())
                    ).scalar_one_or_none()
                    if user:
                        secret = db.execute(
                            select(UserSecret).where(
                                UserSecret.user_id == user.id
                            )
                        ).scalar_one_or_none()
                        if secret:
                            secret.sent_at = datetime.now(timezone.utc)
                            db.commit()
        else:
            logger.warning(f"Unknown notification type: {notification.type}")
            notification.delivery_state = "failed"
            notification.last_error = f"Unknown notification type: {notification.type}"
            db.commit()
            return False

        # Update notification state
        if success:
            notification.delivery_state = "sent"
            notification.sent_at = datetime.now(timezone.utc)
            notification.last_error = None
            db.commit()
            return True
        else:
            # Delivery failed - attempt retry with exponential backoff
            logger.warning(
                f"Delivery failed for notification {notification_id} "
                f"(attempt {notification.retry_count + 1})"
            )
            retry_scheduled = _schedule_retry(notification, db)
            if retry_scheduled:
                # Retry was scheduled successfully
                return False  # Current attempt failed, but retry is scheduled
            else:
                # Max retries exceeded or scheduling failed
                return False

    except Exception as e:
        logger.error(
            f"Failed to process notification {notification_id}: {str(e)}",
            exc_info=True,
        )
        if db:
            try:
                notification = db.execute(
                    select(OutboxNotification).where(
                        OutboxNotification.id == UUID(notification_id)
                    )
                ).scalar_one_or_none()
                if notification:
                    # Try to schedule a retry for exceptions too
                    retry_scheduled = _schedule_retry(notification, db)
                    if not retry_scheduled:
                        # Max retries exceeded, mark as failed
                        notification.delivery_state = "failed"
                        notification.last_error = str(e)
                        db.commit()
            except Exception as inner_e:
                logger.error(
                    f"Failed to update notification {notification_id} "
                    f"after exception: {str(inner_e)}",
                    exc_info=True,
                )
        return False

    finally:
        db.close()


def _process_invitation_notification(
    db: Session, notification: OutboxNotification
) -> bool:  # noqa: ARG001
    """Process user invitation notification."""
    payload = notification.payload
    email = payload.get("email")
    token = payload.get("token")
    expires_at = payload.get("expires_at")

    if not email or not token:
        logger.error("Missing email or token in invitation notification")
        return False

    # Generate invitation email
    base_url = settings.oauth_redirect_base_url.replace("/oauth", "")
    activation_url = f"{base_url}/users/activate?token={token}"
    subject = f"You've been invited to join {settings.tenant_name}"
    body = f"""
You have been invited to join the {settings.tenant_name} reporting platform.

Click the link below to activate your account:
{activation_url}

This invitation expires on {expires_at}.

If you did not expect this invitation, please ignore this email.
"""

    html_body = f"""
<html>
<body>
    <h2>You've been invited!</h2>
    <p>You have been invited to join the {settings.tenant_name} reporting platform.</p>
    <p><a href="{activation_url}">Activate your account</a></p>
    <p>This invitation expires on {expires_at}.</p>
    <p>If you did not expect this invitation, please ignore this email.</p>
</body>
</html>
"""

    return send_email(email, subject, body, html_body)


def _process_2fa_notification(
    db: Session, notification: OutboxNotification
) -> bool:  # noqa: ARG001
    """Process 2FA code notification."""
    payload = notification.payload
    email = payload.get("email")
    phone = payload.get("phone")
    code = payload.get("code")
    delivery_method = payload.get("delivery_method", "email")

    if not code:
        logger.error("Missing 2FA code in notification")
        return False

    if delivery_method == "email":
        if not email:
            logger.error("Missing email for 2FA delivery")
            return False

        subject = "Your 2FA code"
        body = (
            f"Your verification code is: {code}\n\nThis code will expire in 5 minutes."
        )

        return send_email(email, subject, body)

    elif delivery_method == "sms":
        if not phone:
            logger.error("Missing phone number for SMS delivery")
            return False

        message = f"Your verification code is: {code}. Expires in 5 minutes."
        return send_sms(phone, message)

    else:
        logger.error(f"Unknown delivery method: {delivery_method}")
        return False


def process_import_job(job_id: str) -> None:
    """
    Process import job asynchronously.

    Args:
        job_id: Import job ID as string
    """
    db: Session = SessionLocal()
    try:
        job_uuid = UUID(job_id)
        job = db.get(ImportJob, job_uuid)
        if not job:
            logger.error(f"Import job {job_id} not found")
            return

        # Update status to processing
        job.status = "processing"
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        # Download file from S3
        s3_client = S3Client()
        file_content = s3_client.download_file(job.file_path)

        # Parse file
        parser = get_parser(ImportFormat(job.file_format))
        mapping_dict = {
            source: config.get("target_field")
            for source, config in job.mapping_config.items()
        }

        # Get processor (lazy import to avoid circular dependency)
        from app.imports.processors import get_processor
        processor = get_processor(job.entity_type)

        # Get default org_unit_id from job
        org_unit_id = job.default_org_unit_id

        # Process rows
        imported_count = 0
        error_count = 0
        skipped_count = 0
        error_rows = []

        row_count = 0
        for row in parser.parse_rows(file_content):
            row_count += 1
            row["_row_number"] = row_count

            # Apply mapping
            mapped_row = {}
            for source_col, target_field in mapping_dict.items():
                if source_col in row:
                    mapped_row[target_field] = row[source_col]

            # Extract org_unit_id for this row if present
            row_org_unit_id = org_unit_id  # Default to job's org_unit_id
            if "org_unit_id" in mapped_row and mapped_row["org_unit_id"]:
                try:
                    row_org_unit_id = UUID(str(mapped_row["org_unit_id"]))
                except (ValueError, TypeError):
                    # Invalid UUID format - will be caught by validation
                    row_org_unit_id = None

            # Check if org_unit_id is required but not available
            if not row_org_unit_id and processor.requires_org_unit():
                error_count += 1
                error_rows.append(
                    {
                        "row_number": row_count,
                        "errors": [
                            {
                                "field": "org_unit_id",
                                "error_type": "required",
                                "message": "org_unit_id is required but not provided",
                                "original_value": None,
                            }
                        ],
                    }
                )
                # Store error in database (only if not dry run)
                if not job.dry_run:
                    import_error = ImportError(
                        import_job_id=job.id,
                        row_number=row_count,
                        column_name="org_unit_id",
                        error_type="required",
                        error_message="org_unit_id is required but not provided",
                        original_value=None,
                        suggested_value=None,
                    )
                    db.add(import_error)
                continue

            # Process row
            try:
                result = processor.process_row(
                    db=db,
                    row=mapped_row,
                    mapping=mapping_dict,
                    mode=job.import_mode,
                    tenant_id=job.tenant_id,
                    user_id=job.user_id,
                    org_unit_id=row_org_unit_id,
                )

                if result.success:
                    if not job.dry_run:
                        imported_count += 1
                    else:
                        # In dry run, count as validated
                        skipped_count += 1
                else:
                    error_count += 1
                    error_rows.append(
                        {
                            "row_number": row_count,
                            "errors": [
                                {
                                    "field": e.field,
                                    "error_type": e.error_type,
                                    "message": e.message,
                                    "original_value": e.original_value,
                                }
                                for e in result.errors
                            ],
                        }
                    )

                    # Store errors in database (only if not dry run)
                    if not job.dry_run:
                        for error in result.errors:
                            import_error = ImportError(
                                import_job_id=job.id,
                                row_number=error.row_number,
                                column_name=error.field,
                                error_type=error.error_type,
                                error_message=error.message,
                                original_value=str(error.original_value) if error.original_value else None,
                                suggested_value=error.suggestion,
                            )
                            db.add(import_error)

            except Exception as e:
                logger.error(f"Error processing row {row_count}: {e}", exc_info=True)
                error_count += 1
                error_rows.append(
                    {
                        "row_number": row_count,
                        "errors": [
                            {
                                "field": "general",
                                "error_type": "processing",
                                "message": str(e),
                                "original_value": None,
                            }
                        ],
                    }
                )

            # Update progress every 100 rows (only commit if not dry run)
            if row_count % 100 == 0:
                if not job.dry_run:
                    job.processed_rows = row_count
                    job.imported_count = imported_count
                    job.error_count = error_count
                    db.commit()
                # In dry run, just track in memory - will update at end

        # Generate error report CSV
        error_file_path = None
        if error_rows:
            error_csv = StringIO()
            writer = csv.DictWriter(
                error_csv,
                fieldnames=[
                    "row_number",
                    "column_name",
                    "error_type",
                    "error_message",
                    "original_value",
                    "suggested_value",
                ],
            )
            writer.writeheader()
            for error_row in error_rows:
                for error in error_row["errors"]:
                    writer.writerow(
                        {
                            "row_number": error_row["row_number"],
                            "column_name": error.get("field", ""),
                            "error_type": error.get("error_type", ""),
                            "error_message": error.get("message", ""),
                            "original_value": str(error.get("original_value", "")),
                            "suggested_value": error.get("suggestion", ""),
                        }
                    )

            # Upload error report to S3
            error_file_key = f"imports/{job.tenant_id}/{job.id}/errors.csv"
            s3_client.upload_file(
                error_csv.getvalue().encode("utf-8"),
                error_file_key,
                content_type="text/csv",
            )
            error_file_path = error_file_key

        # Update job status
        job.processed_rows = row_count
        job.imported_count = imported_count if not job.dry_run else 0
        job.error_count = error_count
        job.skipped_count = skipped_count
        job.error_file_path = error_file_path
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        job.validation_errors = [
            {
                "row_number": er["row_number"],
                "errors": er["errors"],
            }
            for er in error_rows[:100]
        ]

        if job.dry_run:
            # Rollback all changes in dry run mode
            db.rollback()
            # Re-fetch job and update status only
            job = db.get(ImportJob, job_uuid)
            if job:
                job.processed_rows = row_count
                job.imported_count = 0
                job.error_count = error_count
                job.skipped_count = skipped_count
                job.error_file_path = error_file_path
                job.status = "completed"
                job.completed_at = datetime.now(timezone.utc)
                job.validation_errors = [
                    {
                        "row_number": er["row_number"],
                        "errors": er["errors"],
                    }
                    for er in error_rows[:100]
                ]
                db.commit()
        else:
            db.commit()

        logger.info(
            f"Import job {job_id} completed: {imported_count} imported, {error_count} errors"
        )

        # Emit business metrics
        try:
            MetricsService.emit_import_metric(
                metric_name=BusinessMetric.IMPORT_COMPLETED,
                tenant_id=job.tenant_id,
                user_id=job.user_id,
                entity_type=job.entity_type,
                rows_processed=row_count,
                imported_count=imported_count if not job.dry_run else 0,
                error_count=error_count,
                dry_run=job.dry_run,
            )
            if error_count > 0:
                MetricsService.emit_import_metric(
                    metric_name=BusinessMetric.IMPORT_VALIDATION_ERROR,
                    tenant_id=job.tenant_id,
                    user_id=job.user_id,
                    entity_type=job.entity_type,
                    error_count=error_count,
                )
        except Exception as e:
            logger.warning(f"Failed to emit import completion metrics: {e}")

        # Send email notification
        try:
            user = db.get(User, job.user_id)
            if user and user.email:
                subject = f"Import Job {job_id} Completed"
                mode_text = " (Dry Run)" if job.dry_run else ""
                body = f"""
Your import job has completed{mode_text}.

Job ID: {job_id}
Entity Type: {job.entity_type}
File: {job.file_name}

Results:
- Total Rows: {row_count}
- Imported: {imported_count if not job.dry_run else 0}
- Errors: {error_count}
- Skipped: {skipped_count}

Status: {"Success" if error_count == 0 else "Completed with errors"}
"""
                if error_count > 0:
                    body += f"\nYou can download the error report from the import job details page."

                enqueue_email_notification(
                    db=db,
                    email=user.email,
                    subject=subject,
                    body=body,
                )
        except Exception as e:
            logger.error(f"Failed to send import completion email: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Failed to process import job {job_id}: {e}", exc_info=True)
        # Update job status to failed
        try:
            job = db.get(ImportJob, UUID(job_id))
            if job:
                job.status = "failed"
                job.completed_at = datetime.now(timezone.utc)
                db.commit()

                # Emit business metric for failure
                try:
                    MetricsService.emit_import_metric(
                        metric_name=BusinessMetric.IMPORT_FAILED,
                        tenant_id=job.tenant_id,
                        user_id=job.user_id,
                        entity_type=job.entity_type,
                        error_message=str(e)[:200],  # Truncate long error messages
                    )
                except Exception as metric_error:
                    logger.warning(f"Failed to emit import failure metric: {metric_error}")
        except Exception:
            pass
    finally:
        db.close()


def process_export_job(export_id: str) -> None:
    """
    Process export job asynchronously.

    Args:
        export_id: Export job ID as string
    """
    db: Session = SessionLocal()
    try:
        from app.reports.models import ExportJob
        from app.reports.service import ReportService
        from app.reports.export_generators import CSVGenerator, ExcelGenerator
        from app.reports.pdf_generator import PDFReportGenerator

        export_uuid = UUID(export_id)
        job = db.get(ExportJob, export_uuid)
        if not job:
            logger.error(f"Export job {export_id} not found")
            return

        # Update status to processing
        job.status = "processing"
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        try:
            # Execute query
            result = ReportService.execute_query(
                db=db,
                tenant_id=job.tenant_id,
                user_id=job.user_id,
                query_request=job.query_definition,
            )

            results = result.get("results", [])
            total_rows = len(results)
            
            # Update progress: query completed
            job.total_rows = total_rows
            job.processed_rows = 0
            db.commit()
            db.refresh(job)

            # Generate file based on format
            file_content = None
            content_type = None
            file_extension = ""

            if job.format == "csv":
                # For CSV, we can track progress during generation for large datasets
                # For now, mark as processing
                job.processed_rows = total_rows // 2  # 50% progress
                db.commit()
                file_content = CSVGenerator.generate(results)
                job.processed_rows = total_rows  # 100% progress
                db.commit()
                content_type = "text/csv"
                file_extension = ".csv"
            elif job.format == "excel" or job.format == "xlsx":
                job.processed_rows = total_rows // 2  # 50% progress
                db.commit()
                file_content = ExcelGenerator.generate(results)
                job.processed_rows = total_rows  # 100% progress
                db.commit()
                content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                file_extension = ".xlsx"
            elif job.format == "pdf":
                # Get template if available
                template = None
                if job.template_id:
                    from app.reports.models import ReportTemplate
                    template = db.get(ReportTemplate, job.template_id)

                job.processed_rows = total_rows // 3  # 33% progress
                db.commit()
                pdf_gen = PDFReportGenerator()
                file_content = pdf_gen.generate(
                    results=results,
                    template_config={"name": "Export Report"} if template else None,
                    visualization_config=template.visualization_config if template else None,
                    pdf_config=template.pdf_config if template else None,
                )
                job.processed_rows = total_rows  # 100% progress
                db.commit()
                content_type = "application/pdf"
                file_extension = ".pdf"
            else:
                raise ValueError(f"Unsupported export format: {job.format}")

            # Upload to S3
            file_key = f"exports/{job.tenant_id}/{job.id}/export{file_extension}"
            s3_client = S3Client()
            s3_client.upload_file(file_content, file_key, content_type=content_type)

            # Update job status
            job.status = "completed"
            job.file_path = file_key
            job.file_size = len(file_content)
            job.completed_at = datetime.now(timezone.utc)
            db.commit()

            # Emit business metric for completion
            try:
                MetricsService.emit_report_metric(
                    metric_name=BusinessMetric.REPORT_EXPORT_COMPLETED,
                    tenant_id=job.tenant_id,
                    user_id=job.user_id,
                    report_type=job.format,
                    total_rows=total_rows,
                    file_size=len(file_content),
                )
            except Exception as e:
                logger.warning(f"Failed to emit export completion metric: {e}")

            # Send email notification
            try:
                user = db.get(User, job.user_id)
                if user and user.email:
                    file_url = s3_client.get_presigned_url(file_key, expiration=604800)  # 7 days
                    subject = f"Export Job {export_id} Completed"
                    body = f"""
Your export job has completed.

Job ID: {export_id}
Format: {job.format}
File Size: {len(file_content) / 1024:.2f} KB

Download your file here (expires in 7 days):
{file_url}
"""
                    enqueue_email_notification(
                        db=db,
                        email=user.email,
                        subject=subject,
                        body=body,
                    )
            except Exception as e:
                logger.error(f"Failed to send export completion email: {e}", exc_info=True)

            logger.info(f"Export job {export_id} completed successfully")

        except Exception as e:
            logger.error(f"Failed to process export job {export_id}: {e}", exc_info=True)
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
            db.commit()

            # Emit business metric for failure
            try:
                MetricsService.emit_report_metric(
                    metric_name=BusinessMetric.REPORT_EXPORT_FAILED,
                    tenant_id=job.tenant_id,
                    user_id=job.user_id,
                    report_type=job.format,
                    error_message=str(e)[:200],  # Truncate long error messages
                )
            except Exception as metric_error:
                logger.warning(f"Failed to emit export failure metric: {metric_error}")

    except Exception as e:
        logger.error(f"Error processing export job {export_id}: {e}", exc_info=True)
        try:
            job = db.get(ExportJob, UUID(export_id))
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def process_scheduled_report(schedule_id: str) -> None:
    """
    Execute scheduled report and send via email.

    Args:
        schedule_id: Report schedule ID as string
    """
    db: Session = SessionLocal()
    try:
        from app.reports.models import ReportSchedule, ReportTemplate
        from app.reports.service import ReportService
        from app.reports.pdf_generator import PDFReportGenerator

        schedule_uuid = UUID(schedule_id)
        schedule = db.get(ReportSchedule, schedule_uuid)
        if not schedule:
            logger.error(f"Schedule {schedule_id} not found")
            return

        if not schedule.is_active:
            logger.info(f"Schedule {schedule_id} is not active, skipping")
            return

        # Get template
        template = db.get(ReportTemplate, schedule.template_id)
        if not template:
            logger.error(f"Template {schedule.template_id} not found for schedule {schedule_id}")
            schedule.is_active = False
            db.commit()
            return

        # Apply query overrides if provided
        query_definition = template.query_definition.copy()
        if schedule.query_overrides:
            query_definition.update(schedule.query_overrides)

        # Execute query
        result = ReportService.execute_query(
            db=db,
            tenant_id=schedule.tenant_id,
            user_id=schedule.user_id,
            query_request=query_definition,
        )

        results = result.get("results", [])

        # Generate PDF
        pdf_gen = PDFReportGenerator()
        file_content = pdf_gen.generate(
            results=results,
            template_config={"name": template.name, "description": template.description},
            visualization_config=template.visualization_config,
            pdf_config=template.pdf_config,
        )

        filename = f"{template.name}_{datetime.now().strftime('%Y%m%d')}.pdf"
        content_type = "application/pdf"

        # Upload to S3
        file_key = f"scheduled_reports/{schedule.tenant_id}/{schedule.id}/{filename}"
        s3_client = S3Client()
        s3_client.upload_file(file_content, file_key, content_type=content_type)

        # Generate presigned URL
        file_url = s3_client.get_presigned_url(file_key, expiration=604800)  # 7 days

        # Send email to recipients
        subject = f"Scheduled Report: {template.name}"
        body = f"""
Your scheduled report has been generated.

Report: {template.name}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Download your report here (expires in 7 days):
{file_url}
"""

        for recipient in schedule.recipients:
            try:
                enqueue_email_notification(
                    db=db,
                    email=recipient,
                    subject=subject,
                    body=body,
                )
            except Exception as e:
                logger.error(f"Failed to send scheduled report email to {recipient}: {e}", exc_info=True)

        # Update schedule
        schedule.last_run_at = datetime.now(timezone.utc)
        # Calculate next run
        from app.reports.service import _calculate_next_run
        schedule.next_run_at = _calculate_next_run(
            schedule.frequency,
            schedule.time,
            schedule.day_of_week,
            schedule.day_of_month,
        )
        db.commit()

        # Audit log
        from app.common.audit import create_audit_log
        create_audit_log(
            db,
            schedule.user_id,
            "report.schedule.execute",
            "report_schedules",
            schedule.id,
            None,
            {"template_id": str(template.id), "recipients": schedule.recipients},
        )

        logger.info(f"Scheduled report {schedule_id} executed and sent to {len(schedule.recipients)} recipients")

    except Exception as e:
        logger.error(f"Failed to process scheduled report {schedule_id}: {e}", exc_info=True)
        try:
            schedule = db.get(ReportSchedule, UUID(schedule_id))
            if schedule:
                schedule.is_active = False
                db.commit()
        except Exception:
            pass
    finally:
        db.close()
