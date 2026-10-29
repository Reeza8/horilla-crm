"""
My work: the signed-in user's own tasks, meetings and events, in three tabs
(Overdue, Today, Upcoming), with mark as done and undo.

"Own" is the desktop calendar's "Mine" rule: activities the user owns, is
assigned to, takes part in or hosts. Logged calls are not listed; they
record something already done. The rows are shared with the Agenda.
"""

# Standard library imports
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlencode

# First party imports (Horilla)
from horilla.db.models import Case, F, Q, When
from horilla.extension.formatting import get_datetime_formatter
from horilla.urls import reverse
from horilla.utils.translation import gettext_lazy as _
from horilla.utils.translation import pgettext_lazy
from horilla.views.generic import TemplateView
from horilla.contrib.activity.models import Activity

# Local imports
from .access import can_open
from .activities import get_type_colors
from .dates import day_label, day_start, format_time, user_now
from .navigation import agenda_url
from .records import _hidden_fields, record_url
from .registry import get_mobile_config
from .search import tel_href
from .templatetags.mobile_tags import mobile_field_value
from .views import MobilePageMixin

TODAY_TYPES = ("task", "meeting", "event")
CLOSED_STATUSES = ("completed", "cancelled")
UPCOMING_DAYS = 7
TABS = ("overdue", "today", "upcoming")
DEFAULT_TAB = "today"
TAB_LABELS = {
    # Its own context: the shared catalog's "Overdue" reads as "delay".
    "overdue": pgettext_lazy("mobile today tab", "Overdue"),
    "today": _("Today"),
    "upcoming": _("Upcoming"),
}

# Status an activity goes back to when "done" is undone from the Done today
# list, where its earlier status isn't known: the starting one of its type.
REOPEN_STATUS = {"task": "not_started", "meeting": "scheduled", "event": "scheduled"}


def my_activities(user):
    """
    The user's own tasks, meetings and events (the desktop calendar's "Mine"),
    with ``_when``: the due date of a task, the start of the others.
    """
    mine = (
        Q(owner=user)
        | Q(assigned_to=user)
        | Q(participants=user)
        | Q(meeting_host=user)
    )
    return with_when(
        Activity.objects.filter(activity_type__in=TODAY_TYPES).filter(mine)
    )


def with_when(activities):
    """
    ``activities`` with ``_when``: the due date of a task, the start of the
    others. Filtering on the many-to-many fields can repeat a row; a subquery
    on the ids keeps the annotation and ordering free of DISTINCT.
    """
    return Activity.objects.filter(pk__in=activities.values("pk")).annotate(
        _when=Case(
            When(activity_type="task", then=F("due_datetime")),
            default=F("start_datetime"),
        )
    )


def is_all_day(activity):
    """True for an all-day meeting or event."""
    return activity.activity_type != "task" and activity.is_all_day


@dataclass
class ActivityRow:
    """One activity on My work or the Agenda."""

    obj: object
    label: str
    color: str
    title: str
    when: str
    late: bool
    all_day: bool
    done: bool
    record_name: str
    record_url: str
    phone_href: str
    detail_url: str
    status_url: str
    undo_status: str
    # Whose activity it is, on the Agenda's Team view.
    person: str = ""
    # False when the user may see the activity but not mark it done.
    can_change: bool = True


class ActivityRows:
    """
    Builds rows for one user: formatting, colors and related records.
    ``detail_query`` tells the details sheet which page it was opened from,
    so an edit returns there.
    """

    def __init__(self, user, now, detail_query=""):
        self.user = user
        self.now = now
        self.detail_query = detail_query
        self.colors = get_type_colors(user)
        self.formatter = get_datetime_formatter()
        self._records = {}

    def time_text(self, value):
        """A time of day, as the user formats it."""
        return format_time(self.user, value, self.now.tzinfo)

    def when_text(self, activity, with_date):
        """The time (and the date when it isn't today) of an activity."""
        when = activity._when
        if when is None:
            return ""
        if is_all_day(activity):
            if not with_date:
                return str(_("All day"))
            return self.formatter.format(
                when.astimezone(self.now.tzinfo).date(), user=self.user
            )
        if with_date:
            return self.formatter.format(when, user=self.user)
        return self.time_text(when)

    def record(self, activity):
        """``(name, url, phone)`` of the related record when it is on the phone."""
        key = (activity.content_type_id, activity.object_id)
        if key in self._records:
            return self._records[key]
        result = ("", "", "")
        record = activity.related_object
        if record is not None:
            meta = record._meta
            config = get_mobile_config(meta.app_label, meta.model_name)
            if config is not None and can_open(self.user, record):
                hidden = _hidden_fields(self.user, config.model)
                name = ""
                if config.title_field and config.title_field not in hidden:
                    name = mobile_field_value(record, config.title_field, self.user)
                phone = ""
                for field in config.phone_fields:
                    if field not in hidden:
                        phone = tel_href(getattr(record, field, ""))
                        if phone:
                            break
                result = (str(name or record), record_url(record), phone)
        self._records[key] = result
        return result

    def next_row(self, activity, day):
        """Row for the Next card; ``day`` names the day when it isn't today."""
        row = self.row(activity)
        local_day = activity._when.astimezone(self.now.tzinfo).date()
        if local_day != self.now.date():
            row.when = f"{day} {row.when}"
        return row

    def is_late(self, activity, done):
        """
        Not done and its time has passed: a task's due date, or the end of a
        meeting or event (one still running isn't late). All-day ones aren't.
        """
        if done or activity._when is None or is_all_day(activity):
            return False
        end = activity.end_datetime if activity.activity_type != "task" else None
        return (end or activity._when) < self.now

    def row(self, activity, with_date=False, when=None):
        """Row for ``activity``; ``when`` replaces the time shown."""
        record_name, url, phone = self.record(activity)
        done = activity.status == "completed"
        detail_url = reverse("mobile:activity_detail", args=[activity.pk])
        if self.detail_query:
            detail_url = f"{detail_url}?{self.detail_query}"
        return ActivityRow(
            obj=activity,
            label=activity.get_activity_type_display(),
            color=self.colors.get(activity.activity_type, ""),
            title=str(activity),
            when=when if when is not None else self.when_text(activity, with_date),
            late=self.is_late(activity, done),
            all_day=is_all_day(activity),
            done=done,
            record_name=record_name,
            record_url=url,
            phone_href=phone,
            detail_url=detail_url,
            status_url=reverse("mobile:activity_status", args=[activity.pk]),
            undo_status=REOPEN_STATUS.get(activity.activity_type, "not_started"),
        )


