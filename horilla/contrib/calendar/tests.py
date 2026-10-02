"""
Tests for the calendar app.

This module contains unit and integration tests for calendar functionality.
"""

# Standard library imports
import datetime
import json

# Third-party imports (Django)
from django.contrib.auth.models import Permission
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from login_history.models import post_login, post_logout

# First party imports (Horilla)
from horilla.auth.models import User
from horilla.contrib.activity.models import Activity
from horilla.contrib.core.models import Company, Holiday, HorillaContentType, Role
from horilla.db import connection
from horilla.urls import reverse
from horilla.utils import timezone

# Local imports
from . import views
from .models import CustomCalendar, UserAvailability, UserCalendarPreference


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


def _utc(month, day, hour=9, minute=0):
    return datetime.datetime(
        2026, month, day, hour, minute, tzinfo=datetime.timezone.utc
    )


class CalendarTeamViewTests(TestCase):
    """
    The Team view (``scope=team``) adds the activities a user may see in the
    All Activities list: the whole company with ``activity.view_activity``,
    otherwise those of the user's subordinates in the role hierarchy
    (``activity.view_own_activity``). It never shows more, and Mine (the
    default) stays as it was.
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
        manager_role = Role.objects.create(
            role_name="Sales Manager", company=self.company
        )
        rep_role = Role.objects.create(
            role_name="Sales Rep", parent_role=manager_role, company=self.company
        )
        support_role = Role.objects.create(role_name="Support", company=self.company)
        self.manager = self._make_user("manager", manager_role)
        self.rep = self._make_user("rep", rep_role)
        self.peer = self._make_user("peer", support_role)

        self.own = self._make_activity("Call the client", self.manager)
        self.reps = self._make_activity("Demo for the client", self.rep)
        self.peers = self._make_activity("Answer a ticket", self.peer)

    def _make_user(self, username, role, company=None):
        return User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="pass",
            company=company or self.company,
            role=role,
        )

    def _make_activity(self, subject, owner, **fields):
        fields.setdefault("activity_type", "task")
        if fields["activity_type"] == "task":
            fields.setdefault("due_datetime", timezone.now())
        activity = Activity.objects.create(
            subject=subject,
            status="not_started",
            owner=owner,
            company=owner.company,
            **fields,
        )
        activity.assigned_to.add(owner)
        return activity

    def _grant(self, user, *perms):
        for perm in perms:
            app_label, codename = perm.split(".")
            user.user_permissions.add(
                Permission.objects.get(
                    content_type__app_label=app_label, codename=codename
                )
            )

    def _fetch_events(self, **params):
        response = self.client.get(
            reverse("calendar:get_calendar_events"),
            {"calendar_types[]": ["task", "event", "meeting"], **params},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success", data)
        return {event["id"]: event for event in data["events"]}

    def _events(self, user, **params):
        self.client.force_login(user)
        return self._fetch_events(**params)

    def test_mine_is_unchanged(self):
        """Without scope=team the calendar shows only the user's own activities."""
        self._grant(self.manager, "activity.view_own_activity")
        events = self._events(self.manager)
        self.assertEqual(set(events), {self.own.pk})
        self.assertNotIn("canChange", events[self.own.pk])
        self.assertNotIn("canDelete", events[self.own.pk])

    def test_team_adds_subordinates_activities(self):
        """view_own_activity: Team adds subordinates' activities, not peers'."""
        self._grant(self.manager, "activity.view_own_activity")
        self.assertEqual(
            set(self._events(self.manager, scope="team")),
            {self.own.pk, self.reps.pk},
        )

    def test_team_includes_activities_assigned_to_a_subordinate(self):
        """As in the All Activities list, an assignee counts like the owner."""
        self._grant(self.manager, "activity.view_own_activity")
        handed_over = self._make_activity("Hand over the account", self.peer)
        handed_over.assigned_to.add(self.rep)
        self.assertIn(handed_over.pk, self._events(self.manager, scope="team"))

    def test_team_keeps_activities_the_user_only_takes_part_in(self):
        """Team adds to Mine, so a meeting the user only attends stays on it."""
        self._grant(self.manager, "activity.view_own_activity")
        meeting = self._make_activity(
            "Weekly sync",
            self.peer,
            activity_type="meeting",
            start_datetime=timezone.now(),
            end_datetime=timezone.now() + datetime.timedelta(hours=1),
        )
        meeting.participants.add(self.manager)
        self.assertIn(meeting.pk, self._events(self.manager))
        self.assertIn(meeting.pk, self._events(self.manager, scope="team"))

    def test_team_with_view_activity_covers_the_active_company_only(self):
        """view_activity: Team shows every activity in the company, none elsewhere."""
        other_company = Company.objects.create(
            name="Other", email="other@example.com", country="US"
        )
        outsider = self._make_user("outsider", None, company=other_company)
        elsewhere = self._make_activity("Call in another company", outsider)
        self._grant(self.peer, "activity.view_activity")
        events = self._events(self.peer, scope="team")
        self.assertEqual(set(events), {self.own.pk, self.reps.pk, self.peers.pk})
        self.assertNotIn(elsewhere.pk, events)

    def test_team_needs_an_activity_view_permission(self):
        """Without view or view_own permission, scope=team is ignored."""
        events = self._events(self.manager, scope="team")
        self.assertEqual(set(events), {self.own.pk})
        self.assertNotIn("canChange", events[self.own.pk])

    def test_team_without_subordinates_is_mine(self):
        """With view_own_activity but no subordinates, Team would add nothing."""
        self._grant(self.rep, "activity.view_own_activity")
        events = self._events(self.rep, scope="team")
        self.assertEqual(set(events), {self.reps.pk})
        self.assertNotIn("canChange", events[self.reps.pk])

    def test_team_actions_follow_record_access(self):
        """
        Team events say what the popup may offer on each record, by the All
        Activities list's rules: Edit and Mark as Complete need change access
        to the record, Delete needs activity.delete_activity.
        """
        self._grant(self.peer, "activity.view_activity", "activity.change_own_activity")
        events = self._events(self.peer, scope="team")
        self.assertTrue(events[self.peers.pk]["canChange"])
        self.assertFalse(events[self.own.pk]["canChange"])
        self.assertFalse(events[self.peers.pk]["canDelete"])

        self._grant(self.peer, "activity.delete_activity")
        events = self._events(self.peer, scope="team")
        self.assertTrue(events[self.own.pk]["canDelete"])

    def test_team_actions_cover_subordinates_records(self):
        """change_own_activity covers subordinates' records, as in the list."""
        self._grant(
            self.manager, "activity.view_own_activity", "activity.change_own_activity"
        )
        events = self._events(self.manager, scope="team")
        self.assertTrue(events[self.own.pk]["canChange"])
        self.assertTrue(events[self.reps.pk]["canChange"])

    def test_team_actions_add_no_query_per_activity(self):
        """Owners are joined and assignees prefetched for the access checks."""
        self._grant(
            self.manager, "activity.view_own_activity", "activity.change_own_activity"
        )
        self.client.force_login(self.manager)
        self._fetch_events(scope="team")  # warm up per-process caches
        with CaptureQueriesContext(connection) as before:
            self._fetch_events(scope="team")
        self._make_activity("Second demo", self.rep)
        self._make_activity("Third demo", self.rep)
        with CaptureQueriesContext(connection) as after:
            events = self._fetch_events(scope="team")
        self.assertEqual(len(events), 4)
        self.assertEqual(len(after.captured_queries), len(before.captured_queries))

    def test_range_limits_activities_to_the_visible_dates(self):
        """
        With FullCalendar's start/end, only activities around that window are
        loaded (a day's margin keeps the edges FullCalendar may still draw);
        without them, all are.
        """
        self._grant(self.manager, "activity.view_own_activity")
        inside = self._make_activity("Inside", self.manager, due_datetime=_utc(10, 7))
        # A task gets FullCalendar's default one-hour length, so it reaches
        # into the window.
        edge = self._make_activity(
            "Evening before", self.manager, due_datetime=_utc(10, 4, 23, 30)
        )
        spanning = self._make_activity(
            "Conference",
            self.manager,
            activity_type="event",
            start_datetime=_utc(9, 30),
            end_datetime=_utc(10, 15),
        )
        # No end: the payload falls back to created_at, before the window.
        open_ended = self._make_activity(
            "Open-ended",
            self.manager,
            activity_type="event",
            start_datetime=_utc(10, 8),
        )
        Activity.all_objects.filter(pk=open_ended.pk).update(created_at=_utc(9, 1))
        before = self._make_activity("Before", self.manager, due_datetime=_utc(9, 20))
        after = self._make_activity("After", self.manager, due_datetime=_utc(10, 20))

        events = self._events(
            self.manager,
            start="2026-10-05T00:00:00+00:00",
            end="2026-10-12T00:00:00+00:00",
        )
        for activity in (inside, edge, spanning, open_ended):
            self.assertIn(activity.pk, events, activity.subject)
        for activity in (before, after):
            self.assertNotIn(activity.pk, events, activity.subject)

        events = self._events(self.manager)
        for activity in (inside, edge, spanning, open_ended, before, after):
            self.assertIn(activity.pk, events, activity.subject)

    def test_requested_range(self):
        """The window is widened by a day and ignored when it isn't usable."""
        factory = RequestFactory()
        window = views._requested_range(
            factory.get(
                "/",
                {
                    "start": "2026-10-05T03:30:00+03:30",
                    "end": "2026-10-12T03:30:00+03:30",
                },
            )
        )
        self.assertEqual(window, (_utc(10, 4, 0), _utc(10, 13, 0)))

        unusable = {
            "missing": {"start": "2026-10-05T00:00:00+00:00"},
            "malformed": {"start": "soon", "end": "later"},
            "invalid": {
                "start": "2026-13-01T00:00:00+00:00",
                "end": "2026-14-01T00:00:00+00:00",
            },
            "reversed": {
                "start": "2026-10-12T00:00:00+00:00",
                "end": "2026-10-05T00:00:00+00:00",
            },
            "overflowing": {
                "start": "0001-01-01T00:00:00+00:00",
                "end": "0001-01-02T00:00:00+00:00",
            },
        }
        for name, params in unusable.items():
            with self.subTest(name):
                self.assertIsNone(views._requested_range(factory.get("/", params)))

    def test_toggle_is_shown_only_when_team_shows_more(self):
        """The Mine | Team toggle needs a Team view that adds something."""
        self._grant(self.manager, "activity.view_own_activity")
        self._grant(self.rep, "activity.view_own_activity")
        self._grant(self.peer, "activity.view_activity")
        for user, shown in ((self.manager, True), (self.rep, False), (self.peer, True)):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                # EnsureSectionMiddleware first redirects to add ?section=.
                response = self.client.get(
                    reverse("calendar:calendar_view"), follow=True
                )
                self.assertEqual(response.status_code, 200)
                self.assertIs(response.context["team_scope_available"], shown)
                self.assertIs(b'data-scope="team"' in response.content, shown)


