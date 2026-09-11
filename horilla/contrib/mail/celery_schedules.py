"""
Celery beat schedule configuration for mail app.

This module defines periodic tasks that are executed by Celery Beat,
including scheduled email processing tasks.
"""

# Standard library imports
from datetime import timedelta

HORILLA_BEAT_SCHEDULE = {
    "process-scheduled-mails-every-minute": {
        "task": "horilla.contrib.mail.tasks.process_scheduled_mails",
        "schedule": timedelta(seconds=10),
    },
    "refresh-outlook-auth-token": {
        "task": "horilla.contrib.mail.tasks.refresh_outlook_auth_token",
        "schedule": timedelta(minutes=50),
    },
}
