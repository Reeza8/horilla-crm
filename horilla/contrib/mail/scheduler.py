"""
mail scheduler module"""

# Standard library imports
import fcntl
import logging
import os
import sys

# Third-party imports (Django)
from apscheduler.schedulers.background import BackgroundScheduler
from django.conf import settings

logger = logging.getLogger(__name__)

_lock_file = None


def _acquire_scheduler_lock():
    """
    Ensure only one process (e.g. one gunicorn worker) runs the
    scheduler. Each worker imports this module and would otherwise
    start its own BackgroundScheduler, causing the same Outlook
    token to be refreshed concurrently by multiple processes -
    Microsoft rotates the refresh_token on every use, so the loser
    of that race fails with an invalid_client/invalid_grant error.

    Returns True if this process won the lock and should start the
    scheduler.
    """
    global _lock_file
    lock_path = os.path.join(settings.BASE_DIR, ".outlook_refresh_scheduler.lock")
    _lock_file = open(lock_path, "w", encoding="utf-8")
    try:
        fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        _lock_file.close()
        _lock_file = None
        return False
    return True


def refresh_outlook_auth_token():
    """
    scheduler method to refresh token
    """
    # Local imports
    from .models import HorillaMailConfiguration
    from .views.outlook import refresh_outlook_token

    apis = HorillaMailConfiguration.objects.filter(token__isnull=False, type="outlook")
    for api in apis:
        try:
            refresh_outlook_token(api)
            logger.info("Updated token for %s outlook ", api)
        except Exception as e:
            logger.error("Error in refresh outlook token: %s", e)


if (
    not any(
        cmd in sys.argv
        for cmd in ["makemigrations", "migrate", "compilemessages", "flush", "shell"]
    )
    and _acquire_scheduler_lock()
):
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        refresh_outlook_auth_token,
        "interval",
        minutes=50,
        id="refresh_outlook_auth_token",
    )
    scheduler.start()
