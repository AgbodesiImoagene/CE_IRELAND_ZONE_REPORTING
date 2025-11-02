"""Redis Queue setup and connection."""

from __future__ import annotations

import redis
from rq import Queue

from app.core.config import settings


def get_redis_connection() -> redis.Redis:
    """Get Redis connection for RQ."""
    return redis.from_url(settings.redis_url)


def get_queue(name: str = "default") -> Queue:
    """
    Get RQ queue instance.

    Args:
        name: Queue name (default, emails, sms, imports, exports, summaries)

    Returns:
        RQ Queue instance
    """
    return Queue(name, connection=get_redis_connection())


# Pre-configured queues
default_queue = Queue("default", connection=get_redis_connection())
emails_queue = Queue("emails", connection=get_redis_connection())
sms_queue = Queue("sms", connection=get_redis_connection())
imports_queue = Queue("imports", connection=get_redis_connection())
exports_queue = Queue("exports", connection=get_redis_connection())
summaries_queue = Queue("summaries", connection=get_redis_connection())
