"""
Log activity from a record's phone page (a call, a task or a short note),
and edit them again from their details sheet.

The forms are the desktop ones (``LogCallForm``, ``TaskForm``,
``HorillaAttachmentForm``), validated and saved the way the desktop saves
them; only the template is the phone's.
"""

# Third-party imports (Django)
from django import forms
from django.contrib import messages

# First party imports (Horilla)
from horilla.shortcuts import redirect, render
from horilla.urls import reverse
from horilla.utils.translation import gettext_lazy as _
from horilla.views.generic import FormView
from horilla.web import safe_url
from horilla.contrib.activity.forms import LogCallForm, TaskForm
from horilla.contrib.activity.models import Activity
from horilla.contrib.core.models import HorillaAttachment, HorillaContentType
from horilla.contrib.generics.forms.generics import HorillaAttachmentForm
from horilla.contrib.generics.views import HorillaSingleFormView

# Local imports
from .access import (
    can_edit_activity,
    can_edit_note,
    can_log_activity,
    can_open,
    scope_queryset,
)
from .navigation import get_nav_items
from .records import record_url
from .registry import get_mobile_config
from .views import MobilePageMixin

# What each kind of activity shows on the phone besides the fields its form
# requires. The related record and the owner are filled in, not shown.
ACTIVITY_KINDS = {
    "call": {
        "form_class": LogCallForm,
        "activity_type": "log_call",
        "fields": ["subject", "call_type", "call_purpose", "status", "notes"],
        "title": _("Log a call"),
        "edit_title": _("Edit call"),
    },
    "task": {
        "form_class": TaskForm,
        "activity_type": "task",
        "fields": ["subject", "due_datetime", "task_priority", "status", "description"],
        "title": _("New task"),
        "edit_title": _("Edit task"),
    },
}

# Activity types the phone edits, and their kind. Meetings and events are
# edited from the Agenda.
EDITABLE_TYPES = {kind["activity_type"]: kind for kind in ACTIVITY_KINDS.values()}

# Fields that tie the activity to the record: taken from the URL, never from
# the posted form.
RECORD_FIELDS = ("object_id", "content_type", "activity_type")


def unavailable_page(request, message, status):
    """Phone-layout page saying why the form can't be shown."""
    return render(
        request,
        "mobile/unavailable.html",
        {
            "message": message,
            "mobile_nav_items": get_nav_items(request),
            "back_url": reverse("mobile:records"),
        },
        status=status,
    )


def record_context(record):
    """The record a form belongs to, and the way back to it."""
    config = None
    if record is not None:
        meta = record._meta
        config = get_mobile_config(meta.app_label, meta.model_name)
    return {
        "record": record,
        "config": config,
        "record_url": record_url(record) if config else reverse("mobile:records"),
    }


def mobile_next(request):
    """The posted or requested ``next`` page when it is a safe phone page, else ""."""
    value = request.POST.get("next") or request.GET.get("next") or ""
    url = safe_url(request, value, fallback="")
    return url if url.startswith(reverse("mobile:home")) else ""


def edit_context(request, record):
    """
    Like ``record_context``, but an edit opened from another page (Today)
    returns there.
    """
    context = record_context(record)
    next_url = mobile_next(request)
    if next_url:
        context.update({"record_url": next_url, "next_url": next_url})
    return context


def kind_fields(form, kind, hidden=()):
    """The kind's short field list plus any other field the form requires."""
    return [
        form[name]
        for name, field in form.fields.items()
        if name not in hidden and (name in kind["fields"] or field.required)
    ]


def note_form(form):
    """
    The desktop notes form without the file field (uploads come later) and
    with a plain text box: the desktop rich-text editor isn't loaded on the
    phone.
    """
    form.fields.pop("file", None)
    description = form.fields["description"]
    description.widget = forms.Textarea(attrs={"rows": 6})
    # Its help text describes a file's notes; here it is the note itself.
    description.help_text = ""
    return form


