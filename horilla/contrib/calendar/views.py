"""Views for the calendar app in Horilla"""

# Standard library imports
import datetime
import json
import re

# Third-party imports (Django)
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models.functions import Coalesce
from django.utils.dateparse import parse_datetime
from django.utils.encoding import force_str

# First party imports (Horilla)
from horilla.auth.models import User
from horilla.contrib.activity.methods import get_related_record_urls
from horilla.contrib.activity.models import Activity
from horilla.contrib.core.utils import get_allowed_user_ids, get_user_field_permission
from horilla.contrib.generics.templatetags.horilla_tags._shared import (
    format_datetime_value,
)
from horilla.contrib.generics.views import (
    HorillaSingleDeleteView,
    HorillaSingleFormView,
)
from horilla.contrib.generics.views.details import check_record_change_access
from horilla.contrib.generics.views.helpers.queryset_utils import (
    apply_conditions,
    get_granted_access_filter,
    get_queryset_for_module,
)
from horilla.contrib.utils.middlewares import _thread_local
from horilla.db.models import Q
from horilla.shortcuts import render
from horilla.urls import reverse_lazy
from horilla.utils import timezone
from horilla.utils.decorators import (
    htmx_required,
    method_decorator,
    permission_required_or_denied,
)
from horilla.utils.functional import cached_property  # type: ignore
from horilla.utils.translation import gettext as _
from horilla.views.generic import TemplateView, View
from horilla.web import HxTriggerResponse, JsonResponse, ScriptResponse

# Local imports
from .forms import CustomCalendarForm
from .models import (
    CustomCalendar,
    CustomCalendarCondition,
    UserAvailability,
    UserCalendarPreference,
)

# Default sidebar/checkbox colors per calendar type (keep in sync with calendar UI).
DEFAULT_CALENDAR_TYPE_COLORS = {
    "task": "#3B82F6",
    "event": "#10B981",
    "meeting": "#F50CCE",
    "unavailability": "#F5E614",
}

# Default "Color by: Status" colors; user overrides are UserCalendarPreference rows.
DEFAULT_STATUS_COLORS = {
    "status_completed": "#10B981",
    "status_pending": "#F97316",
}

TEXT_COLOR_PREFIX = "text_"
DEFAULT_TEXT_COLOR = "#FFFFFF"
HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _related_record_urls(activities, user):
    """
    Map each related record's ``(content_type_id, object_id)`` to its detail
    URL if the user may open it, else "". The records are checked together, so
    a month of activities on hundreds of records costs a few queries per
    related model rather than a few per record.
    """
    records = {}
    for activity in activities:
        key = (activity.content_type_id, activity.object_id)
        if all(key) and key not in records and activity.related_object:
            records[key] = activity.related_object
    return get_related_record_urls(records, user)


def _choice_labels(model, field_name):
    """
    Return ``{value: label}`` for a choices field, as get_<field>_display()
    renders them. That method rebuilds and hashes the lazy labels on every
    call, which adds up over a month of events.
    """
    return {
        value: force_str(label, strings_only=True)
        for value, label in model._meta.get_field(field_name).flatchoices
    }


def _pk_url(url_method):
    """
    Return ``activity -> str(url_method(activity))`` for an Activity URL method
    that depends only on the pk, such as get_detail_url().

    Reversing a URL per event is a large share of a busy month's response, so
    reverse once for a placeholder pk and put each event's pk in its place.
    Falls back to calling the method if the placeholder isn't in the URL
    exactly once.
    """
    placeholder = "2147483647"
    url = str(url_method(Activity(pk=int(placeholder))))
    if url.count(placeholder) != 1:
        return lambda activity: str(url_method(activity))
    prefix, suffix = url.split(placeholder)
    return lambda activity: f"{prefix}{activity.pk}{suffix}"


def _team_scope_available(user):
    """
    Return True if the calendar's Team view would show ``user`` more than
    their own activities.

    Follows the All Activities list (``HorillaListView.get_queryset``):
    ``activity.view_activity`` covers every activity in the company, while
    ``activity.view_own_activity`` covers those owned by or assigned to the
    user or anyone in a subordinate role, so it only adds something for a
    user with subordinates (or a granted-access filter on Activity).
    """
    if user.has_perm("activity.view_activity"):
        return True
    if not user.has_perm("activity.view_own_activity"):
        return False
    return (
        len(get_allowed_user_ids(user)) > 1
        or get_granted_access_filter(Activity, user, "view") is not None
    )


