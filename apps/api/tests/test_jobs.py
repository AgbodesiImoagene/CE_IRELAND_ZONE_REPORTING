"""Tests for background job processing."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from sqlalchemy.orm import Session

from app.common.models import OutboxNotification
from app.core.config import settings
from app.jobs.notifications import enqueue_2fa_notification
from app.jobs.tasks import (
    _process_2fa_notification,
    _process_invitation_notification,
    process_outbox_notification,
    send_email,
    send_sms,
)


class TestSendEmail:
    """Test email sending functionality."""

    def test_send_email_with_smtp_configured(self):
        """Test sending email when SMTP is configured."""
        # Mock the entire send_email function's SMTP usage
        # Since smtplib is imported inside the function, we need to
        # patch it where it will be imported
        mock_smtp_class = MagicMock()
        mock_smtp_instance = MagicMock()
        mock_server = MagicMock()
        mock_smtp_instance.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_instance.__exit__ = MagicMock(return_value=None)
        mock_smtp_class.return_value = mock_smtp_instance

        # Import smtplib and patch it
        import smtplib

        original_smtp = smtplib.SMTP
        smtplib.SMTP = mock_smtp_class

        try:
            # Configure settings to use SMTP
            with patch.object(settings, "smtp_host", "smtp.example.com"):
                with patch.object(settings, "smtp_port", 587):
                    with patch.object(settings, "smtp_user", ""):
                        with patch.object(settings, "smtp_password", ""):
                            with patch("app.jobs.tasks.logger"):
                                result = send_email(
                                    "test@example.com",
                                    "Test Subject",
                                    "Test body",
                                    html_body="<html>Test</html>",
                                )

            assert result is True
            assert mock_smtp_class.called
            call_args = mock_smtp_class.call_args
            assert call_args[0][0] == "smtp.example.com"
            assert call_args[0][1] == 587
        finally:
            smtplib.SMTP = original_smtp

    def test_send_email_dev_mode(self):
        """Test email sending in dev mode (logs to console)."""
        with patch.object(settings, "smtp_host", "localhost"):
            with patch("app.jobs.tasks.logger") as mock_logger:
                result = send_email(
                    "test@example.com",
                    "Test Subject",
                    "Test body",
                )

        assert result is True
        mock_logger.info.assert_called()

    def test_send_email_handles_failure(self):
        """Test email sending handles failures gracefully."""
        import smtplib as smtp_module

        with patch.object(smtp_module, "SMTP") as mock_smtp:
            mock_smtp.side_effect = Exception("SMTP error")

            with patch.object(settings, "smtp_host", "smtp.example.com"):
                with patch("app.jobs.tasks.logger") as mock_logger:
                    result = send_email("test@example.com", "Subject", "Body")

        assert result is False
        mock_logger.error.assert_called()


class TestSendSMS:
    """Test SMS sending functionality."""

    def test_send_sms_dev_mode(self):
        """Test SMS sending in dev mode (logs to console)."""
        with patch("app.jobs.tasks.logger") as mock_logger:
            result = send_sms("+1234567890", "Test message")

        assert result is True
        mock_logger.info.assert_called()

    def test_send_sms_handles_failure(self):
        """Test SMS sending handles failures gracefully."""
        with patch("app.jobs.tasks.logger") as mock_logger:
            mock_logger.info.side_effect = Exception("SMS error")
            result = send_sms("+1234567890", "Test message")

        assert result is False
        mock_logger.error.assert_called()


class TestProcessInvitationNotification:
    """Test invitation notification processing."""

    def test_process_invitation_notification_success(self, db: Session):
        """Test successful invitation notification processing."""
        notification = OutboxNotification(
            id=uuid4(),
            type="user_invitation",
            payload={
                "email": "invited@example.com",
                "token": "test-token",
                "expires_at": "2025-12-31T23:59:59Z",
            },
            delivery_state="pending",
        )
        db.add(notification)
        db.commit()

        with patch("app.jobs.tasks.send_email") as mock_send:
            mock_send.return_value = True
            result = _process_invitation_notification(db, notification)

        assert result is True
        mock_send.assert_called_once()
        # Check email was sent
        call_args = mock_send.call_args
        assert call_args[0][0] == "invited@example.com"
        assert "invited to join" in call_args[0][1].lower()

    def test_process_invitation_missing_email(self, db: Session):
        """Test invitation processing fails when email is missing."""
        notification = OutboxNotification(
            id=uuid4(),
            type="user_invitation",
            payload={"token": "test-token"},
            delivery_state="pending",
        )
        db.add(notification)
        db.commit()

        with patch("app.jobs.tasks.logger") as mock_logger:
            result = _process_invitation_notification(db, notification)

        assert result is False
        mock_logger.error.assert_called()


class TestProcess2FANotification:
    """Test 2FA notification processing."""

    def test_process_2fa_email_success(self, db: Session):
        """Test successful 2FA email notification."""
        notification = OutboxNotification(
            id=uuid4(),
            type="2fa_code",
            payload={
                "email": "user@example.com",
                "code": "123456",
                "delivery_method": "email",
            },
            delivery_state="pending",
        )
        db.add(notification)
        db.commit()

        with patch("app.jobs.tasks.send_email") as mock_send:
            mock_send.return_value = True
            result = _process_2fa_notification(db, notification)

        assert result is True
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert call_args[0][0] == "user@example.com"
        assert "123456" in call_args[0][2]

    def test_process_2fa_sms_success(self, db: Session):
        """Test successful 2FA SMS notification."""
        notification = OutboxNotification(
            id=uuid4(),
            type="2fa_code",
            payload={
                "phone": "+1234567890",
                "code": "123456",
                "delivery_method": "sms",
            },
            delivery_state="pending",
        )
        db.add(notification)
        db.commit()

        with patch("app.jobs.tasks.send_sms") as mock_send:
            mock_send.return_value = True
            result = _process_2fa_notification(db, notification)

        assert result is True
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert call_args[0][0] == "+1234567890"
        assert "123456" in call_args[0][1]

    def test_process_2fa_missing_code(self, db: Session):
        """Test 2FA processing fails when code is missing."""
        notification = OutboxNotification(
            id=uuid4(),
            type="2fa_code",
            payload={"email": "user@example.com", "delivery_method": "email"},
            delivery_state="pending",
        )
        db.add(notification)
        db.commit()

        with patch("app.jobs.tasks.logger") as mock_logger:
            result = _process_2fa_notification(db, notification)

        assert result is False
        mock_logger.error.assert_called()


class TestProcessOutboxNotification:
    """Test outbox notification processing."""

    def test_process_outbox_notification_invitation(self, db: Session):
        """Test processing invitation notification."""
        notification = OutboxNotification(
            id=uuid4(),
            type="user_invitation",
            payload={
                "email": "invited@example.com",
                "token": "test-token",
                "expires_at": "2025-12-31T23:59:59Z",
            },
            delivery_state="pending",
        )
        db.add(notification)
        db.commit()
        notification_id = str(notification.id)

        # Mock SessionLocal to return the test session
        # Also prevent db.close() from closing our test session
        with patch("app.jobs.tasks.SessionLocal", return_value=db):
            with patch.object(db, "close"):  # Prevent closing test session
                with patch("app.jobs.tasks.send_email") as mock_send:
                    mock_send.return_value = True
                    result = process_outbox_notification(notification_id)

        assert result is True
        # Re-query to get updated state
        db.expire_all()  # Expire all objects to force reload from DB
        updated_notification = db.query(OutboxNotification).filter_by(
            id=notification.id
        ).first()
        assert updated_notification is not None
        assert updated_notification.delivery_state == "sent"
        assert updated_notification.sent_at is not None

    def test_process_outbox_notification_2fa(self, db: Session):
        """Test processing 2FA notification."""
        notification = OutboxNotification(
            id=uuid4(),
            type="2fa_code",
            payload={
                "email": "user@example.com",
                "code": "123456",
                "delivery_method": "email",
            },
            delivery_state="pending",
        )
        db.add(notification)
        db.commit()
        notification_id = str(notification.id)

        # Mock SessionLocal to return the test session
        with patch("app.jobs.tasks.SessionLocal", return_value=db):
            with patch.object(db, "close"):  # Prevent closing test session
                with patch("app.jobs.tasks.send_email") as mock_send:
                    mock_send.return_value = True
                    result = process_outbox_notification(notification_id)

        assert result is True
        # Re-query to get updated state
        db.expire_all()
        updated_notification = db.query(OutboxNotification).filter_by(
            id=notification.id
        ).first()
        assert updated_notification is not None
        assert updated_notification.delivery_state == "sent"

    def test_process_outbox_notification_not_found(
        self, db: Session  # noqa: ARG001
    ):
        """Test processing non-existent notification."""
        fake_id = str(uuid4())

        # Mock SessionLocal to return the test session
        with patch("app.jobs.tasks.SessionLocal", return_value=db):
            with patch.object(db, "close"):  # Prevent closing test session
                with patch("app.jobs.tasks.logger") as mock_logger:
                    result = process_outbox_notification(fake_id)

        assert result is False
        mock_logger.warning.assert_called()

    def test_process_outbox_notification_already_processed(self, db: Session):
        """Test processing already processed notification."""
        notification = OutboxNotification(
            id=uuid4(),
            type="2fa_code",
            payload={"code": "123456"},
            delivery_state="sent",
            sent_at=datetime.now(timezone.utc),
        )
        db.add(notification)
        db.commit()
        notification_id = str(notification.id)

        # Mock SessionLocal to return the test session
        with patch("app.jobs.tasks.SessionLocal", return_value=db):
            with patch.object(db, "close"):  # Prevent closing test session
                result = process_outbox_notification(notification_id)

        assert result is True  # Returns True for already processed

    def test_process_outbox_notification_failure(self, db: Session):
        """Test handling notification processing failure."""
        notification = OutboxNotification(
            id=uuid4(),
            type="2fa_code",
            payload={"email": "user@example.com", "code": "123456"},
            delivery_state="pending",
        )
        db.add(notification)
        db.commit()
        notification_id = str(notification.id)

        # Mock SessionLocal to return the test session
        with patch("app.jobs.tasks.SessionLocal", return_value=db):
            with patch.object(db, "close"):  # Prevent closing test session
                with patch("app.jobs.tasks.send_email") as mock_send:
                    mock_send.return_value = False  # Email send fails
                    for _ in range(settings.max_notification_retries + 1):
                        result = process_outbox_notification(notification_id)
                        assert result is False

        # Re-query to get updated state
        db.expire_all()
        updated_notification = db.query(OutboxNotification).filter_by(
            id=notification.id
        ).first()
        assert updated_notification is not None
        assert updated_notification.delivery_state == "failed"
        assert updated_notification.last_error is not None

    def test_process_outbox_notification_unknown_type(self, db: Session):
        """Test processing unknown notification type."""
        notification = OutboxNotification(
            id=uuid4(),
            type="unknown_type",
            payload={},
            delivery_state="pending",
        )
        db.add(notification)
        db.commit()
        notification_id = str(notification.id)

        # Mock SessionLocal to return the test session
        with patch("app.jobs.tasks.SessionLocal", return_value=db):
            with patch.object(db, "close"):  # Prevent closing test session
                result = process_outbox_notification(notification_id)

        assert result is False
        # Re-query to get updated state
        db.expire_all()
        updated_notification = db.query(OutboxNotification).filter_by(
            id=notification.id
        ).first()
        assert updated_notification is not None
        assert updated_notification.delivery_state == "failed"
        assert updated_notification.last_error is not None
        assert "Unknown notification type" in str(
            updated_notification.last_error
        )


class TestEnqueue2FANotification:
    """Test 2FA notification enqueueing."""

    def test_enqueue_2fa_notification_email(self, db: Session):
        """Test creating and enqueueing 2FA email notification."""
        # Patch where it's imported in notifications.py
        with patch("app.jobs.notifications.emails_queue") as mock_queue:
            notification = enqueue_2fa_notification(
                db=db,
                email="user@example.com",
                code="123456",
                delivery_method="email",
            )

        assert notification is not None
        assert notification.type == "2fa_code"
        assert notification.delivery_state == "pending"
        assert notification.payload["code"] == "123456"
        assert notification.payload["email"] == "user@example.com"
        mock_queue.enqueue.assert_called_once()

    def test_enqueue_2fa_notification_sms(self, db: Session):
        """Test creating and enqueueing 2FA SMS notification."""
        # Patch where it's imported in notifications.py
        with patch("app.jobs.notifications.sms_queue") as mock_queue:
            notification = enqueue_2fa_notification(
                db=db,
                phone="+1234567890",
                code="123456",
                delivery_method="sms",
            )

        assert notification is not None
        assert notification.type == "2fa_code"
        assert notification.payload["code"] == "123456"
        assert notification.payload["phone"] == "+1234567890"
        assert notification.payload["delivery_method"] == "sms"
        mock_queue.enqueue.assert_called_once()

    def test_enqueue_2fa_notification_handles_queue_failure(self, db: Session):
        """Test that notification is created even if queueing fails."""
        # Patch where it's imported in notifications.py
        with patch("app.jobs.notifications.emails_queue") as mock_queue:
            mock_queue.enqueue.side_effect = Exception("Queue error")

            notification = enqueue_2fa_notification(
                db=db,
                email="user@example.com",
                code="123456",
            )

        # Notification should still be created (will be picked up by processor)
        assert notification is not None
        assert notification.delivery_state == "pending"


class TestNotificationRetries:
    """Test notification retry functionality."""

    def test_retry_on_delivery_failure(self, db: Session):
        """Test that notifications are retried on delivery failure."""
        notification = OutboxNotification(
            id=uuid4(),
            type="2fa_code",
            payload={"email": "user@example.com", "code": "123456"},
            delivery_state="pending",
            retry_count=0,
        )
        db.add(notification)
        db.commit()
        notification_id = str(notification.id)

        # Mock SessionLocal and queues
        with patch("app.jobs.tasks.SessionLocal", return_value=db):
            with patch.object(db, "close"):
                with patch("app.jobs.tasks.send_email") as mock_send:
                    mock_send.return_value = False  # Delivery fails
                    # Patch the queue where it's imported in tasks.py
                    with patch("app.jobs.tasks.emails_queue") as mock_queue:
                        result = process_outbox_notification(notification_id)

        assert result is False  # Current attempt failed
        db.expire_all()
        updated = db.query(OutboxNotification).filter_by(
            id=notification.id
        ).first()
        assert updated is not None
        assert updated.retry_count == 1
        assert updated.delivery_state == "pending"
        assert "Scheduling retry" in str(updated.last_error)
        # Verify queue.enqueue_in was called for retry
        assert mock_queue.enqueue_in.called

    def test_max_retries_exceeded(self, db: Session):
        """Test that notifications fail after max retries."""
        notification = OutboxNotification(
            id=uuid4(),
            type="2fa_code",
            payload={"email": "user@example.com", "code": "123456"},
            delivery_state="pending",
            retry_count=settings.max_notification_retries,  # Already at max
        )
        db.add(notification)
        db.commit()
        notification_id = str(notification.id)

        # Mock SessionLocal
        with patch("app.jobs.tasks.SessionLocal", return_value=db):
            with patch.object(db, "close"):
                with patch("app.jobs.tasks.send_email") as mock_send:
                    mock_send.return_value = False  # Delivery fails
                    result = process_outbox_notification(notification_id)

        assert result is False
        db.expire_all()
        updated = db.query(OutboxNotification).filter_by(
            id=notification.id
        ).first()
        assert updated is not None
        assert updated.delivery_state == "failed"
        assert (
            f"failed after {settings.max_notification_retries} retries"
            in str(updated.last_error).lower()
        )

    def test_retry_exponential_backoff(self, db: Session):
        """Test that retries use exponential backoff."""
        notification = OutboxNotification(
            id=uuid4(),
            type="user_invitation",
            payload={"email": "invited@example.com", "token": "test-token"},
            delivery_state="pending",
            retry_count=2,  # Third attempt
        )
        db.add(notification)
        db.commit()
        notification_id = str(notification.id)

        # Mock SessionLocal and queue
        with patch("app.jobs.tasks.SessionLocal", return_value=db):
            with patch.object(db, "close"):
                with patch("app.jobs.tasks.send_email") as mock_send:
                    mock_send.return_value = False
                    with patch("app.jobs.tasks.emails_queue") as mock_queue:
                        process_outbox_notification(notification_id)

        # Verify exponential backoff: 2^(retry_count)
        # retry_count=2 means delay = 2^(2) = 4 seconds
        call_args = mock_queue.enqueue_in.call_args
        delay = call_args[0][0]  # First positional arg is timedelta
        assert delay.total_seconds() == 4

    def test_success_after_retry(self, db: Session):
        """Test that notification succeeds on retry."""
        notification = OutboxNotification(
            id=uuid4(),
            type="2fa_code",
            payload={"email": "user@example.com", "code": "123456"},
            delivery_state="pending",
            retry_count=1,  # Second attempt
        )
        db.add(notification)
        db.commit()
        notification_id = str(notification.id)

        # Mock SessionLocal
        with patch("app.jobs.tasks.SessionLocal", return_value=db):
            with patch.object(db, "close"):
                with patch("app.jobs.tasks.send_email") as mock_send:
                    mock_send.return_value = True  # Success on retry
                    result = process_outbox_notification(notification_id)

        assert result is True
        db.expire_all()
        updated = db.query(OutboxNotification).filter_by(
            id=notification.id
        ).first()
        assert updated is not None
        assert updated.delivery_state == "sent"
        assert updated.sent_at is not None
        assert updated.last_error is None