class RecordActionMixin:
    """
    Resolve the record from ``app_label`` / ``model_name`` / ``record_pk``,
    and answer with the phone's "unavailable" page when the user can't add
    to it.
    """

    def dispatch(self, request, *args, **kwargs):
        """Check the record before any form handling."""
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        config = get_mobile_config(kwargs["app_label"], kwargs["model_name"])
        record = None
        if config is not None:
            record = config.model.objects.filter(pk=kwargs["record_pk"]).first()
        if record is None:
            return self.unavailable(_("This record doesn't exist or was deleted."), 404)
        if not can_open(request.user, record) or not can_log_activity(
            request.user, record
        ):
            return self.unavailable(
                _("You don't have permission to add activities to this record."), 403
            )
        self.config = config
        self.record = record
        return super().dispatch(request, *args, **kwargs)

    def unavailable(self, message, status):
        """Phone-layout page saying why the form can't be shown."""
        return unavailable_page(self.request, message, status)

    def get_context_data(self, **kwargs):
        """The record the activity belongs to, and the way back to it."""
        context = super().get_context_data(**kwargs)
        context.update(record_context(self.record))
        return context


class MobileLogActivityView(RecordActionMixin, MobilePageMixin, HorillaSingleFormView):
    """Log a call or add a task to a record, with the desktop activity forms."""

    model = Activity
    template_name = "mobile/log_activity.html"
    hidden_fields = [*RECORD_FIELDS, "owner"]
    save_and_new = False

    def setup(self, request, *args, **kwargs):
        """Pick the form for ``kind`` (call or task)."""
        super().setup(request, *args, **kwargs)
        self.kind = ACTIVITY_KINDS.get(kwargs.get("kind"))

    def dispatch(self, request, *args, **kwargs):
        """Unknown kinds are not found."""
        if self.kind is None:
            return self.unavailable(_("This page doesn't exist."), 404)
        return super().dispatch(request, *args, **kwargs)

    def has_permission(self):
        """Access is decided by the record (``RecordActionMixin``)."""
        return True

    def get_form_class(self):
        """The desktop form for this kind of activity, with its extensions."""
        self.form_class = self.kind["form_class"]
        return super().get_form_class()

    def record_values(self):
        """Values tying the activity to the record."""
        content_type = HorillaContentType.objects.get_for_model(self.record)
        return {
            "object_id": str(self.record.pk),
            "content_type": str(content_type.pk),
            "activity_type": self.kind["activity_type"],
        }

    def get_initial(self):
        """Pre-fill the record, the type and the owner, as the desktop views do."""
        initial = super().get_initial()
        initial.update(self.record_values())
        initial["owner"] = self.request.user.pk
        return initial

    def get_form_kwargs(self):
        """Posted data always carries this record, whatever the hidden inputs say."""
        kwargs = super().get_form_kwargs()
        if "data" in kwargs:
            data = kwargs["data"].copy()
            data.update(self.record_values())
            if not data.get("owner"):
                data["owner"] = str(self.request.user.pk)
            kwargs["data"] = data
        return kwargs

    def get_form(self, form_class=None):
        """The owner is filled in; the phone doesn't ask for it."""
        form = super().get_form(form_class)
        if "owner" in form.fields:
            form.fields["owner"].widget = forms.HiddenInput()
        return form

    def get_context_data(self, **kwargs):
        """Fields to show: the kind's short list plus any field the form requires."""
        context = super().get_context_data(**kwargs)
        context["shown_fields"] = kind_fields(
            context["form"], self.kind, self.hidden_fields
        )
        context["page_title"] = self.kind["title"]
        return context

    def form_valid(self, form):
        """Save through the desktop form view, then go back to the record."""
        response = super().form_valid(form)
        if form.errors or not getattr(self.object, "pk", None):
            return response
        return redirect(record_url(self.record))


class MobileNoteView(RecordActionMixin, MobilePageMixin, FormView):
    """Add a short text note to a record, saved like the desktop notes."""

    template_name = "mobile/log_activity.html"
    form_class = HorillaAttachmentForm

    def get_form(self, form_class=None):
        """The desktop notes form, trimmed for the phone."""
        return note_form(super().get_form(form_class))

    def get_context_data(self, **kwargs):
        """Show every field of the trimmed notes form."""
        context = super().get_context_data(**kwargs)
        context["shown_fields"] = list(context["form"])
        context["page_title"] = _("New note")
        return context

    def form_valid(self, form):
        """Attach the note to the record, as the desktop notes view does."""
        note = form.save(commit=False)
        note.created_by = self.request.user
        note.content_type = HorillaContentType.objects.get_for_model(self.record)
        note.object_id = self.record.pk
        note.company = self.request.active_company
        note.save()
        messages.success(
            self.request,
            _("%(title)s created successfully.") % {"title": note.title},
        )
        return redirect(record_url(self.record))


