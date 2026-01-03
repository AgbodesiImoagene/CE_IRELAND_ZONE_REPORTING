"""Tests for notification functions."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from app.jobs.notifications import (
    enqueue_2fa_notification,
    enqueue_email_notification,
)
from app.common.models import OutboxNotification


class Test2FANotification:
    """Tests for 2FA notification."""

    def test_enqueue_2fa_notification_email(self, db):
        """Test enqueueing 2FA notification via email."""
        with patch("app.jobs.notifications.emails_queue") as mock_queue:
            notification = enqueue_2fa_notification(
                db=db,
                email="test@example.com",
                code="123456",
                delivery_method="email",
            )

            assert notification.type == "2fa_code"
            assert notification.payload["email"] == "test@example.com"
            assert notification.payload["code"] == "123456"
            assert notification.payload["delivery_method"] == "email"
            assert notification.delivery_state == "pending"

            # Verify queue was called
            mock_queue.enqueue.assert_called_once()

    def test_enqueue_2fa_notification_sms(self, db):
        """Test enqueueing 2FA notification via SMS."""
        with patch("app.jobs.notifications.sms_queue") as mock_queue:
            notification = enqueue_2fa_notification(
                db=db,
                phone="+3531234567890",
                code="123456",
                delivery_method="sms",
            )

            assert notification.type == "2fa_code"
            assert notification.payload["phone"] == "+3531234567890"
            assert notification.payload["code"] == "123456"
            assert notification.payload["delivery_method"] == "sms"
            assert notification.delivery_state == "pending"

            # Verify queue was called
            mock_queue.enqueue.assert_called_once()

    def test_enqueue_2fa_notification_queue_failure(self, db):
        """Test handling queue failure gracefully."""
        with patch("app.jobs.notifications.emails_queue") as mock_queue:
            mock_queue.enqueue.side_effect = Exception("Queue error")

            # Should still create notification
            notification = enqueue_2fa_notification(
                db=db,
                email="test@example.com",
                code="123456",
                delivery_method="email",
            )

            assert notification.type == "2fa_code"
            assert notification.delivery_state == "pending"


class TestEmailNotification:
    """Tests for email notification."""

    def test_enqueue_email_notification(self, db):
        """Test enqueueing email notification."""
        with patch("app.jobs.notifications.emails_queue") as mock_queue:
            notification = enqueue_email_notification(
                db=db,
                email="recipient@example.com",
                subject="Test Subject",
                body="Test Body",
            )

            assert notification.type == "email"
            assert notification.payload["email"] == "recipient@example.com"
            assert notification.payload["subject"] == "Test Subject"
            assert notification.payload["body"] == "Test Body"
            assert notification.delivery_state == "pending"

            # Verify queue was called
            mock_queue.enqueue.assert_called_once()

    def test_enqueue_email_notification_queue_failure(self, db):
        """Test handling queue failure gracefully."""
        with patch("app.jobs.notifications.emails_queue") as mock_queue:
            mock_queue.enqueue.side_effect = Exception("Queue error")

            # Should still create notification
            notification = enqueue_email_notification(
                db=db,
                email="recipient@example.com",
                subject="Test Subject",
                body="Test Body",
            )

            assert notification.type == "email"
            assert notification.delivery_state == "pending"