def _team_members(request):
    """
    Return the users the Team view can be narrowed to, for the members filter.

    Everyone in the active company with ``activity.view_activity``, otherwise
    the user and the users in subordinate roles (``activity.view_own_activity``).
    Nobody when the Team view is not available to the user.
    """
    user = request.user
    if not _team_scope_available(user):
        return User.objects.none()
    if user.has_perm("activity.view_activity"):
        company = getattr(request, "active_company", None) or user.company
        members = User.objects.filter(company=company)
    else:
        members = User.objects.filter(pk__in=get_allowed_user_ids(user))
    return (
        members.filter(is_active=True)
        .select_related("role")
        .order_by("first_name", "last_name", "pk")
    )


def _requested_member_ids(request):
    """
    Return the member ids the Team view is narrowed to, or None for everyone.

    Only ids from ``_team_members`` count, so the parameter can never reach
    beyond what the filter offers.
    """
    requested = {
        int(value) for value in request.GET.getlist("members[]") if str(value).isdigit()
    }
    if not requested:
        return None
    allowed = set(
        _team_members(request).filter(pk__in=requested).values_list("pk", flat=True)
    )
    return allowed or None


def _member_name(member):
    """Return a user's full name, falling back to the username."""
    return f"{member.first_name} {member.last_name}".strip() or member.username


def _calendar_activities(user, activity_types, team=False, member_ids=None):
    """
    Return the activities of ``activity_types`` to show on ``user``'s calendar.

    Without ``team`` ("Mine"), these are the activities the user is assigned
    to, takes part in, owns or hosts. ``team`` adds the activities the user
    may see in the All Activities list: every one with
    ``activity.view_activity``, otherwise those whose ``OWNER_FIELDS`` hold
    the user or a subordinate (``activity.view_own_activity``). Without
    either permission ``team`` adds nothing, so the request parameter can
    never widen what a user sees.

    ``member_ids`` narrows the Team view to the activities owned by or
    assigned to those users; it has no effect on Mine.
    """
    queryset = Activity.objects.filter(activity_type__in=activity_types)
    visible = (
        Q(assigned_to=user)
        | Q(participants=user)
        | Q(owner=user)
        | Q(meeting_host=user)
    )
    if team and user.has_perm("activity.view_activity"):
        activities = queryset
    else:
        if team and user.has_perm("activity.view_own_activity"):
            allowed_user_ids = list(get_allowed_user_ids(user))
            for field_name in Activity.OWNER_FIELDS:
                visible |= Q(**{f"{field_name}__in": allowed_user_ids})
            granted_query = get_granted_access_filter(Activity, user, "view")
            if granted_query is not None:
                visible |= granted_query
        activities = queryset.filter(visible)
    if team and member_ids:
        by_member = Q()
        for field_name in Activity.OWNER_FIELDS:
            by_member |= Q(**{f"{field_name}__in": member_ids})
        activities = activities.filter(by_member)
    return activities


def _requested_range(request):
    """
    Return the ``(start, end)`` window FullCalendar asks events for, or None.

    FullCalendar sends its visible range as ISO 8601 ``start``/``end`` and
    draws only what overlaps it. It gives an event without a usable end a
    default length and snaps all-day events to whole days, so the window is
    widened by a day on each side to never drop an event it would draw.
    A missing or malformed bound means no window, as before the calendar
    sent one.
    """
    try:
        start = parse_datetime(request.GET.get("start", ""))
        end = parse_datetime(request.GET.get("end", ""))
        if start is None or end is None:
            return None
        if timezone.is_naive(start):
            start = timezone.make_aware(start)
        if timezone.is_naive(end):
            end = timezone.make_aware(end)
        if start >= end:
            return None
        margin = datetime.timedelta(days=1)
        # Converted to UTC as the database stores them; a bound too close to
        # the datetime limits overflows here instead of in the query.
        return (
            (start - margin).astimezone(datetime.timezone.utc),
            (end + margin).astimezone(datetime.timezone.utc),
        )
    except (ValueError, OverflowError):
        return None


def _whole_day_span(start, end):
    """
    Return (first_day, last_day) when start..end covers whole days, else None.

    That is a start at 00:00 and an end at 23:59 (or exactly 00:00 of a later
    day, which is the same moment as the end of the day before).
    """
    if not start or not end:
        return None
    first = timezone.localtime(start)
    last = timezone.localtime(end)
    if (first.hour, first.minute) != (0, 0):
        return None
    if (last.hour, last.minute) == (23, 59):
        last_day = last.date()
    elif (last.hour, last.minute) == (0, 0) and last.date() > first.date():
        last_day = last.date() - datetime.timedelta(days=1)
    else:
        return None
    if last_day < first.date():
        return None
    return first.date(), last_day