ALL_TYPES = ["task", "event", "meeting", "unavailability"]


class CalendarTypeSelectionTests(TestCase):
    """
    Unchecking a calendar type in the sidebar sticks after the reload, also
    when the user has no ``UserCalendarPreference`` row for it yet (e.g. a new
    user who never changed its color). The sidebar shows a type without a row
    as checked.
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
            username="planner",
            email="planner@example.com",
            password="pass",
            company=self.company,
        )
        start = timezone.now()
        end = start + datetime.timedelta(hours=1)
        for activity_type in ("task", "event", "meeting"):
            Activity.objects.create(
                subject=f"Weekly {activity_type}",
                activity_type=activity_type,
                status="not_started",
                start_datetime=start,
                end_datetime=end,
                owner=self.user,
                company=self.company,
            )
        UserAvailability.objects.create(
            user=self.user,
            from_datetime=start,
            to_datetime=end,
            reason="Dentist",
            company=self.company,
        )
        self.client.force_login(self.user)

    def _save(self, calendar_types):
        """Post the checked types, as a sidebar or My Calendars checkbox does."""
        response = self.client.post(
            reverse("calendar:save_calendar_preferences"),
            json.dumps({"calendar_types": calendar_types}),
            content_type="application/json",
        )
        self.assertEqual(response.json()["status"], "success", response.json())

    def _checked(self, **params):
        """Return the standard calendar types the sidebar renders checked."""
        response = self.client.get(
            reverse("calendar:calendar_view"), params, HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        return [cal["id"] for cal in response.context["calendars"] if cal["selected"]]

    def _event_types(self):
        """Return the event types fetched without ``calendar_types[]``."""
        response = self.client.get(
            reverse("calendar:get_calendar_events"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        data = response.json()
        self.assertEqual(data["status"], "success", data)
        return {event["calendarType"] for event in data["events"]}

    def _row(self, calendar_type):
        return UserCalendarPreference.objects.get(
            user=self.user, calendar_type=calendar_type
        )

    def test_unchecked_type_without_a_row_stays_unchecked(self):
        """Unchecking Tasks is saved as a row with the default color."""
        self._save(["event", "meeting", "unavailability"])

        self.assertEqual(self._checked(), ["event", "meeting", "unavailability"])
        task = self._row("task")
        self.assertFalse(task.is_selected)
        self.assertEqual(task.color, views.DEFAULT_CALENDAR_TYPE_COLORS["task"])
        self.assertEqual(task.company, self.company)

        self._save(ALL_TYPES)
        self.assertEqual(self._checked(), ALL_TYPES)

    def test_unchecking_keeps_the_saved_color(self):
        """A type that already has a row keeps its color when unchecked."""
        UserCalendarPreference.objects.create(
            user=self.user, calendar_type="task", color="#123456", company=self.company
        )
        self._save(["event", "meeting", "unavailability"])

        task = self._row("task")
        self.assertFalse(task.is_selected)
        self.assertEqual(task.color, "#123456")

    def test_status_color_rows_are_left_alone(self):
        """Status colors aren't calendar types: no row is added or changed."""
        UserCalendarPreference.objects.create(
            user=self.user,
            calendar_type="status_completed",
            color="#123456",
            is_selected=False,
            company=self.company,
        )
        self._save(["task"])

        self.assertEqual(
            list(
                UserCalendarPreference.objects.filter(
                    user=self.user, calendar_type__startswith="status_"
                ).values_list("calendar_type", "color", "is_selected")
            ),
            [("status_completed", "#123456", False)],
        )

    def test_unchecking_my_calendars_unchecks_every_type(self):
        """With nothing checked, no type comes back and no event is fetched."""
        self._save([])

        self.assertEqual(self._checked(), [])
        self.assertEqual(self._event_types(), set())

        self._save(ALL_TYPES)
        self.assertEqual(self._checked(), ALL_TYPES)
        self.assertEqual(self._event_types(), set(ALL_TYPES))

    def test_events_without_types_count_a_type_without_a_row_as_checked(self):
        """The events fallback matches the sidebar, not just the saved rows."""
        UserCalendarPreference.objects.create(
            user=self.user, calendar_type="task", color="#123456", company=self.company
        )

        self.assertEqual(self._checked(), ALL_TYPES)
        self.assertEqual(self._event_types(), set(ALL_TYPES))

    def test_selection_is_saved_for_the_active_company(self):
        """Rows go to the active company; another company keeps its own."""
        other = Company.objects.create(
            name="Other", email="other@example.com", country="US"
        )
        session = self.client.session
        session["active_company_id"] = other.pk
        session.save()
        self._save(["event", "meeting", "unavailability"])

        self.assertEqual(self._checked(), ["event", "meeting", "unavailability"])
        self.assertEqual(self._row("task").company, other)

        session["active_company_id"] = self.company.pk
        session.save()
        self.assertEqual(self._checked(), ALL_TYPES)

    def test_display_this_only_sticks(self):
        """Display This Only on a type is still applied on the next load."""
        self.assertEqual(self._checked(display_only="task"), ["task"])
        self.assertEqual(self._checked(), ["task"])
        self.assertEqual(self._event_types(), {"task"})

    def test_display_this_only_on_a_custom_calendar_sticks(self):
        """Display This Only on a custom calendar unchecks every standard type."""
        custom = CustomCalendar.objects.create(
            user=self.user,
            name="Holidays",
            module=HorillaContentType.objects.get_for_model(Holiday),
            start_date_field="start_date",
            display_name_field="name",
            company=self.company,
        )

        self.assertEqual(self._checked(display_only=f"custom_{custom.pk}"), [])
        self.assertEqual(self._checked(), [])
        custom.refresh_from_db()
        self.assertTrue(custom.is_selected)
