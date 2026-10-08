"""
Celery beat schedule configuration for mail app.

This module defines periodic tasks that are executed by Celery Beat,
including scheduled email processing tasks.
"""

# Standard library imports
from datetime import timedelta

# Third-party imports (other)
from celery.schedules import crontab

HORILLA_BEAT_SCHEDULE = {
    "process-scheduled-mails-every-minute": {
        "task": "horilla.contrib.mail.tasks.process_scheduled_mails",
        "schedule": timedelta(seconds=10),
    },
    "refresh-outlook-auth-token": {
        "task": "horilla.contrib.mail.tasks.refresh_outlook_auth_token",
        "schedule": timedelta(minutes=50),
    },
    "fetch-emails-every-minute": {
        "task": "horilla.contrib.mail.tasks.fetch_emails_to_incoming_mail",
        "schedule": crontab(minute="*"),  # Every minute
    },
    "prune-expired-deleted-message-ids-daily": {
        "task": "horilla.contrib.mail.tasks.prune_expired_deleted_message_ids",
        "schedule": crontab(hour=3, minute=0),  # Once a day, off-peak
    },
}