def _all_day_fields(request, first_day, last_day):
    """FullCalendar start/end (end exclusive) and the popup texts for whole days."""
    return {
        "start": first_day.isoformat(),
        "end": (last_day + datetime.timedelta(days=1)).isoformat(),
        "start_display": (
            f"{format_datetime_value(first_day, user=request.user)} ({_('All Day')})"
        ),
        "end_display": format_datetime_value(last_day, user=request.user),
    }


def _activity_events(request, activities, team, custom_calendar=None):
    """
    Turn an Activity queryset into FullCalendar event dicts.

    The queryset is narrowed to FullCalendar's visible window. With
    ``custom_calendar`` the events take its color and are keyed to it
    (``calendarType`` ``custom_<pk>``) so the sidebar's checkbox and color
    pickers drive them; ``activityType`` still holds the real type.
    """
    date_range = _requested_range(request)
    if date_range:
        range_start, range_end = date_range
        # Same start/end fallbacks as the event payload below.
        activities = activities.alias(
            calendar_start=Coalesce("start_datetime", "due_datetime", "created_at"),
            calendar_end=Coalesce("end_datetime", "due_datetime", "created_at"),
        ).filter(
            Q(calendar_start__gte=range_start) | Q(calendar_end__gte=range_start),
            calendar_start__lt=range_end,
        )
    if team:
        # check_record_change_access() reads each owner.
        activities = activities.select_related("owner")
    activities = activities.prefetch_related("assigned_to", "related_object")
    activities = list(activities.distinct())
    can_delete = team and request.user.has_perm("activity.delete_activity")

    related_urls = _related_record_urls(activities, request.user)
    activity_type_labels = _choice_labels(Activity, "activity_type")
    status_labels = _choice_labels(Activity, "status")
    edit_url = _pk_url(Activity.get_activity_edit_url)
    delete_url = _pk_url(Activity.get_delete_url)
    detail_url = _pk_url(Activity.get_detail_url)

    events = []
    for activity in activities:
        start_dt = activity.get_start_date()
        end_dt = activity.get_end_date()
        start_display = (
            format_datetime_value(start_dt, user=request.user)
            if not isinstance(start_dt, str)
            else start_dt
        )
        end_display = (
            format_datetime_value(end_dt, user=request.user)
            if not isinstance(end_dt, str) and end_dt
            else None
        )
        due_date_display = None
        if activity.activity_type == "task" and activity.due_datetime:
            due_date_display = format_datetime_value(
                activity.due_datetime, user=request.user
            )
        # get_start_date()/get_end_date() return a translated
        # "All Day Event" label (not a datetime) for all-day
        # events/meetings, so the actual ISO timestamps for
        # FullCalendar must come from the raw datetime fields.
        start_raw = (
            activity.start_datetime or activity.due_datetime or activity.created_at
        )
        end_raw = activity.end_datetime or activity.due_datetime or activity.created_at
        all_day_fields = None
        if activity.activity_type in ["event", "meeting"] and activity.is_all_day:
            # An all-day activity spans whole days: show the dates, not the
            # "All Day Event" label with an empty end.
            all_day_fields = _all_day_fields(
                request,
                timezone.localtime(start_raw).date(),
                timezone.localtime(end_raw or start_raw).date(),
            )
            start_display = all_day_fields["start_display"]
            end_display = all_day_fields["end_display"]
        type_label = activity_type_labels.get(
            activity.activity_type, activity.activity_type
        )
        event = {
            # The type after the name tells apart e.g. a task and an event
            # that share a name.
            "title": f"{activity.title or activity.subject} - {type_label}",
            "start": start_raw.isoformat(),
            "end": end_raw.isoformat() if end_raw else None,
            "calendarType": activity.activity_type,
            "activityType": activity.activity_type,
            "activity_type_display": type_label,
            "description": activity.description or "",
            "subject": activity.subject or "",
            "assignedTo": [
                {
                    "id": user.id,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                }
                for user in activity.assigned_to.all()
            ],
            "status": activity.status,
            "status_display": status_labels.get(activity.status, activity.status),
            "start_display": start_display,
            "end_display": end_display,
            "due_date_display": due_date_display,
            "id": activity.id,
            "activityId": activity.id,
            "url": (edit_url(activity) if activity.activity_type != "email" else None),
            "deleteUrl": (
                delete_url(activity) if activity.activity_type != "email" else None
            ),
            "detailUrl": (
                detail_url(activity) if activity.activity_type != "email" else None
            ),
            "relatedUrl": related_urls.get(
                (activity.content_type_id, activity.object_id), ""
            ),
            "dueDate": (
                activity.due_datetime.isoformat()
                if activity.activity_type == "task" and activity.due_datetime
                else None
            ),
            "textColor": "#FFFFFF",
        }
        if all_day_fields:
            event["allDay"] = True
            event["start"] = all_day_fields["start"]
            event["end"] = all_day_fields["end"]
        if custom_calendar:
            calendar_type = f"custom_{custom_calendar.pk}"
            event["calendarType"] = calendar_type
            # Unique per calendar: one activity can also be on a standard type
            # or on another custom calendar.
            event["id"] = f"{calendar_type}_{activity.id}"
            event["backgroundColor"] = custom_calendar.color
            event["borderColor"] = custom_calendar.color
        if team:
            # The Team view also lists other people's
            # activities, so the popup offers only what the
            # user may do on each one, like the All Activities
            # list's row actions: Edit and Mark as Complete
            # need change access to the record, Delete needs
            # activity.delete_activity (as ActivityDeleteView).
            event["canChange"] = check_record_change_access(request.user, activity)
            event["canDelete"] = can_delete
        events.append(event)
    return events


