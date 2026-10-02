"""
Tests for the calendar app.

This module contains unit and integration tests for calendar functionality.
"""

# Third-party imports (Django)
from django.contrib.auth.models import Permission
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from login_history.models import post_login, post_logout

# First party imports (Horilla)
from horilla.auth.models import User
from horilla.contrib.activity.models import Activity
from horilla.contrib.core.models import Company, Holiday, HorillaContentType
from horilla.db import connection
from horilla.urls import reverse
from horilla.utils import timezone


class CalendarEventsTestBase(TestCase):
    """
    A user with a task related to a Holiday, and helpers to fetch the
    calendar's events. Holiday is a core model: the calendar only knows the
    generic ``Activity.related_object``, not any particular related model.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # django-login-history reads request.META['HTTP_USER_AGENT'] on
        # login/logout, which the test client's bare request doesn't set.
        user_logged_in.disconnect(post_login)
        user_logged_out.disconnect(post_logout)

    @classmethod
    def tearDownClass(cls):
        user_logged_in.connect(post_login)
        user_logged_out.connect(post_logout)
        super().tearDownClass()

    def setUp(self):
        self.company = Company.objects.create(
            name="Acme", email="acme@example.com", country="US"
        )
        self.user = User.objects.create_user(
            username="salesperson",
            email="salesperson@example.com",
            password="pass",
            company=self.company,
        )
        self.record = self._make_holiday("Launch Day")
        self.activity = self._make_activity("Call about the launch", self.record)
        self.record_url = str(self.record.get_detail_url())

    def _make_holiday(self, name):
        now = timezone.now()
        return Holiday.objects.create(
            name=name,
            start_date=now,
            end_date=now,
            company=self.company,
            created_by=self.user,
            updated_by=self.user,
        )

    def _make_activity(self, subject, related=None):
        activity = Activity.objects.create(
            subject=subject,
            activity_type="task",
            status="not_started",
            due_datetime=timezone.now(),
            owner=self.user,
            content_type=(
                HorillaContentType.objects.get_for_model(related) if related else None
            ),
            object_id=related.pk if related else None,
            company=self.company,
        )
        activity.assigned_to.add(self.user)
        return activity

    def _grant(self, *perms):
        for perm in perms:
            app_label, codename = perm.split(".")
            self.user.user_permissions.add(
                Permission.objects.get(
                    content_type__app_label=app_label, codename=codename
                )
            )

    def _events(self):
        self.client.force_login(self.user)
        return self._fetch_events()

    def _fetch_events(self):
        response = self.client.get(
            reverse("calendar:get_calendar_events"),
            {"calendar_types[]": ["task"]},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success", data)
        return {event["id"]: event for event in data["events"]}


class CalendarRelatedRecordLinkTests(CalendarEventsTestBase):
    """
    Calendar events carry ``relatedUrl`` for the popup's Open Related Record
    action, only when the user may open the activity's related record.
    """

    def test_link_when_user_can_view_the_related_record(self):
        """With view access to the record, the event links to its detail page."""
        self._grant("core.view_holiday")
        related_url = self._events()[self.activity.pk]["relatedUrl"]
        self.assertTrue(related_url.startswith(self.record_url), related_url)

    def test_no_link_without_access_to_the_related_record(self):
        """Seeing the activity on the calendar doesn't open its related record."""
        self.assertEqual(self._events()[self.activity.pk]["relatedUrl"], "")

    def test_no_link_when_there_is_no_related_record(self):
        """An activity that isn't related to any record gets no link."""
        activity = self._make_activity("Plan the week")
        self._grant("core.view_holiday")
        self.assertEqual(self._events()[activity.pk]["relatedUrl"], "")

    def test_no_link_to_a_record_outside_the_active_company(self):
        """A record in another company 404s on its own page, so it isn't linked."""
        other_company = Company.objects.create(
            name="Other", email="other@example.com", country="US"
        )
        Holiday.all_objects.filter(pk=self.record.pk).update(company=other_company)
        self._grant("core.view_holiday")
        self.assertEqual(self._events()[self.activity.pk]["relatedUrl"], "")

    def test_query_count_does_not_grow_with_related_records(self):
        """
        Related records are checked together, so linking several records costs
        the same queries as linking one. Uses a view_own user, whose access
        depends on each record's owner field (Holiday.specific_users).
        """
        self._grant("core.view_own_holiday")
        self.record.specific_users.add(self.user)
        self.client.force_login(self.user)
        self._fetch_events()  # warm process-wide caches (content types)
        with CaptureQueriesContext(connection) as one_record:
            events = self._fetch_events()
        self.assertTrue(events[self.activity.pk]["relatedUrl"])

        owned = []
        for i in range(4):
            holiday = self._make_holiday(f"Holiday {i}")
            holiday.specific_users.add(self.user)
            owned.append(self._make_activity(f"Plan holiday {i}", holiday))
        not_owned = self._make_activity(
            "Plan someone else's holiday", self._make_holiday("Other Day")
        )
        same_record = self._make_activity("Follow up on the launch", self.record)
        with CaptureQueriesContext(connection) as many_records:
            events = self._fetch_events()

        for activity in owned:
            self.assertTrue(events[activity.pk]["relatedUrl"])
        self.assertEqual(events[not_owned.pk]["relatedUrl"], "")
        self.assertEqual(
            events[same_record.pk]["relatedUrl"],
            events[self.activity.pk]["relatedUrl"],
        )
        self.assertEqual(
            len(many_records.captured_queries), len(one_record.captured_queries)
        )


class CalendarEventFieldsTests(CalendarEventsTestBase):
    """
    The feed builds labels and URLs once per request instead of calling the
    Activity methods per event. They must still read the same as those methods.
    """

    def test_labels_and_urls_match_the_activity_methods(self):
        """Includes a status outside STATUS_CHOICES (the field's default)."""
        pending = self._make_activity("Left at the default status")
        Activity.objects.filter(pk=pending.pk).update(status="pending")
        events = self._events()
        for activity in Activity.objects.filter(pk__in=[self.activity.pk, pending.pk]):
            event = events[activity.pk]
            self.assertEqual(
                event["activity_type_display"], activity.get_activity_type_display()
            )
            self.assertEqual(event["status_display"], activity.get_status_display())
            self.assertEqual(event["url"], str(activity.get_activity_edit_url()))
            self.assertEqual(event["deleteUrl"], str(activity.get_delete_url()))
            self.assertEqual(event["detailUrl"], str(activity.get_detail_url()))
        self.assertEqual(events[pending.pk]["status_display"], "pending")
