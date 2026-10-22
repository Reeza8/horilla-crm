"""
Mark an activity done from My work or the Agenda, or undo it.

Saved like the desktop status update (the status only, refused on locked
records) for users who may change the activity. The answer is the page's
refreshed content and a toast that can undo the change.
"""

# Standard library imports
import json

# First party imports (Horilla)
from horilla.shortcuts import render
from horilla.urls import reverse
from horilla.utils.translation import gettext_lazy as _
from horilla.views.generic import View
from horilla.web import HttpResponse
from horilla.contrib.activity.models import Activity
from horilla.contrib.generics.history import is_record_locked

# Local imports
from .access import can_edit_activity
from .agenda import build_agenda
from .dates import parse_day
from .log_activity import unavailable_page
from .today import TODAY_TYPES, build_today, my_activities, today_tab
from .views import MobilePageMixin

# The element the refreshed content replaces, on both pages.
CONTENT_TARGET = "#activity-content"


def refreshed_page(request, reopened):
    """
    Template and context of the page the change was made on, from the state
    its rows post (``view`` and its ``tab`` or ``date``).
    """
    user = request.user
    if request.POST.get("view") == "agenda":
        day = parse_day(user, request.POST.get("date"))
        return "mobile/partials/agenda_content.html", build_agenda(user, day)
    tab = today_tab(request.POST.get("tab"))
    # Keep Done today open after something in it was reopened.
    context = build_today(user, tab, done_open=reopened)
    return "mobile/partials/today_content.html", context


class MobileActivityStatusView(MobilePageMixin, View):
    """Set an activity's status from a row's done circle or the toast's Undo."""

    def post(self, request, *args, **kwargs):
        """Set ``status`` on one of the user's own activities, then re-render the page."""
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

        template, context = refreshed_page(request, reopened=status != "completed")
        response = render(request, template, context)
        if status == "completed":
            toast = {
                "message": str(_("“%(title)s” marked as done.") % {"title": activity}),
                "undo": {
                    "url": reverse("mobile:activity_status", args=[activity.pk]),
                    "values": {**context["state"], "status": previous},
                    "target": CONTENT_TARGET,
                    "label": str(_("Undo")),
                },
            }
        else:
            toast = {
                "message": str(_("“%(title)s” is open again.") % {"title": activity})
            }
        response["HX-Trigger"] = json.dumps({"mobileToast": toast})
        return response
