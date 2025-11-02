"""Background job tasks for email/SMS delivery and notification processing."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.db import SessionLocal
from app.common.models import OutboxNotification
from app.core.config import settings
from app.jobs.queue import emails_queue, sms_queue

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
