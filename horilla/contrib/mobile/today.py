"""
Today: the signed-in user's own tasks, meetings and events, in three tabs
(Overdue, Today, Upcoming), with mark as done and undo.

"Own" is the desktop calendar's "Mine" rule: activities the user owns, is
assigned to, takes part in or hosts. Logged calls are not listed; they
record something already done.
"""

# Standard library imports
import json
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

# First party imports (Horilla)
from horilla.apps import apps
from horilla.db.models import Case, F, Q, When
from horilla.extension.formatting import get_datetime_formatter
from horilla.shortcuts import render
from horilla.urls import NoReverseMatch, reverse
from horilla.utils import timezone
from horilla.utils.translation import gettext_lazy as _
from horilla.utils.translation import pgettext_lazy
from horilla.views.generic import TemplateView, View
from horilla.web import HttpResponse
from horilla.contrib.activity.models import Activity
from horilla.contrib.generics.history import is_record_locked

# Local imports
from .access import can_edit_activity, can_open
from .activities import get_type_colors
from .log_activity import unavailable_page
from .records import _hidden_fields, record_url
from .registry import get_mobile_config
from .search import tel_href
from .templatetags.mobile_tags import mobile_field_value
from .views import MobilePageMixin

TODAY_TYPES = ("task", "meeting", "event")
CLOSED_STATUSES = ("completed", "cancelled")
UPCOMING_DAYS = 7
# Day headings: weekday, day and month name, in the user's calendar.
LONG_DATE_FORMAT = "%A %-d %B"
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


def user_now(user):
    """Now in the user's time zone (their profile's, else the server's)."""
    zone = getattr(user, "time_zone", None)
    if zone:
        try:
            return timezone.now().astimezone(ZoneInfo(zone))
        except Exception:  # pylint: disable=broad-except
            pass
    return timezone.localtime()


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
    # Filtering on the many-to-many fields can repeat a row; a subquery on the
    # ids keeps the annotation and ordering free of DISTINCT.
    ids = Activity.objects.filter(activity_type__in=TODAY_TYPES).filter(mine)
    return Activity.objects.filter(pk__in=ids.values("pk")).annotate(
        _when=Case(
            When(activity_type="task", then=F("due_datetime")),
            default=F("start_datetime"),
        )
    )


def short_time_format(user):
    """The user's (else the company's) time format, without seconds."""
    company = getattr(user, "company", None)
    fmt = (
        getattr(user, "time_format", None)
        or getattr(company, "time_format", None)
        or "%H:%M"
    )
    return fmt.replace(":%S", "")


@dataclass
class TodayRow:
    """One activity on the Today page."""

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


class TodayRows:
    """Builds rows for one user: formatting, colors and related records."""

    def __init__(self, user, now):
        self.user = user
        self.now = now
        self.colors = get_type_colors(user)
        self.formatter = get_datetime_formatter()
        self.time_format = short_time_format(user)
        self._records = {}

    def when_text(self, activity, with_date):
        """The time (and the date when it isn't today) of an activity."""
        when = activity._when
        if when is None:
            return ""
        local = when.astimezone(self.now.tzinfo)
        if activity.activity_type in ("meeting", "event") and activity.is_all_day:
            if not with_date:
                return str(_("All day"))
            return self.formatter.format(local.date(), user=self.user)
        if with_date:
            return self.formatter.format(when, user=self.user)
        # As a datetime, so a calendar extension formats it like other dates
        # (Jalali: 24-hour, Persian digits).
        return self.formatter.format_datetime(local, self.time_format, user=self.user)

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

    def row(self, activity, with_date=False):
        """Row for ``activity``."""
        record_name, url, phone = self.record(activity)
        done = activity.status == "completed"
        when = activity._when
        return TodayRow(
            obj=activity,
            label=activity.get_activity_type_display(),
            color=self.colors.get(activity.activity_type, ""),
            title=str(activity),
            when=self.when_text(activity, with_date),
            late=bool(
                not done
                and when is not None
                and when < self.now
                and not (activity.activity_type != "task" and activity.is_all_day)
            ),
            all_day=activity.activity_type != "task" and activity.is_all_day,
            done=done,
            record_name=record_name,
            record_url=url,
            phone_href=phone,
            detail_url=reverse("mobile:activity_detail", args=[activity.pk]),
            status_url=reverse("mobile:activity_status", args=[activity.pk]),
            undo_status=REOPEN_STATUS.get(activity.activity_type, "not_started"),
        )


