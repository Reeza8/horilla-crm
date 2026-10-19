"""
Activities and notes shown on a mobile record page.

Which rows show follows the desktop record tabs: activities and notes attached
to the record or to one of its history sources (``history_q``), with
activities limited to those the user may view.
"""

# Standard library imports
import re
from dataclasses import dataclass

# Third-party imports (Django)
from django.db.models.functions import Coalesce

# First party imports (Horilla)
from horilla.apps import apps
from horilla.contrib.activity.models import Activity
from horilla.contrib.core.models import HorillaAttachment
from horilla.contrib.generics.history import history_q
from horilla.db.models import F, Q
from horilla.utils.translation import gettext_lazy as _

# Local imports
from .access import scope_queryset

# Rows shown per section on the record page.
SECTION_LIMIT = 5

# Activity types that are planned work (shown under "Open activities" until done).
PLANNED_TYPES = ("task", "meeting", "event")
CLOSED_STATUSES = ("completed", "cancelled")

# Colors when the user has not picked their own in the calendar settings. The
# activity types match the calendar's defaults.
DEFAULT_TYPE_COLORS = {
    "task": "#3B82F6",
    "event": "#10B981",
    "meeting": "#F50CCE",
    "log_call": "#B45309",
    "note": "#64748B",
}
_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def get_type_colors(user):
    """
    Return ``{type: hex color}``: the user's calendar colors for tasks, events
    and meetings when the calendar app is installed, else the defaults.
    """
    colors = dict(DEFAULT_TYPE_COLORS)
    if not apps.is_installed("horilla.contrib.calendar"):
        return colors
    preference_model = apps.get_model("calendar", "UserCalendarPreference")
    for calendar_type, color in preference_model.all_objects.filter(
        user=user, calendar_type__in=PLANNED_TYPES
    ).values_list("calendar_type", "color"):
        if color and _HEX_COLOR_RE.match(color):
            colors[calendar_type] = color
    return colors


@dataclass
class TimelineRow:
    """One activity or note row: what it is, its title, and which date to show."""

    kind: str
    label: str
    title: str
    obj: object
    date_field: str
    detail: str = ""
    all_day: bool = False
    color: str = ""


def _activity_row(activity):
    """Row for an activity, showing the date that matters for its type."""
    if activity.activity_type == "task":
        date_field = "due_datetime"
    elif activity.start_datetime:
        date_field = "start_datetime"
    else:
        date_field = "created_at"
    return TimelineRow(
        kind=activity.activity_type,
        label=activity.get_activity_type_display(),
        title=str(activity),
        obj=activity,
        date_field=date_field,
        detail=activity.description or "",
        all_day=activity.activity_type in ("meeting", "event") and activity.is_all_day,
    )


def _note_row(note):
    """Row for a note or attachment."""
    return TimelineRow(
        kind="note",
        label=_("Note"),
        title=note.title,
        obj=note,
        date_field="created_at",
        detail=note.description or "",
    )


def _record_activities(user, obj):
    """Activities attached to ``obj`` (and its history sources) that ``user`` may view."""
    queryset = Activity.objects.filter(history_q(obj, user))
    return scope_queryset(user, queryset).annotate(
        _mobile_when=Coalesce("start_datetime", "due_datetime", "created_at")
    )


def get_open_activities(user, obj, limit=SECTION_LIMIT):
    """
    Planned activities (task, meeting, event) not completed or cancelled, the
    soonest first. Returns ``(rows, has_more)``.
    """
    queryset = (
        _record_activities(user, obj)
        .filter(activity_type__in=PLANNED_TYPES)
        .exclude(status__in=CLOSED_STATUSES)
        .order_by(F("_mobile_when").asc(nulls_last=True), "pk")
    )
    activities = list(queryset[: limit + 1])
    return [_activity_row(a) for a in activities[:limit]], len(activities) > limit


def get_interactions(user, obj, limit=SECTION_LIMIT):
    """
    What already happened with the record, newest first: logged calls,
    completed tasks, meetings and events, and notes. Returns
    ``(rows, has_more)``.
    """
    activities = list(
        _record_activities(user, obj)
        .filter(Q(activity_type="log_call") | Q(status="completed"))
        .order_by(F("_mobile_when").desc(nulls_last=True), "-pk")[: limit + 1]
    )
    notes = list(
        HorillaAttachment.objects.filter(history_q(obj, user)).order_by(
            "-created_at", "-pk"
        )[: limit + 1]
    )
    dated = [(a._mobile_when, _activity_row(a)) for a in activities]
    dated += [(n.created_at, _note_row(n)) for n in notes]
    dated.sort(key=lambda item: item[0], reverse=True)
    return [row for _when, row in dated[:limit]], len(dated) > limit
