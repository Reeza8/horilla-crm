"""
Tests for the activity app
"""

# Third-party imports (Django)
from auditlog.models import LogEntry
from django.test import TestCase

# First party imports (Horilla)
from horilla.contrib.activity.models import Activity
from horilla.contrib.core.models import Company
from horilla.contrib.generics.templatetags.horilla_tags.history_display import (
    create_status_display,
    create_type_display,
)
from horilla.utils.translation import override


class ActivityHistoryCreateRowTests(TestCase):
    """An activity's creation row on a related record's History tab shows the
    activity as it was created, not as it is now."""

    def test_creation_row_shows_status_and_type_at_creation(self):
        """A task created "In Progress" and completed since still reads
        "Status: In Progress" on its creation row."""
        company = Company.objects.create(
            name="Acme", email="acme@example.com", country="US"
        )
        activity = Activity.objects.create(
            subject="Follow up",
            activity_type="task",
            status="in_progress",
            company=company,
        )
        activity.status = "completed"
        activity.activity_type = "meeting"
        activity.save()

        created = LogEntry.objects.get_for_object(activity).get(
            action=LogEntry.Action.CREATE
        )
        with override("en"):
            self.assertEqual(create_status_display(created, "company"), "In Progress")
            self.assertEqual(create_type_display(created), "New Task created")


class AllDayActivityDateTests(TestCase):
    """An all-day event keeps the day it was created for."""

    def test_hidden_start_and_end_keep_the_clicked_day(self):
        """Ticking All Day hides the times but still posts the day clicked."""
        from horilla.contrib.activity.forms import EventForm

        form = EventForm(
            initial={
                "is_all_day": True,
                "start_datetime": "2099-11-11T09:00",
                "end_datetime": "2099-11-11T09:30",
            }
        )
        self.assertIn('value="2099-11-11T09:00"', str(form["start_datetime"]))
        self.assertIn('value="2099-11-11T09:30"', str(form["end_datetime"]))
        self.assertIn("hidden", str(form["start_datetime"]))

    def test_all_day_today_is_not_rejected_once_the_time_has_passed(self):
        """Only the day is checked for an all-day event, so today is allowed."""
        from datetime import timedelta

        from horilla.contrib.activity.forms import EventForm
        from horilla.utils import timezone

        earlier_today = timezone.localtime().replace(hour=0, minute=1)
        form = EventForm()
        form.cleaned_data = {}
        from horilla.contrib.activity.forms import _validate_not_past

        _validate_not_past(form, "start_datetime", earlier_today, date_only=True)
        self.assertNotIn("start_datetime", form.errors)
        _validate_not_past(
            form, "start_datetime", earlier_today - timedelta(days=1), date_only=True
        )
        self.assertIn("start_datetime", form.errors)
