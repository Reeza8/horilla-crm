"""Views for custom calendars."""

# Third-party imports (Django)
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin

# First party imports (Horilla)
from horilla.contrib.generics.views import (
    HorillaSingleDeleteView,
    HorillaSingleFormView,
)
from horilla.urls import reverse_lazy
from horilla.utils.decorators import (
    htmx_required,
    method_decorator,
    permission_required_or_denied,
)
from horilla.utils.functional import cached_property
from horilla.utils.translation import gettext as _
from horilla.web import HxTriggerResponse, ScriptResponse

# Local imports
from ..forms import CustomCalendarForm
from ..models import CustomCalendar, CustomCalendarCondition


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
