"""
Outbox notification processor.

This module provides a worker that processes pending outbox notifications
from the database and enqueues them as background jobs.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from sqlalchemy import select

from app.common.db import SessionLocal
from app.common.models import OutboxNotification
from app.jobs.queue import emails_queue, sms_queue

logger = logging.getLogger(__name__)


def process_outbox_notifications(batch_size: int = 10, max_iterations: Optional[int] = None) -> None:
    """
    Process pending outbox notifications by enqueueing them as background jobs.

    This function polls the database for pending notifications and enqueues them
    to the appropriate RQ queue for processing.

    Args:
        batch_size: Number of notifications to process per iteration
        max_iterations: Maximum number of iterations (None for infinite)
    """
    iteration = 0
    while max_iterations is None or iteration < max_iterations:
        iteration += 1
        db = SessionLocal()
        try:
            # Fetch pending notifications
            stmt = (
                select(OutboxNotification)
                .where(OutboxNotification.delivery_state == "pending")
                .order_by(OutboxNotification.created_at)
                .limit(batch_size)
            )
            notifications = db.execute(stmt).scalars().all()

            if not notifications:
                # No pending notifications, wait before next check
                time.sleep(5)
                continue

            for notification in notifications:
                # Determine queue based on notification type
                if notification.type == "2fa_code":
                    payload = notification.payload
                    delivery_method = payload.get("delivery_method", "email")
                    queue = sms_queue if delivery_method == "sms" else emails_queue
                else:
                    # Most notifications are emails (invitations, etc.)
                    queue = emails_queue

                # Enqueue job
                try:
                    job = queue.enqueue(
                        "app.jobs.tasks.process_outbox_notification",
                        str(notification.id),
                        job_id=str(notification.id),
                    )
                    logger.info(
                        f"Enqueued notification {notification.id} "
                        f"({notification.type}) as job {job.id}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to enqueue notification {notification.id}: {str(e)}",
                        exc_info=True,
                    )
                    # Mark as failed
                    notification.delivery_state = "failed"
                    notification.last_error = f"Failed to enqueue: {str(e)}"
                    db.commit()

            db.commit()

        except Exception as e:
            logger.error(f"Error processing outbox notifications: {str(e)}", exc_info=True)
            if db:
                db.rollback()
        finally:
            db.close()

        # Small delay between batches
        time.sleep(1)


if __name__ == "__main__":
    # Run as standalone worker
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.info("Starting outbox notification processor...")
    process_outbox_notifications()