def today_tab(value):
    """``value`` when it is a tab of My work, else the default tab."""
    return value if value in TABS else DEFAULT_TAB


def build_today(user, tab, done_open=False):
    """
    Context of My work for ``tab``. ``done_open`` keeps the Done today list
    expanded (after something in it was reopened).
    """
    now = user_now(user)
    today = now.date()
    start = day_start(today, now.tzinfo)
    tomorrow = start + timedelta(days=1)
    upcoming_end = start + timedelta(days=UPCOMING_DAYS + 1)
    activities = my_activities(user)
    open_ = activities.exclude(status__in=CLOSED_STATUSES)
    overdue = open_.filter(_when__lt=start)
    todays = open_.filter(_when__gte=start, _when__lt=tomorrow)
    state = {"view": "today", "tab": tab}
    rows = ActivityRows(user, now, urlencode({"from": "today", "tab": tab}))
    context = {
        "tab": tab,
        "state": state,
        "tab_choices": [(key, TAB_LABELS[key]) for key in TABS],
        "counts": {"overdue": overdue.count(), "today": todays.count()},
        "upcoming_days": UPCOMING_DAYS,
        "done_open": done_open,
    }

    if tab == "overdue":
        context["rows"] = [
            rows.row(a, with_date=True) for a in overdue.order_by("_when", "pk")
        ]
    elif tab == "upcoming":
        days = []
        current = None
        for activity in open_.filter(
            _when__gte=tomorrow, _when__lt=upcoming_end
        ).order_by("_when", "pk"):
            day = activity._when.astimezone(now.tzinfo).date()
            if current is None or current["date"] != day:
                current = {
                    "date": day,
                    "label": day_label(user, day, today),
                    "rows": [],
                }
                days.append(current)
            current["rows"].append(rows.row(activity))
        context["days"] = days
        context["later_url"] = agenda_url(today + timedelta(days=UPCOMING_DAYS + 1))
    else:
        context["rows"] = [rows.row(a) for a in todays.order_by("_when", "pk")]
        # The nearest timed activity still ahead, today or in the coming days.
        upcoming_timed = (
            open_.filter(_when__gte=now, _when__lt=upcoming_end)
            .filter(Q(activity_type="task") | Q(is_all_day=False))
            .order_by("_when", "pk")
            .first()
        )
        context["next_row"] = (
            rows.next_row(
                upcoming_timed,
                day_label(
                    user, upcoming_timed._when.astimezone(now.tzinfo).date(), today
                ),
            )
            if upcoming_timed
            else None
        )
        # Marked done today (from any tab), so a slip can be undone.
        context["done_rows"] = [
            rows.row(a)
            for a in activities.filter(
                status="completed", updated_at__gte=start
            ).order_by("-updated_at", "-pk")
        ]
    return context


class MobileTodayView(MobilePageMixin, TemplateView):
    """The My work page; ``?tab=`` picks Overdue, Today or Upcoming."""

    template_name = "mobile/today.html"

    def get_template_names(self):
        """Only the tab's content for an HTMX request."""
        if self.request.headers.get("HX-Request") == "true":
            return ["mobile/partials/today_content.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        """Rows of the selected tab."""
        context = super().get_context_data(**kwargs)
        tab = today_tab(self.request.GET.get("tab"))
        context.update(build_today(self.request.user, tab))
        return context
