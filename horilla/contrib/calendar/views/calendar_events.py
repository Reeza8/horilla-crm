"""
Views for calendar events.
"""

# Standard library imports
import datetime
import json

# Third-party imports (Django)
from django.contrib import messages

from horilla.auth.mixins import LoginRequiredMixin

# First party imports (Horilla)
from horilla.contrib.activity.models import Activity
from horilla.contrib.core.utils import get_user_field_permission
from horilla.contrib.generics.templatetags.horilla_tags._shared import (
    format_datetime_value,
)
from horilla.shortcuts import render
from horilla.utils.translation import gettext as _
from horilla.views.generic import View
from horilla.web import JsonResponse

# Local imports
from ..models import CustomCalendar, UserAvailability, UserCalendarPreference
from .helpers import (
    DEFAULT_CALENDAR_TYPE_COLORS,
    _activity_events,
    _all_day_fields,
    _calendar_activities,
    _multi_day_span,
    _requested_member_ids,
    _team_scope_available,
    _whole_day_span,
    events_for_custom_calendar,
)


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
                    # Mine shows the user's own; a Team member filter shows
                    # those members' instead, like the activities above.
                    unavailabilities = UserAvailability.objects.all()
                    if scope_team and member_ids:
                        unavailabilities = unavailabilities.filter(
                            user__in=member_ids
                        ).select_related("user")
                    else:
                        unavailabilities = unavailabilities.filter(user=request.user)
                    for unavailability in unavailabilities:
                        is_own = unavailability.user_id == request.user.pk
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
                        if not is_own:
                            event_title = (
                                f"{unavailability.user.get_full_name()}: {event_title}"
                            )
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
                                if unavailability.pk and is_own
                                else None
                            ),
                            "deleteUrl": (
                                unavailability.delete_mark_unavailability_url()
                                if unavailability.pk and is_own
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
                        else:
                            # Spans midnight (e.g. 2 Oct 10:00 -> 3 Oct 12:00):
                            # one bar across the days in the all-day row; the
                            # popup keeps the exact start and end times.
                            multi_day = _multi_day_span(
                                unavailability.from_datetime,
                                unavailability.to_datetime,
                            )
                            if multi_day:
                                event["allDay"] = True
                                event["start"] = multi_day[0].isoformat()
                                event["end"] = (
                                    multi_day[1] + datetime.timedelta(days=1)
                                ).isoformat()
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