def events_for_custom_calendar(request, cc, team=False, member_ids=None):
    """
    Return the FullCalendar events of a CustomCalendar: the chosen activity
    types of the records of its module that match its conditions.

    The records are limited the way the module's own list is (permissions and
    the calendar's conditions) and the activities by the same visibility as the
    standard calendars, so a custom calendar never shows more than they would.
    """
    model = cc.module.model_class()
    activity_types = cc.get_activity_types_list()
    if not model or not activity_types:
        return []

    records = get_queryset_for_module(request.user, model)
    records = apply_conditions(records, cc.conditions.all().order_by("sequence"))

    activities = _calendar_activities(
        request.user, activity_types, team=team, member_ids=member_ids
    ).filter(content_type=cc.module, object_id__in=records.values("pk"))
    return _activity_events(request, activities, team, custom_calendar=cc)


def _save_unchecked_calendar_types(user, company, checked_types):
    """
    Give each standard calendar type not in ``checked_types`` an unselected
    preference row if it has none. The sidebar shows a type without a row as
    checked, so otherwise unchecking it doesn't stick. Callers unselect the
    user's existing rows first.
    """
    saved_types = set(
        UserCalendarPreference.objects.filter(user=user, company=company).values_list(
            "calendar_type", flat=True
        )
    )
    for calendar_type, color in DEFAULT_CALENDAR_TYPE_COLORS.items():
        if calendar_type in checked_types or calendar_type in saved_types:
            continue
        # Not create(): a quick double click can post the same change twice.
        UserCalendarPreference.objects.get_or_create(
            user=user,
            calendar_type=calendar_type,
            company=company,
            defaults={"color": color, "is_selected": False},
        )


class CalendarView(LoginRequiredMixin, TemplateView):
    """View to display the calendar with user preferences."""

    template_name = "calendar.html"

    def get_context_data(self, **kwargs):
        """Build context with calendar types and user color preferences for display."""
        context = super().get_context_data(**kwargs)
        context["calendars"] = [
            {
                "id": "task",
                "name": _("Tasks"),
                "default_color": DEFAULT_CALENDAR_TYPE_COLORS["task"],
            },
            {
                "id": "event",
                "name": _("Events"),
                "default_color": DEFAULT_CALENDAR_TYPE_COLORS["event"],
            },
            {
                "id": "meeting",
                "name": _("Meetings"),
                "default_color": DEFAULT_CALENDAR_TYPE_COLORS["meeting"],
            },
            {
                "id": "unavailability",
                "name": _("Unavailability"),
                "default_color": DEFAULT_CALENDAR_TYPE_COLORS["unavailability"],
            },
        ]
        preferences = UserCalendarPreference.objects.filter(user=self.request.user)
        preferences_by_type = {pref.calendar_type: pref for pref in preferences}
        context["user_preferences"] = {
            pref.calendar_type: pref.color for pref in preferences
        }
        # Text colors keyed by plain calendar id ("task", "custom_5", ...).
        context["text_preferences"] = {
            pref.calendar_type[len(TEXT_COLOR_PREFIX) :]: pref.color
            for pref in preferences
            if pref.calendar_type.startswith(TEXT_COLOR_PREFIX)
        }
        context["default_text_color"] = DEFAULT_TEXT_COLOR
        context["status_colors"] = [
            {
                "id": "status_completed",
                "name": _("Completed"),
                "default_color": DEFAULT_STATUS_COLORS["status_completed"],
            },
            {
                "id": "status_pending",
                "name": _("Not completed"),
                "default_color": DEFAULT_STATUS_COLORS["status_pending"],
            },
        ]

        display_only = self.request.GET.get("display_only")
        company = (
            getattr(self.request, "active_company", None) or self.request.user.company
        )
        custom_calendars = CustomCalendar.objects.filter(
            user=self.request.user, is_active=True
        ).order_by("name")

        if display_only and display_only in [cal["id"] for cal in context["calendars"]]:
            UserCalendarPreference.objects.filter(user=self.request.user).update(
                is_selected=False
            )
            UserCalendarPreference.objects.filter(
                user=self.request.user, calendar_type=display_only
            ).update(is_selected=True)
            _save_unchecked_calendar_types(self.request.user, company, [display_only])
            for calendar in context["calendars"]:
                calendar["selected"] = calendar["id"] == display_only
            CustomCalendar.objects.filter(user=self.request.user).update(
                is_selected=False
            )
        elif (
            display_only
            and isinstance(display_only, str)
            and display_only.startswith("custom_")
        ):
            try:
                custom_pk = int(display_only.replace("custom_", "", 1))
            except ValueError:
                custom_pk = None
            if custom_pk is not None and custom_calendars.filter(pk=custom_pk).exists():
                UserCalendarPreference.objects.filter(user=self.request.user).update(
                    is_selected=False
                )
                _save_unchecked_calendar_types(self.request.user, company, [])
                for calendar in context["calendars"]:
                    calendar["selected"] = False
                CustomCalendar.objects.filter(user=self.request.user).update(
                    is_selected=False
                )
                CustomCalendar.objects.filter(
                    user=self.request.user, pk=custom_pk
                ).update(is_selected=True)
        else:
            for calendar in context["calendars"]:
                pref = preferences_by_type.get(calendar["id"])
                calendar["selected"] = pref.is_selected if pref else True

        status_field_permission = get_user_field_permission(
            self.request.user, Activity, "status"
        )
        context["status_field_permission"] = status_field_permission
        context["team_scope_available"] = _team_scope_available(self.request.user)

        context["custom_calendars"] = CustomCalendar.objects.filter(
            user=self.request.user, is_active=True
        ).order_by("name")

        return context


