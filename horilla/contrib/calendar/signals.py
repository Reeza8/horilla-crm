"""
Signal handlers for the calendar app.

This module defines Django signal receivers related to calendar functionality,
including automatic syncing of events to each user's Google Calendar.
"""

# Standard library imports
import logging
import queue
import threading
import time

# Third-party imports (Django)
from django.dispatch import receiver

# First party imports (Horilla)
from horilla.db.models.signals import post_delete, post_save

# ---------------------------------------------------------------------------
# Single-worker Google push queue
# ---------------------------------------------------------------------------

_google_push_queue = queue.Queue()


def _google_push_worker():
    """Single daemon thread that drains _google_push_queue at a throttled rate."""
    from django.db import close_old_connections

    while True:
        # Close any stale/idle connection before starting the next job so the
        # worker thread never holds a SQLite shared lock while the main thread
        # needs an exclusive write lock (bulk delete, assigned_to.add, etc.).
        close_old_connections()
        fn, args, kwargs = _google_push_queue.get()
        try:
            fn(*args, **kwargs)
        except Exception as exc:
            logging.getLogger(__name__).error("Google push worker error: %s", exc)
        finally:
            _google_push_queue.task_done()
            # Release the connection immediately after the job so no lock is
            # held during the sleep or while waiting for the next queue item.
            close_old_connections()
        # Throttle: ~4 pushes/second keeps us safely under Google's
        # 500 writes/100 s per-user quota even during bulk backfills.
        time.sleep(0.25)


_google_push_worker_thread = threading.Thread(
    target=_google_push_worker, daemon=True, name="google-push-worker"
)
_google_push_worker_thread.start()


def _run_in_thread(fn, *args, **kwargs):
    """Enqueue fn(*args) onto the single Google push worker (non-blocking)."""
    # Skip during the test run: the worker holds a second SQLite connection and
    # races the test transaction ("database table is locked: activity_activity").
    import sys

    if "test" in sys.argv:
        return
    _google_push_queue.put((fn, args, kwargs))


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Google Calendar sync signals
# ---------------------------------------------------------------------------


def _sync_activity(instance):
    """Push an Activity to Google Calendar for all related users who are connected.

    Re-fetches the activity from the database by PK so we always read the
    committed state of assigned_to (the signal may fire before an in-progress
    assigned_to.add() on the main thread has committed).

    The DB read is done first and the connection is closed before the Google
    API call so the worker thread holds no SQLite lock during network I/O.
    """
    from django.db import close_old_connections

    from horilla.contrib.activity.models import Activity

    from .google_calendar.sync import push_activity_to_google

    # --- DB read phase: fetch all data needed, then release the connection ---
    try:
        fresh = (
            Activity.objects.select_related("owner", "meeting_host")
            .prefetch_related("assigned_to")
            .get(pk=instance.pk)
        )
    except Activity.DoesNotExist:
        return

    users = set()
    if fresh.owner_id:
        users.add(fresh.owner)
    if fresh.meeting_host_id:
        users.add(fresh.meeting_host)
    try:
        for u in fresh.assigned_to.all():
            users.add(u)
    except Exception:
        pass

    # Release the DB connection before network I/O so no SQLite lock is held
    # while the Google API call (which can take hundreds of ms) is in flight.
    close_old_connections()

    # --- Network phase: push to Google (no DB connection held) ---------------
    for user in users:
        try:
            push_activity_to_google(fresh, user)
        except Exception as exc:
            logger.error(
                "Google sync error for activity %s user %s: %s", fresh.pk, user, exc
            )


@receiver(post_save, sender="activity.Activity")
def sync_activity_to_google(sender, instance, **kwargs):
    """Auto-push Activity to Google Calendar on create/update.
    Runs in a background thread so the request returns immediately.
    Skip activities pulled FROM Google to avoid a sync loop.
    """
    from .google_calendar.sync import is_pulling_from_google

    if (
        getattr(instance, "_from_google", False)
        or getattr(instance, "_skip_google_push", False)
        or is_pulling_from_google()
    ):
        return
    _run_in_thread(_sync_activity, instance)


@receiver(post_delete, sender="activity.Activity")
def delete_activity_from_google(sender, instance, **kwargs):
    """Remove Activity from Google Calendar when deleted from Horilla.
    Runs in a background thread so the delete response is instant.
    """
    from .google_calendar.sync import delete_activity_google_event

    user = instance.owner
    if not user:
        return

    def _do_delete():
        try:
            delete_activity_google_event(instance, user)
        except Exception as exc:
            logger.error(
                "Google delete error for activity %s user %s: %s",
                instance.pk,
                user,
                exc,
            )

    _run_in_thread(_do_delete)


@receiver(post_save, sender="calendar.UserAvailability")
def sync_unavailability_to_google(sender, instance, **kwargs):
    """Auto-push UserAvailability block to Google Calendar on create/update.
    Runs in a background thread. Skip records pulled FROM Google to avoid a sync loop.
    """
    if instance.reason and instance.reason.startswith("[Google]"):
        return

    from .google_calendar.sync import push_unavailability_to_google

    def _do_push():
        try:
            push_unavailability_to_google(instance)
        except Exception as exc:
            logger.error(
                "Google sync error for unavailability %s: %s", instance.pk, exc
            )

    _run_in_thread(_do_push)


@receiver(post_delete, sender="calendar.UserAvailability")
def delete_unavailability_from_google(sender, instance, **kwargs):
    """Remove UserAvailability block from Google Calendar when deleted.
    Runs in a background thread. Skip [Google]-sourced records.
    """
    if instance.reason and instance.reason.startswith("[Google]"):
        return

    from .google_calendar.sync import delete_unavailability_google_event

    def _do_delete():
        try:
            delete_unavailability_google_event(instance)
        except Exception as exc:
            logger.error(
                "Google delete error for unavailability %s: %s", instance.pk, exc
            )

    _run_in_thread(_do_delete)
