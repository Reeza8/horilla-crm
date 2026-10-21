# horilla.contrib.core/scheduler.py

"""
Background scheduler tasks for Horilla.

This module defines periodic background jobs executed using APScheduler.
It handles maintenance and automation tasks such as:

- Updating the active fiscal year
- Cleaning up expired records from the recycle bin
- Initializing and starting the background scheduler

These tasks are intended to run continuously in the background
alongside the Django application.
"""

# Standard library imports
from datetime import timedelta

# Third-party imports (Django)
from apscheduler.schedulers.background import BackgroundScheduler
from django.core.management import call_command

# First party imports (Horilla)
from horilla.utils import timezone

# Local imports
from .models import RecycleBin, RecycleBinPolicy


def fiscal_year_update():
    """
    Trigger the fiscal year update management command.

    This function invokes the `update_fiscal_year` Django management
    command to ensure fiscal year data remains up to date.
    """
    call_command("update_fiscal_year")


def clear_expired_recyclebin():
    """
    Remove recycle bin records that exceed their retention period.

    For each recycle bin policy, this function deletes records whose
    deletion date is older than the configured retention duration.
    Policies with 0 retention days mean "no expiry" and are skipped, so their
    records are kept.
    """
    now = timezone.now()
    total_deleted = 0
    for policy in RecycleBinPolicy.objects.filter(retention_days__gt=0).select_related(
        "company"
    ):
        cutoff = now - timedelta(days=policy.retention_days)
        deleted_count, _ = RecycleBin.objects.filter(
            company=policy.company, deleted_at__date__lte=cutoff.date()
        ).delete()
        total_deleted += deleted_count


def start_scheduler():
    """
    Initialize and start the background scheduler.

    This scheduler runs periodic jobs for fiscal year updates
    and recycle bin cleanup at predefined intervals.
    """
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        fiscal_year_update, "interval", hours=12, id="fiscal_year_update_job"
    )
    scheduler.add_job(
        clear_expired_recyclebin,
        "interval",
        hours=4,
        id="clear_expired_recyclebin_job",
        replace_existing=True,
    )
    scheduler.start()