class SaveCalendarPreferencesView(LoginRequiredMixin, View):
    """View to save user calendar preferences via AJAX."""

    def post(self, request, *args, **kwargs):
        """Handle AJAX POST request to save calendar preferences."""
        try:
            data = json.loads(request.body)
            calendar_types = data.get("calendar_types", [])
            calendar_type = data.get("calendar_type")
            color = data.get("color")
            valid_types = {"task", "event", "meeting", "unavailability"}
            company = getattr(request, "active_company", None) or request.user.company

            if calendar_type and color:
                if calendar_type in valid_types:
                    preference, created = (
                        UserCalendarPreference.objects.update_or_create(
                            user=request.user,
                            calendar_type=calendar_type,
                            company=company,
                            defaults={
                                "color": color,
                                "is_selected": True,
                            },
                        )
                    )
                    if not created:
                        preference.color = color
                        preference.save()
                elif calendar_type in DEFAULT_STATUS_COLORS:
                    # Color-only rows: never selected, so they are not fetched as a calendar.
                    UserCalendarPreference.objects.update_or_create(
                        user=request.user,
                        calendar_type=calendar_type,
                        company=company,
                        defaults={"color": color, "is_selected": False},
                    )
                elif isinstance(calendar_type, str) and calendar_type.startswith(
                    "custom_"
                ):
                    try:
                        pk = int(calendar_type.replace("custom_", "", 1))
                    except ValueError:
                        pk = None
                    if pk is not None:
                        CustomCalendar.objects.filter(user=request.user, pk=pk).update(
                            color=color, is_selected=True
                        )

            text_color = data.get("text_color")
            if calendar_type and text_color and HEX_COLOR_RE.match(str(text_color)):
                is_custom = isinstance(calendar_type, str) and calendar_type.startswith(
                    "custom_"
                )
                text_key_ok = (
                    calendar_type in valid_types
                    or calendar_type in DEFAULT_STATUS_COLORS
                )
                if is_custom:
                    try:
                        custom_pk = int(calendar_type.replace("custom_", "", 1))
                    except ValueError:
                        custom_pk = None
                    text_key_ok = (
                        custom_pk is not None
                        and CustomCalendar.objects.filter(
                            user=request.user, pk=custom_pk
                        ).exists()
                    )
                if text_key_ok:
                    # Color-only row: never selected, so it is not fetched as a calendar.
                    UserCalendarPreference.objects.update_or_create(
                        user=request.user,
                        calendar_type=f"{TEXT_COLOR_PREFIX}{calendar_type}",
                        company=company,
                        defaults={"color": text_color, "is_selected": False},
                    )

            if "calendar_types" in data:
                UserCalendarPreference.objects.filter(user=request.user).update(
                    is_selected=False
                )
                CustomCalendar.objects.filter(user=request.user).update(
                    is_selected=False
                )
                calendar_types = data.get("calendar_types") or []
                standard_types = [ct for ct in calendar_types if ct in valid_types]
                custom_pks = []
                for ct in calendar_types:
                    if isinstance(ct, str) and ct.startswith("custom_"):
                        try:
                            custom_pks.append(int(ct.replace("custom_", "", 1)))
                        except ValueError:
                            continue

                for ct in standard_types:
                    defaults = {
                        "is_selected": True,
                        "company": company,
                    }
                    if not UserCalendarPreference.objects.filter(
                        user=request.user, calendar_type=ct
                    ).exists():
                        defaults["color"] = DEFAULT_CALENDAR_TYPE_COLORS[ct]
                    preference, created = (
                        UserCalendarPreference.objects.update_or_create(
                            user=request.user,
                            calendar_type=ct,
                            company=company,
                            defaults=defaults,
                        )
                    )

                    if not created:
                        preference.is_selected = True
                        if not preference.company:
                            preference.company = company
                        preference.save(update_fields=["is_selected", "company"])

                _save_unchecked_calendar_types(request.user, company, standard_types)

                if custom_pks:
                    CustomCalendar.objects.filter(
                        user=request.user, pk__in=custom_pks
                    ).update(is_selected=True)

            messages.success(request, _("Preferences saved successfully"))

            return JsonResponse(
                {"status": "success", "message": "Preferences saved successfully"}
            )
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)


