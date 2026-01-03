"""Helper functions to create and enqueue notifications."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.common.models import OutboxNotification
from app.jobs.queue import emails_queue, sms_queue


def enqueue_2fa_notification(
    db: Session,
    email: str | None = None,
    phone: str | None = None,
    code: str | None = None,
    delivery_method: str = "email",
) -> OutboxNotification:
    """
    Create and enqueue a 2FA notification.

    Args:
        db: Database session
        email: User email address
        phone: User phone number (for SMS)
        code: 2FA code
        delivery_method: "email" or "sms"

    Returns:
        Created OutboxNotification instance
    """
    payload = {
        "delivery_method": delivery_method,
        "code": code,
    }

    if email:
        payload["email"] = email
    if phone:
        payload["phone"] = phone

    notification = OutboxNotification(
        type="2fa_code",
        payload=payload,
        delivery_state="pending",
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    # Enqueue for processing
    queue = sms_queue if delivery_method == "sms" else emails_queue
    try:
        queue.enqueue(
            "app.jobs.tasks.process_outbox_notification",
            str(notification.id),
            job_id=str(notification.id),
        )
    except Exception:
        # If queueing fails, notification remains pending and will be
        # picked up by the outbox processor
        pass

    return notification


def enqueue_email_notification(
    db: Session,
    email: str,
    subject: str,
    body: str,
) -> OutboxNotification:
    """
    Create and enqueue an email notification.

    Args:
        db: Database session
        email: Recipient email address
        subject: Email subject
        body: Email body (plain text)

    Returns:
        Created OutboxNotification instance
    """
    payload = {
        "email": email,
        "subject": subject,
        "body": body,
    }

    notification = OutboxNotification(
        type="email",
        payload=payload,
        delivery_state="pending",
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    # Enqueue for processing
    try:
        emails_queue.enqueue(
            "app.jobs.tasks.process_outbox_notification",
            str(notification.id),
            job_id=str(notification.id),
        )
    except Exception:
        # If queueing fails, notification remains pending and will be
        # picked up by the outbox processor
        pass

    return notification
