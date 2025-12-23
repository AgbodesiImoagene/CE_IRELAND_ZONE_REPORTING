"""Command-line interface for job workers."""

import sys
from rq import Worker

from app.jobs.queue import get_redis_connection


def run_worker(queues: list[str] | None = None):
    """
    Run an RQ worker for processing background jobs.

    Args:
        queues: List of queue names to process (default: ['default'])
    """
    if queues is None:
        queues = ["default"]

    # In RQ 2.x, pass connection directly to Worker
    redis_conn = get_redis_connection()
    worker = Worker(queues, connection=redis_conn)
    worker.work()


if __name__ == "__main__":
    # Allow specifying queues via command line
    queues = sys.argv[1:] if len(sys.argv) > 1 else ["default"]
    run_worker(queues)