@method_decorator(htmx_required, name="dispatch")
class TeamMembersListView(LoginRequiredMixin, View):
    """
    HTMX list of the members the Team view can be narrowed to, 20 per page.

    The Team members filter loads the next page as it is scrolled, like the
    user picker, and passes ``search`` to narrow the list by name, username or
    role. The first page also carries every matching member (for "Select all")
    and, with no search, the total.
    """

    per_page = 20

    def get(self, request, *args, **kwargs):
        """Render one page of members as filter rows."""
        members = _team_members(request)
        search = request.GET.get("search", "").strip()
        for term in search.split():
            members = members.filter(
                Q(first_name__icontains=term)
                | Q(last_name__icontains=term)
                | Q(username__icontains=term)
                | Q(role__role_name__icontains=term)
            )
        try:
            page = int(request.GET.get("page", 1))
        except ValueError:
            page = 1
        # The members already applied come first (those matching the search),
        # then the rest 20 at a time, so a chosen member is never far down.
        selected_ids = [
            int(value)
            for value in request.GET.get("selected", "").split(",")
            if value.strip().isdigit()
        ]
        picked = list(members.filter(pk__in=selected_ids)) if selected_ids else []
        if selected_ids:
            members = members.exclude(pk__in=selected_ids)
        paginator = Paginator(members, self.per_page)
        page_obj = paginator.get_page(page)

        def row(member):
            return {
                "id": member.pk,
                "name": _member_name(member),
                "role": member.role.role_name if member.role else "",
                "is_me": member.pk == request.user.pk,
            }

        listed = (picked if page_obj.number == 1 else []) + list(page_obj.object_list)
        context = {
            "items": [row(member) for member in listed],
            "page_obj": page_obj,
            "search": search,
            "selected": ",".join(str(pk) for pk in selected_ids),
        }
        return render(request, "team_members_list.html", context)