def build_today(user, tab, done_open=False):
    """
    Context of the Today page for ``tab``. ``done_open`` keeps the Done today
    list expanded (after something in it was reopened).
    """
    now = user_now(user)
    day_start = datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)
    tomorrow = day_start + timedelta(days=1)
    upcoming_end = day_start + timedelta(days=UPCOMING_DAYS + 1)
    activities = my_activities(user)
    open_ = activities.exclude(status__in=CLOSED_STATUSES)
    overdue = open_.filter(_when__lt=day_start)
    today = open_.filter(_when__gte=day_start, _when__lt=tomorrow)
    rows = TodayRows(user, now)
    context = {
        "tab": tab,
        "tab_choices": [(key, TAB_LABELS[key]) for key in TABS],
        "counts": {"overdue": overdue.count(), "today": today.count()},
        "today_label": long_date(user, now.date()),
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
                current = {"date": day, "label": day_label(user, day, now), "rows": []}
                days.append(current)
            current["rows"].append(rows.row(activity))
        context["days"] = days
        context["desktop_url"] = desktop_calendar_url()
    else:
        today_rows = [rows.row(a) for a in today.order_by("_when", "pk")]
        context["rows"] = today_rows
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
                    user, upcoming_timed._when.astimezone(now.tzinfo).date(), now
                ),
            )
            if upcoming_timed
            else None
        )
        # Marked done today (from any tab), so a slip can be undone.
        context["done_rows"] = [
            rows.row(a)
            for a in activities.filter(
                status="completed", updated_at__gte=day_start
            ).order_by("-updated_at", "-pk")
        ]
    return context


def long_date(user, day):
    """Weekday, day and month name, e.g. "Thursday 22 October"."""
    return get_datetime_formatter().format_date(day, LONG_DATE_FORMAT, user=user)


def day_label(user, day, now):
    """ "Tomorrow", or the weekday, day and month."""
    if day == now.date() + timedelta(days=1):
        return str(_("Tomorrow"))
    return long_date(user, day)


def desktop_calendar_url():
    """The desktop calendar when installed, else the desktop activity list."""
    names = ["activity:activity_view"]
    if apps.is_installed("horilla.contrib.calendar"):
        names.insert(0, "calendar:calendar_view")
    for name in names:
        try:
            return reverse(name)
        except NoReverseMatch:
            continue
    return ""


class MobileTodayView(MobilePageMixin, TemplateView):
    """The My work page; ``?tab=`` picks Overdue, Today or Upcoming."""

    template_name = "mobile/today.html"

    def get_tab(self):
        """The requested tab, Today by default."""
        tab = self.request.GET.get("tab", DEFAULT_TAB)
        return tab if tab in TABS else DEFAULT_TAB

    def get_template_names(self):
        """Only the tab's content for an HTMX request."""
        if self.request.headers.get("HX-Request") == "true":
            return ["mobile/partials/today_content.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        """Rows of the selected tab."""
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context.update(build_today(user, self.get_tab()))
        return context


class MobileActivityStatusView(MobilePageMixin, View):
    """
    Mark an activity done, or undo it. Saved like the desktop status update
    (the status only, refused on locked records); allowed to users who may
    change the activity. Answers with the tab's refreshed content and a toast
    that can undo the change.
    """

    def post(self, request, *args, **kwargs):
        """Set ``status`` on the activity, then re-render ``tab``."""
        activity = (
            Activity.objects.filter(pk=kwargs["pk"], activity_type__in=TODAY_TYPES)
            .filter(pk__in=my_activities(request.user).values("pk"))
            .first()
        )
        if activity is None:
            return unavailable_page(
                request, _("This item doesn't exist or you can't view it."), 404
            )
        if not can_edit_activity(request.user, activity) or is_record_locked(
            activity.related_object
        ):
            return unavailable_page(
                request, _("You don't have permission to edit this item."), 403
            )
        status = request.POST.get("status", "")
        if status not in dict(Activity.STATUS_CHOICES):
            return HttpResponse(status=400)

        previous = activity.status
        activity.status = status
        # ``updated_at`` too, so Done today knows when it was marked.
        activity.save(update_fields=["status", "updated_at"])

        tab = request.POST.get("tab", DEFAULT_TAB)
        tab = tab if tab in TABS else DEFAULT_TAB
        context = build_today(request.user, tab, done_open=status != "completed")
        response = render(request, "mobile/partials/today_content.html", context)
        toast = {"message": str(_("“%(title)s” marked as done.") % {"title": activity})}
        if status == "completed":
            toast["undo"] = {
                "url": reverse("mobile:activity_status", args=[activity.pk]),
                "status": previous,
                "tab": tab,
                "label": str(_("Undo")),
            }
        else:
            toast["message"] = str(
                _("“%(title)s” is open again.") % {"title": activity}
            )
        response["HX-Trigger"] = json.dumps({"mobileToast": toast})
        return response