class MobileEditActivityView(MobilePageMixin, HorillaSingleFormView):
    """
    Edit a logged call or a task with the desktop form. The phone shows the
    same fields as when adding it; every other field keeps its saved value.
    """

    model = Activity
    template_name = "mobile/log_activity.html"
    hidden_fields = [*RECORD_FIELDS, "owner"]
    save_and_new = False

    def dispatch(self, request, *args, **kwargs):
        """Check the activity before any form handling."""
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        queryset = Activity.objects.filter(pk=kwargs["pk"])
        activity = scope_queryset(request.user, queryset).first()
        self.kind = EDITABLE_TYPES.get(activity.activity_type) if activity else None
        if self.kind is None:
            return unavailable_page(
                request, _("This item doesn't exist or you can't view it."), 404
            )
        if not can_edit_activity(request.user, activity):
            return unavailable_page(
                request, _("You don't have permission to edit this item."), 403
            )
        self.record = activity.related_object
        return super().dispatch(request, *args, **kwargs)

    def has_permission(self):
        """Access is decided in ``dispatch``."""
        return True

    def get_form_class(self):
        """The desktop form for this kind of activity, with its extensions."""
        self.form_class = self.kind["form_class"]
        return super().get_form_class()

    def get_form(self, form_class=None):
        """
        Fields the phone doesn't show are disabled: Django then keeps their
        saved values and ignores anything posted for them.
        """
        form = super().get_form(form_class)
        shown = {
            field.name for field in kind_fields(form, self.kind, self.hidden_fields)
        }
        for name, field in form.fields.items():
            if name not in shown:
                field.disabled = True
        return form

    def get_context_data(self, **kwargs):
        """The same fields as when the activity was added."""
        context = super().get_context_data(**kwargs)
        context.update(edit_context(self.request, self.record))
        context["shown_fields"] = kind_fields(
            context["form"], self.kind, self.hidden_fields
        )
        context["page_title"] = self.kind["edit_title"]
        return context

    def form_valid(self, form):
        """Save through the desktop form view, then go back to the record."""
        response = super().form_valid(form)
        if form.errors:
            return response
        return redirect(edit_context(self.request, self.record)["record_url"])


class MobileEditNoteView(MobilePageMixin, FormView):
    """Edit a note's title and text with the desktop notes form."""

    template_name = "mobile/log_activity.html"
    form_class = HorillaAttachmentForm

    def dispatch(self, request, *args, **kwargs):
        """Check the note and its record before any form handling."""
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        note = HorillaAttachment.objects.filter(pk=kwargs["pk"]).first()
        record = note.related_object if note is not None else None
        if record is None or not can_open(request.user, record):
            return unavailable_page(
                request, _("This item doesn't exist or you can't view it."), 404
            )
        if not can_edit_note(request.user, note, record):
            return unavailable_page(
                request, _("You don't have permission to edit this item."), 403
            )
        self.note = note
        self.record = record
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        """Bind the saved note."""
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.note
        return kwargs

    def get_form(self, form_class=None):
        """The desktop notes form, trimmed for the phone; the file is kept."""
        return note_form(super().get_form(form_class))

    def get_context_data(self, **kwargs):
        """Show every field of the trimmed notes form."""
        context = super().get_context_data(**kwargs)
        context.update(edit_context(self.request, self.record))
        context["shown_fields"] = list(context["form"])
        context["page_title"] = _("Edit note")
        return context

    def form_valid(self, form):
        """Save the note and go back to its record."""
        note = form.save()
        messages.success(
            self.request,
            _("%(title)s updated successfully.") % {"title": note.title},
        )
        return redirect(edit_context(self.request, self.record)["record_url"])