class GetCalendarEventsView(LoginRequiredMixin, View):
    """View to fetch calendar events based on user preferences."""

    def get(self, request, *args, **kwargs):
        """Handle AJAX GET request to fetch calendar events."""

        if not request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return render(request, "405.html", status=405)

        try:
            selected_types = request.GET.getlist("calendar_types[]")
            if not selected_types and "calendar_types[]" in request.GET:
                return JsonResponse({"status": "success", "events": []})

            if not selected_types:
                # Same rule as the sidebar: a type without a row is checked.
                unchecked = set(
                    UserCalendarPreference.objects.filter(
                        user=request.user, is_selected=False
                    ).values_list("calendar_type", flat=True)
                )
                selected_types = [
                    ct for ct in DEFAULT_CALENDAR_TYPE_COLORS if ct not in unchecked
                ]
                selected_types += [
                    f"custom_{pk}"
                    for pk in CustomCalendar.objects.filter(
                        user=request.user, is_selected=True, is_active=True
                    ).values_list("id", flat=True)
                ]

            events = []
            scope_team = request.GET.get("scope") == "team" and _team_scope_available(
                request.user
            )
            member_ids = _requested_member_ids(request) if scope_team else None
            if selected_types:
                # Standard activity types (not unavailability or custom calendars)
                activity_types = [
                    t
                    for t in selected_types
                    if t != "unavailability"
                    and not (isinstance(t, str) and t.startswith("custom_"))
                ]
                # A checked custom calendar shows its activities itself, so the
                # standard calendars skip those until it is unchecked.
                custom_events = []
                custom_ids = []
                for t in selected_types:
                    if isinstance(t, str) and t.startswith("custom_"):
                        try:
                            custom_ids.append(int(t.replace("custom_", "", 1)))
                        except ValueError:
                            continue
                if custom_ids:
                    for cc in CustomCalendar.objects.filter(
                        user=request.user, pk__in=custom_ids, is_active=True
                    ).select_related("module"):
                        custom_events.extend(
                            events_for_custom_calendar(
                                request, cc, scope_team, member_ids
                            )
                        )
                shown_in_custom = {event["activityId"] for event in custom_events}

                if activity_types:
                    activities = _calendar_activities(
                        request.user,
                        activity_types,
                        team=scope_team,
                        member_ids=member_ids,
                    ).exclude(pk__in=shown_in_custom)
                    events.extend(_activity_events(request, activities, scope_team))

                # Fetch UserAvailability events if selected
                if "unavailability" in selected_types:
                    unavailabilities = UserAvailability.objects.filter(
                        user=self.request.user
                    )
                    for unavailability in unavailabilities:
                        start_display = format_datetime_value(
                            unavailability.from_datetime, user=request.user
                        )
                        end_display = (
                            format_datetime_value(
                                unavailability.to_datetime, user=request.user
                            )
                            if unavailability.to_datetime
                            else None
                        )
                        # Use the event title for Google-sourced events; fall back to "User Unavailable"
                        if unavailability.reason and unavailability.reason.startswith(
                            "[Google]"
                        ):
                            event_title = unavailability.reason[len("[Google] ") :]
                        else:
                            event_title = _("User Unavailable")
                        event = {
                            "title": event_title,
                            "start": unavailability.from_datetime.isoformat(),
                            "end": (
                                unavailability.to_datetime.isoformat()
                                if unavailability.to_datetime
                                else None
                            ),
                            "start_display": start_display,
                            "end_display": end_display,
                            "calendarType": "unavailability",
                            "description": unavailability.reason
                            or "No reason provided",
                            "id": f"unavailability_{unavailability.id}",
                            "url": (
                                unavailability.update_mark_unavailability_url()
                                if unavailability.pk
                                else None
                            ),
                            "deleteUrl": (
                                unavailability.delete_mark_unavailability_url()
                                if unavailability.pk
                                else None
                            ),
                            "backgroundColor": "#F51414",
                            "borderColor": "#F51414",
                            "textColor": "#FFFFFF",
                        }
                        # No all-day switch here: a block from 00:00 to 23:59 of
                        # whole days is shown in the all-day row.
                        whole_days = _whole_day_span(
                            unavailability.from_datetime, unavailability.to_datetime
                        )
                        if whole_days:
                            event["allDay"] = True
                            event.update(_all_day_fields(request, *whole_days))
                        events.append(event)

                events.extend(custom_events)

            return JsonResponse({"status": "success", "events": events})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)


class MarkCompletedView(LoginRequiredMixin, View):
    """View to mark an activity as completed via AJAX."""

    def post(self, request, *args, **kwargs):
        """Handle AJAX POST request to mark activity as completed."""
        try:
            data = json.loads(request.body)
            event_id = data.get("event_id")
            new_status = data.get("status")

            if not event_id or not new_status:
                return JsonResponse(
                    {"status": "error", "message": "Missing event_id or status"},
                    status=400,
                )

            activity = Activity.objects.get(pk=event_id)

            if not request.user.has_perm("activity.change_own_activity"):
                return JsonResponse(
                    {
                        "status": "error",
                        "message": "Permission denied: You don't have permission to change activities",
                    },
                    status=403,
                )

            status_permission = get_user_field_permission(
                request.user, Activity, "status"
            )
            if status_permission != "readwrite":
                return JsonResponse(
                    {
                        "status": "error",
                        "message": "Permission denied: You don't have permission to change status",
                    },
                    status=403,
                )

            if new_status not in dict(Activity.STATUS_CHOICES):
                return JsonResponse(
                    {"status": "error", "message": "Invalid status"}, status=400
                )

            activity.status = new_status
            activity.save()

            messages.success(request, _("Marked as completed successfully."))
            return JsonResponse(
                {
                    "status": "success",
                }
            )

        except Activity.DoesNotExist as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=404)
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)


