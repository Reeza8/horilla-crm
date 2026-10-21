"""
Details of one activity or note, opened from a record page as a bottom sheet
(or as a page when opened directly).
"""

# First party imports (Horilla)
from horilla.shortcuts import render
from horilla.urls import reverse
from horilla.utils.translation import gettext_lazy as _
from horilla.views.generic import TemplateView
from horilla.contrib.activity.models import Activity
from horilla.contrib.core.models import HorillaAttachment

# Local imports
from .access import can_edit_activity, can_edit_note, can_open, scope_queryset
from .activities import get_type_colors
from .desktop import DesktopLayout
from .log_activity import EDITABLE_TYPES
from .navigation import get_nav_items
from .records import record_url
from .registry import MobileModelConfig
from .views import MobilePageMixin

# Activities aren't opted into the phone; this only tells the desktop layout
# which field is the title.
ACTIVITY_LAYOUT = MobileModelConfig(model=Activity, title_field="subject")

# Already in the sheet's header (title and type label).
HEADER_FIELDS = ("subject", "activity_type")


class DetailSheetMixin(MobilePageMixin):
    """
    Render the details as the body of the record page's sheet for an HTMX
    request, or inside the phone layout when the URL is opened directly.
    """

    def get_template_names(self):
        """Sheet body for HTMX, full page otherwise."""
        if self.request.headers.get("HX-Request") == "true":
            return ["mobile/partials/detail_sheet_body.html"]
        return ["mobile/detail_page.html"]

    def get_context_data(self, **kwargs):
        """The page's back link: the record, or Records when it can't be opened."""
        context = super().get_context_data(**kwargs)
        context["back_url"] = context.get("parent_url") or reverse("mobile:records")
        return context

    def unavailable(self):
        """Same message whether the item is gone or not the user's to see."""
        return render(
            self.request,
            "mobile/unavailable.html",
            {
                "message": _("This item doesn't exist or you can't view it."),
                "mobile_nav_items": get_nav_items(self.request),
                "back_url": reverse("mobile:records"),
            },
            status=404,
        )


class MobileActivityDetailView(DetailSheetMixin, TemplateView):
    """
    One activity with the fields its desktop Details tab shows for its type
    (and the user's own field choice there).
    """

    def get(self, request, *args, **kwargs):
        """Show the activity when the user may view it."""
        queryset = Activity.objects.filter(pk=kwargs["pk"])
        self.activity = scope_queryset(request.user, queryset).first()
        if self.activity is None:
            return self.unavailable()
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Fields, type label and color of the activity."""
        activity = self.activity
        layout = DesktopLayout(self.request, activity, ACTIVITY_LAYOUT)
        # The desktop shows the status as a stage bar; here it leads the list.
        fields = layout.get_all_fields()
        stage = layout.get_stage_field()
        if stage and stage[1] not in {name for _label, name in fields}:
            fields.insert(0, stage)
        parent = activity.related_object
        kwargs.update(
            {
                "item": activity,
                "item_title": str(activity),
                "item_label": activity.get_activity_type_display(),
                "item_color": get_type_colors(self.request.user).get(
                    activity.activity_type, ""
                ),
                "fields": [
                    (label, name) for label, name in fields if name not in HEADER_FIELDS
                ],
                "parent_url": (
                    record_url(parent)
                    if parent is not None and can_open(self.request.user, parent)
                    else ""
                ),
                "edit_url": (
                    reverse("mobile:edit_activity", args=[activity.pk])
                    if activity.activity_type in EDITABLE_TYPES
                    and can_edit_activity(self.request.user, activity)
                    else ""
                ),
            }
        )
        return super().get_context_data(**kwargs)


class MobileNoteDetailView(DetailSheetMixin, TemplateView):
    """One note with its full text and attachment."""

    def get(self, request, *args, **kwargs):
        """Show the note when the user may open the record it belongs to."""
        note = HorillaAttachment.objects.filter(pk=kwargs["pk"]).first()
        parent = note.related_object if note is not None else None
        if parent is None or not can_open(request.user, parent):
            return self.unavailable()
        self.note = note
        self.parent = parent
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """The note's text, file and who added it when."""
        kwargs.update(
            {
                "item": self.note,
                "item_title": self.note.title,
                "item_label": _("Note"),
                "item_color": get_type_colors(self.request.user).get("note", ""),
                "fields": [],
                "note": self.note,
                "parent_url": record_url(self.parent),
                "edit_url": (
                    reverse("mobile:edit_note", args=[self.note.pk])
                    if can_edit_note(self.request.user, self.note, self.parent)
                    else ""
                ),
            }
        )
        return super().get_context_data(**kwargs)
