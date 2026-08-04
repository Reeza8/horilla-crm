"""
Forecast module for managing Forecast Types and Targets.

Includes views for listing, creating, updating, and deleting
forecast types and their associated conditions.
"""

# Standard library imports
from functools import cached_property

# Third-party imports (Django)
from django.contrib.auth.mixins import LoginRequiredMixin

from horilla.contrib.generics.views import (
    HorillaListView,
    HorillaNavView,
    HorillaSingleDeleteView,
    HorillaSingleFormView,
    HorillaView,
)
from horilla.urls import reverse_lazy
from horilla.utils.decorators import (
    htmx_required,
    method_decorator,
    permission_required,
    permission_required_or_denied,
)
from horilla.utils.translation import gettext_lazy as _

# First party imports (Horilla)
from horilla.web import HxTriggerResponse

# Local imports
from horilla_crm.forecast.filters import ForecastTypeFilter
from horilla_crm.forecast.forms import ForecastTypeForm
from horilla_crm.forecast.models import ForecastCondition, ForecastType


class ForecastTypeView(LoginRequiredMixin, HorillaView):
    """Displays the forecast type settings page."""

    template_name = "forecast_type/forecast_type_view.html"
    nav_url = reverse_lazy("forecast:forecast_type_nav_view")
    list_url = reverse_lazy("forecast:forecast_type_list_view")


@method_decorator(htmx_required, name="dispatch")
@method_decorator(permission_required("forecast.view_forecasttype"), name="dispatch")
class ForecastTypeNavbar(LoginRequiredMixin, HorillaNavView):
    """Navigation bar for ForecastType with optional 'New' button."""

    nav_description = _("Define the categories used to group your sales forecasts.")
    search_url = reverse_lazy("forecast:forecast_type_list_view")
    main_url = reverse_lazy("forecast:forecast_type_view")
    filterset_class = ForecastTypeFilter
    model_name = "ForecastType"
    model_app_label = "forecast"
    nav_width = False
    gap_enabled = False
    all_view_types = False
    recently_viewed_option = False
    filter_option = False
    one_view_only = True
    reload_option = False
    border_enabled = False

    @cached_property
    def new_button(self):
        """Return dictionary for the 'New' button if user has permission."""

        if self.request.user.has_perm("forecast.add_forecasttype"):
            return {
                "url": f"""{reverse_lazy("forecast:forecast_type_create_form_view")}""",
                "attrs": {"id": "type-create"},
                "title": "New",
            }
        return None


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("forecast.view_forecasttype"), name="dispatch"
)
class ForecastTypeListView(LoginRequiredMixin, HorillaListView):
    """Lists all ForecastType records with optional actions."""

    model = ForecastType
    view_id = "forecast-type-list"
    filterset_class = ForecastTypeFilter
    search_url = reverse_lazy("forecast:forecast_type_list_view")
    main_url = reverse_lazy("forecast:forecast_type_view")
    save_to_list_option = False
    bulk_select_option = False
    table_width = False
    enable_sorting = False
    table_height_as_class = "h-[calc(_100vh_-_240px_)]"
    columns = ["name", "forecast_type", "is_active"]

    actions = [
        {
            "action": "Edit",
            "src": "assets/icons/edit.svg",
            "img_class": "w-4 h-4",
            "permission": "forecast.change_forecasttype",
            "attrs": """
                        hx-get="{get_edit_url}"
                        hx-target="#modalBox"
                        hx-swap="innerHTML"
                        onclick="openModal()"
                        """,
        },
        {
            "action": "Delete",
            "src": "assets/icons/a4.svg",
            "img_class": "w-4 h-4",
            "permission": "forecast.delete_forecasttype",
            "attrs": """
                    hx-get="{get_delete_url}"
                    hx-target="#modalBox"
                    hx-swap="innerHTML"
                    onclick="openModal()"
                    """,
        },
    ]


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("forecast.add_forecasttype"), name="dispatch"
)
class ForecastTypeFormView(LoginRequiredMixin, HorillaSingleFormView):
    """Form view to create or update ForecastType records with conditions."""

    model = ForecastType
    form_class = ForecastTypeForm
    fields = ["name", "forecast_type", "description"]
    full_width_fields = ["description"]
    condition_fields = ["field", "operator", "value", "logical_operator"]
    condition_model = ForecastCondition
    condition_related_name = "conditions"
    condition_order_by = ["order", "created_at"]
    condition_field_title = _("Filter Opportunities")
    modal_height = False
    save_and_new = False

    def get_form_kwargs(self):
        """Return keyword arguments for initializing the form."""
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request

        model_name = (
            self.request.GET.get("model_name")
            or self.request.POST.get("model_name")
            or "opportunity"
        )
        if "initial" not in kwargs:
            kwargs["initial"] = {}
        kwargs["initial"]["model_name"] = model_name

        return kwargs

    @cached_property
    def form_url(self):
        """Return URL for form submission based on create or update."""
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if pk:
            return reverse_lazy(
                "forecast:forecast_type_update_form_view", kwargs={"pk": pk}
            )
        return reverse_lazy("forecast:forecast_type_create_form_view")


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("forecast.delete_forecasttype", modal=True),
    name="dispatch",
)
class ForecastTypeDeleteView(LoginRequiredMixin, HorillaSingleDeleteView):
    """Delete view for forecast types."""

    model = ForecastType

    def get_post_delete_response(self):
        return HxTriggerResponse()