@method_decorator(htmx_required, name="dispatch")
class CustomCalendarFormView(LoginRequiredMixin, HorillaSingleFormView):
    """Create or update a user-defined module-backed calendar with filter conditions."""

    model = CustomCalendar
    form_class = CustomCalendarForm

    condition_fields = ["field", "operator", "value"]
    condition_model = CustomCalendarCondition
    condition_related_name = "conditions"

    condition_order_by = ["sequence"]
    content_type_field = "module"
    condition_hx_include = "#id_module"

    hidden_fields = ["is_selected"]
    full_width_fields = ["name", "color"]
    save_and_new = False
    view_id = "customcalendar-form-view"
    modal_height = False
    return_response = ScriptResponse(reload=True, close=True)

    @cached_property
    def form_url(self):
        """Return the create or update URL for the custom calendar form."""
        pk = self.kwargs.get("pk")
        if pk:
            return reverse_lazy("calendar:custom_calendar_update", kwargs={"pk": pk})
        return reverse_lazy("calendar:custom_calendar_create")

    def get_object_or_error_response(self, request):
        """Return calendar-aware reload script when the custom calendar pk is not found."""
        obj, error_response = super().get_object_or_error_response(request)
        if error_response is not None:
            error_response = ScriptResponse(reload=True, close=True)

        return obj, error_response

    def form_valid(self, form):
        if not form.instance.pk:
            form.instance.user = self.request.user
        return super().form_valid(form)


@method_decorator(htmx_required, name="dispatch")
class UserAvailabilityFormView(LoginRequiredMixin, HorillaSingleFormView):
    """View to handle marking user unavailability via a form."""

    model = UserAvailability
    form_title = _("Mark Unavailability")
    modal_height = False
    hidden_fields = ["user", "company", "is_active", "google_event_id"]
    full_width_fields = ["from_datetime", "to_datetime", "reason"]
    save_and_new = False

    @cached_property
    def form_url(self):
        """Generate the form URL based on whether it's an update or create action."""
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if pk:
            return reverse_lazy(
                "calendar:update_mark_unavailability", kwargs={"pk": pk}
            )
        return reverse_lazy("calendar:mark_unavailability")

    def get_initial(self):
        """Set initial form data (company, user, optional start date/time from request)."""
        initial = super().get_initial()
        company = (
            getattr(_thread_local, "request", None).active_company
            if hasattr(_thread_local, "request")
            else self.request.user.company
        )
        initial["company"] = company
        initial["user"] = self.request.user
        initial["company"] = company
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if not pk:
            date_str = self.request.GET.get("start_date_time")
            if date_str:
                try:
                    clicked_datetime = datetime.datetime.fromisoformat(date_str)

                    clicked_date = clicked_datetime.date()
                    clicked_time = clicked_datetime.time()

                    start_datetime = timezone.make_aware(
                        datetime.datetime.combine(clicked_date, clicked_time)
                    )

                    end_datetime = start_datetime + datetime.timedelta(minutes=30)

                    initial["from_datetime"] = start_datetime
                    initial["to_datetime"] = end_datetime

                except ValueError:
                    initial["from_datetime"] = timezone.now()
                    initial["to_datetime"] = timezone.now()
            else:
                now = timezone.now()
                initial["from_datetime"] = now
                initial["to_datetime"] = now + datetime.timedelta(minutes=30)

        return initial

    def form_valid(self, form):
        """
        Handle form submission and save the meeting.
        """

        super().form_valid(form)
        return ScriptResponse(reload=True, close=True)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("calendar.delete_userunavailability"),
    name="dispatch",
)
class UserAvailabilityDeleteView(LoginRequiredMixin, HorillaSingleDeleteView):
    """View to handle deletion of user unavailability records."""

    model = UserAvailability

    def get_post_delete_response(self):
        return HxTriggerResponse()


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("calendar.delete_customcalendar"),
    name="dispatch",
)
class CustomCalendarDeleteView(LoginRequiredMixin, HorillaSingleDeleteView):
    """View to handle deletion of custom calendar records."""

    model = CustomCalendar

    def get_post_delete_response(self):
        return HxTriggerResponse()

    def _calendar_not_found_response(self, request, exc):
        """Add error message and reload the calendar when the object is not found."""
        messages.error(request, _(str(exc)))
        return ScriptResponse(reload=True, extra="closeDeleteModeModal();")

    def get(self, request, *args, **kwargs):
        """Intercept missing-object early so we can return a calendar-aware reload."""
        try:
            self.object = self.get_object()
        except Exception as e:
            return self._calendar_not_found_response(request, e)
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """Intercept missing-object early so we can return a calendar-aware reload."""
        try:
            self.object = self.get_object()
        except Exception as e:
            return self._calendar_not_found_response(request, e)
        return self.delete(request, *args, **kwargs)
