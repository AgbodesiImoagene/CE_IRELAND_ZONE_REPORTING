# Background Job Processing

This module implements background job processing using RQ (Redis Queue) for asynchronous email/SMS delivery and other long-running tasks.

## Architecture

- **RQ (Redis Queue)**: Simple, lightweight job queue backed by Redis
- **Queues**: Separate queues for different job types (`emails`, `sms`, `imports`, `exports`, `summaries`)
- **Outbox Pattern**: Notifications are written to `outbox_notifications` table, then processed asynchronously

## Components

### Queues (`queue.py`)
Pre-configured RQ queues for different job types:
- `default`: General purpose jobs
- `emails`: Email delivery jobs
- `sms`: SMS delivery jobs
- `imports`: Data import jobs
- `exports`: Report export jobs
- `summaries`: Summary calculation jobs

### Tasks (`tasks.py`)
Background job functions:
- `send_email()`: Send email via SMTP
- `send_sms()`: Send SMS (currently dev mode only)
- `process_outbox_notification()`: Process a single outbox notification

### Notifications (`notifications.py`)
Helper functions to create and enqueue notifications:
- `enqueue_2fa_notification()`: Create and enqueue 2FA code notification

### Outbox Processor (`outbox_processor.py`)
Optional polling worker that processes pending notifications from the database. Useful for ensuring no notifications are missed if direct enqueueing fails.

## Usage

### Starting Workers

Start the worker service via Docker Compose:

```bash
make worker
# or
docker compose -f infra/docker-compose.yml up -d worker
```

Or run manually:

```bash
python -m app.jobs.cli emails sms
```

### Enqueueing Jobs

Jobs are automatically enqueued when:
- 2FA codes are sent (via `enqueue_2fa_notification()`)
- User invitations are created (enqueues `user_invitation` notification)

You can also manually enqueue:

```python
from app.jobs.queue import emails_queue
from app.jobs.tasks import send_email

emails_queue.enqueue(
    send_email,
    "user@example.com",
    "Subject",
    "Body",
    html_body="<html>Body</html>"
)
```

## Configuration

Email and SMS settings are configured via environment variables (see `app/core/config.py`):

```bash
# Email (SMTP)
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=noreply@ce-ireland.zone
SMTP_FROM_NAME="CE Ireland Zone"

# SMS (future)
SMS_PROVIDER=
SMS_API_KEY=
SMS_API_SECRET=
SMS_FROM_NUMBER=
```

## Development Mode

In development (when `SMTP_HOST=localhost` or empty), emails are logged to console instead of being sent. This allows testing without setting up SMTP.

## Production Setup

For production:
1. Configure real SMTP server (Gmail, SendGrid, AWS SES, etc.)
2. Implement SMS provider (Twilio, AWS SNS, etc.) in `send_sms()`
3. Run multiple worker instances for scalability
4. Set up monitoring and alerting for failed jobs

## Monitoring

Use RQ dashboard or custom monitoring to track:
- Queue sizes
- Failed jobs
- Processing times
- Worker health

