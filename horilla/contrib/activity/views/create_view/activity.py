"""
Generic (multi-type) Activity create/update form view.
"""

# Standard library imports
import datetime
from types import SimpleNamespace

# Third-party imports (Django)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.functional import cached_property  # type: ignore

from horilla.contrib.core.models import HorillaContentType
from horilla.contrib.generics.views import HorillaSingleFormView
from horilla.urls import reverse_lazy
from horilla.utils import timezone
from horilla.utils.decorators import htmx_required, method_decorator
from horilla.utils.translation import gettext_lazy as _

# First party imports (Horilla)
from horilla.web import HttpResponse, ScriptResponse

from ...forms import ActivityCreateForm
from ...models import Activity
from .meeting_helpers import generate_meeting_url, send_meeting_invites


@method_decorator(htmx_required, name="dispatch")
class ActivityCreateView(LoginRequiredMixin, HorillaSingleFormView):
    """
    Form view for creating and updating activities with dynamic fields based on activity type.
    """

    model = Activity
    form_class = ActivityCreateForm
    template_name = "activity_create_form.html"
    success_url = reverse_lazy("activity:activity_list")
    view_id = "activity-form-view"
    save_and_new = False
    full_width_fields = ["description", "notes"]

    ACTIVITY_FIELD_MAP = {
        "event": [
            "activity_type",
            "subject",
            "content_type",
            "object_id",
            "owner",
            "status",
            "title",
            "start_datetime",
            "end_datetime",
            "location",
            "is_all_day",
            "assigned_to",
            "participants",
            "description",
        ],
        "meeting": [
            "activity_type",
            "subject",
            "content_type",
            "object_id",
            "owner",
            "status",
            "title",
            "start_datetime",
            "end_datetime",
            "meeting_host",
            "is_all_day",
            "is_online",
            "location",
            "meeting_provider",
            "participants",
            "reminder",
            "description",
        ],
        "task": [
            "activity_type",
            "subject",
            "content_type",
            "object_id",
            "status",
            "owner",
            "task_priority",
            "due_datetime",
            "description",
        ],
        "email": [
            "activity_type",
            "subject",
            "content_type",
            "object_id",
            "status",
            "sender",
            "to_email",
            "email_subject",
            "body",
            "bcc",
            "sent_at",
            "scheduled_at",
            "is_sent",
            "description",
        ],
        "log_call": [
            "activity_type",
            "subject",
            "content_type",
            "object_id",
            "owner",
            "status",
            "call_duration_display",
            "call_duration_seconds",
            "call_type",
            "call_purpose",
            "notes",
            "description",
        ],
    }

    def get_initial(self):
        """Set initial activity type, related record, toggles, and calendar date/time from request."""
        initial = super().get_initial()
        is_create = not (self.kwargs.get("pk") or self.object)

        if self.request.method == "POST":
            initial["is_all_day"] = self.request.POST.get("is_all_day") == "on"
            initial["is_online"] = self.request.POST.get("is_online") == "on"
        else:
            object_id = self.request.GET.get("object_id")
            model_name = self.request.GET.get("model_name")
            all_day = self.request.GET.get("is_all_day")
            toggle_is_all_day = self.request.GET.get("toggle_is_all_day")
            date_str = self.request.GET.get("start_date_time") or self.request.GET.get(
                "date"
            )

            if is_create:
                initial["activity_type"] = (
                    self.request.GET.get("activity_type") or "event"
                )
                initial["owner"] = self.request.user
            else:
                initial["activity_type"] = getattr(
                    self.object, "activity_type", None
                ) or initial.get("activity_type", "event")

            if toggle_is_all_day == "true" and self.kwargs.get("pk"):
                initial["is_all_day"] = False
            elif all_day is not None:
                initial["is_all_day"] = all_day == "on"
            elif hasattr(self, "object") and self.object:
                initial["is_all_day"] = self.object.is_all_day

            toggle_is_online = self.request.GET.get("toggle_is_online")
            if toggle_is_online == "true" and self.kwargs.get("pk"):
                initial["is_online"] = False
            elif self.request.GET.get("is_online") is not None:
                initial["is_online"] = self.request.GET.get("is_online") == "on"
            elif hasattr(self, "object") and self.object:
                initial["is_online"] = getattr(self.object, "is_online", False)

            if (
                is_create
                and self.request.GET.get("activity_type") == "meeting"
                and self.request.GET.get("is_online") is None
            ):
                initial["is_online"] = False

            if is_create and date_str:
                try:
                    clicked_datetime = datetime.datetime.fromisoformat(
                        date_str.replace("Z", "+00:00")
                    )
                    clicked_date = clicked_datetime.date()
                    clicked_time = clicked_datetime.time()
                    if clicked_time == datetime.time.min:
                        clicked_time = datetime.time(9, 0)
                    start_datetime = timezone.make_aware(
                        datetime.datetime.combine(clicked_date, clicked_time)
                    )
                    end_datetime = start_datetime + datetime.timedelta(minutes=30)
                    initial["start_datetime"] = start_datetime
                    initial["end_datetime"] = end_datetime
                    initial["due_datetime"] = end_datetime
                except (ValueError, TypeError):
                    pass

            if object_id and model_name:
                initial["object_id"] = object_id
                content_type = HorillaContentType.objects.get(model=model_name.lower())
                initial["content_type"] = content_type.id

        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        activity_type = (
            self.request.POST.get("activity_type")
            or self.request.GET.get("activity_type")
            or (getattr(self, "object", None) and self.object.activity_type)
            or getattr(self, "activity_type", None)
        )
        if not activity_type:
            activity_type = list(self.ACTIVITY_FIELD_MAP.keys())[0]

        selected_fields = self.ACTIVITY_FIELD_MAP.get(
            activity_type, self.ACTIVITY_FIELD_MAP["event"]
        )
        kwargs["visible_fields"] = selected_fields
        kwargs["initial"] = kwargs.get("initial", {})
        kwargs["initial"]["activity_type"] = activity_type

        if self.request.method == "GET":
            kwargs["initial"] = kwargs.get("initial", {})
            for field in self.ACTIVITY_FIELD_MAP.get(
                activity_type, self.ACTIVITY_FIELD_MAP["event"]
            ):
                if field == "is_online" and field in self.request.GET:
                    kwargs["initial"][field] = self.request.GET.get("is_online") == "on"
                    continue
                if field in self.request.GET:
                    value = self.request.GET.get(field)
                    if value:
                        if field in ["start_datetime", "end_datetime"] and kwargs[
                            "initial"
                        ].get("is_all_day"):
                            continue
                        kwargs["initial"][field] = value
                elif field in self.request.GET.getlist(field):
                    values = self.request.GET.getlist(field)
                    if values:
                        kwargs["initial"][field] = values

            if (
                activity_type == "meeting"
                and "is_online" not in self.request.GET
                and not (self.kwargs.get("pk") or self.request.GET.get("id"))
            ):
                kwargs["initial"]["is_online"] = False

            for field in ["start_datetime", "end_datetime", "due_datetime"]:
                if field in self.request.GET:
                    value = self.request.GET.get(field)
                    if value:
                        kwargs["initial"][field] = value
            if "content_type" in self.request.GET:
                kwargs["initial"]["content_type"] = self.request.GET.get("content_type")
            if "object_id" in self.request.GET:
                kwargs["initial"]["object_id"] = self.request.GET.get("object_id")

            if (
                self.duplicate_mode
                and "initial" in kwargs
                and "content_type" in kwargs["initial"]
            ):
                content_type_value = kwargs["initial"]["content_type"]
                if hasattr(content_type_value, "id"):
                    kwargs["initial"]["content_type"] = content_type_value.id
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_url"] = self.form_url
        context["modal_height"] = True
        context["view_id"] = self.view_id
        activity_type = (
            self.request.POST.get("activity_type")
            or self.request.GET.get("activity_type")
            or (
                getattr(self.object, "activity_type", None)
                if getattr(self, "object", None)
                else None
            )
            or "event"
        )
        show_meeting = activity_type == "meeting"
        context["show_meeting_extras"] = show_meeting
        if show_meeting:
            instance = getattr(self, "object", None)
            existing = (
                instance.external_participants if instance and instance.pk else None
            ) or []
            if not isinstance(existing, list):
                existing = []
            context["ext_email_list"] = existing
            context["ext_email_string"] = ",".join(existing)
        return context

    @cached_property
    def form_url(self):
        """Return the create or update URL depending on whether a pk is present."""
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if pk:
            return reverse_lazy("activity:activity_edit_form", kwargs={"pk": pk})
        return reverse_lazy("activity:activity_create_form")

    def _prepare_meeting_activity(self, form):
        provider = form.cleaned_data.get("meeting_provider") or ""
        is_online = form.cleaned_data.get("is_online", False)
        start_dt = form.cleaned_data.get("start_datetime")
        end_dt = form.cleaned_data.get("end_datetime")
        external_emails = form.cleaned_data.get("external_participants") or []
        inst = form.instance
        inst.external_participants = external_emails
        inst.activity_type = "meeting"
        form._meeting_generated_url = ""
        if is_online and provider:
            inst.start_datetime = start_dt
            inst.end_datetime = end_dt
            host = inst.meeting_host or self.request.user
            bridge = SimpleNamespace(request=self.request)
            url = generate_meeting_url(bridge, provider, host, inst) or ""
            form._meeting_generated_url = url
            if url:
                inst.meeting_url = url

    def _after_meeting_activity_save(self, form):
        inst = self.object
        if not inst or not inst.pk:
            return
        generated_url = getattr(form, "_meeting_generated_url", "") or ""
        if generated_url:
            Activity.objects.filter(pk=inst.pk).update(meeting_url=generated_url)
            inst.meeting_url = generated_url
        external_emails = form.cleaned_data.get("external_participants") or []
        participant_emails = list(
            inst.participants.exclude(email="").values_list("email", flat=True)
        )
        all_recipients = list(dict.fromkeys(participant_emails + external_emails))
        if all_recipients:
            inst.start_datetime = inst.start_datetime or form.cleaned_data.get(
                "start_datetime"
            )
            inst.end_datetime = inst.end_datetime or form.cleaned_data.get(
                "end_datetime"
            )
            bridge = SimpleNamespace(request=self.request)
            send_meeting_invites(bridge, inst, all_recipients)

    def _is_calendar_request(self):
        referer = (
            self.request.META.get("HTTP_HX_CURRENT_URL")
            or self.request.META.get("HTTP_REFERER")
            or ""
        )
        return "calendar-view" in referer

    def get_object_or_error_response(self, request):
        obj, error_response = super().get_object_or_error_response(request)
        if error_response is not None and self._is_calendar_request():
            error_response = ScriptResponse(
                extra="$('#reloadMainContent').click();", close=True
            )
        return obj, error_response

    def post(self, request, *args, **kwargs):
        """Re-render the form when the is_online toggle is changed via HTMX."""
        if request.POST.get("_toggle_field") == "is_online":
            self.object = getattr(self, "object", None)
            form = self.get_form()
            context = self.get_context_data(form=form)
            return self.render_to_response(context)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        activity_type = form.cleaned_data.get("activity_type")
        is_meeting = activity_type == "meeting"
        if is_meeting:
            self._prepare_meeting_activity(form)
        if self._is_calendar_request():
            self.return_response = ScriptResponse(
                extra="$('#reloadMainContent').click();", close=True
            )
        else:
            TAB_MAP = {
                "task": "tab-tasks",
                "meeting": "tab-meetings",
                "log_call": "tab-calls",
                "event": "tab-events",
            }
            tab_id = TAB_MAP.get(activity_type)
            if tab_id:
                self.return_response = ScriptResponse(
                    extra=f"htmx.trigger('#{tab_id}','click');", close=True
                )
            else:
                self.return_response = ScriptResponse(reload=True, close=True)
        response = super().form_valid(form)
        if is_meeting:
            self._after_meeting_activity_save(form)
        return response
