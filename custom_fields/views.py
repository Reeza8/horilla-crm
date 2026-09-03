from django.contrib.auth.mixins import LoginRequiredMixin

from horilla.contrib.generics.views import (
    HorillaListView,
    HorillaNavView,
    HorillaSingleDeleteView,
    HorillaSingleFormView,
    HorillaView,
)
from horilla.urls import reverse_lazy
from horilla.utils.decorators import htmx_required, method_decorator
from horilla.utils.functional import cached_property

from .filters import CustomFieldDefinitionFilter
from .forms import CustomFieldDefinitionForm
from .models import CustomFieldDefinition


class CustomFieldView(LoginRequiredMixin, HorillaView):
    """Shell view for the custom fields settings page."""

    template_name = "settings/settings_list_shell.html"
    view_id = "custom-fields-view"
    nav_url = reverse_lazy("custom_fields:navbar")
    list_url = reverse_lazy("custom_fields:list")


@method_decorator(htmx_required, name="dispatch")
class CustomFieldNavbar(LoginRequiredMixin, HorillaNavView):
    """Navbar for the custom fields settings page."""

    nav_title = "Custom Fields"
    nav_description = "Define custom fields to capture additional information on Leads and Opportunities."
    search_url = reverse_lazy("custom_fields:list")
    main_url = reverse_lazy("custom_fields:view")
    filterset_class = CustomFieldDefinitionFilter
    one_view_only = True
    all_view_types = False
    reload_option = False
    model_name = "CustomFieldDefinition"
    model_app_label = "custom_fields"
    nav_width = False
    url_name = "custom_fields_list"

    @cached_property
    def new_button(self):
        return {
            "url": f"{reverse_lazy('custom_fields:create')}?new=true",
            "attrs": {"id": "custom-field-create"},
        }


@method_decorator(htmx_required, name="dispatch")
class CustomFieldListView(LoginRequiredMixin, HorillaListView):
    """List view for custom field definitions."""

    model = CustomFieldDefinition
    view_id = "custom_field_list"
    filterset_class = CustomFieldDefinitionFilter
    search_url = reverse_lazy("custom_fields:list")
    main_url = reverse_lazy("custom_fields:view")
    bulk_update_option = False
    list_column_visibility = False

    columns = [
        ("Name", "name"),
        ("Model", "content_type"),
        ("Type", "get_field_type_display"),
        ("Required", "is_required"),
        ("Order", "order"),
    ]

    @cached_property
    def no_record_add_button(self):
        return {
            "url": f"{reverse_lazy('custom_fields:create')}?new=true",
            "attrs": 'id="custom-field-create"',
        }

    actions = [
        {
            "action": "Edit",
            "src": "assets/icons/edit.svg",
            "img_class": "w-4 h-4",
            "attrs": """
                hx-get="{get_edit_url}?new=true"
                hx-target="#modalBox"
                hx-swap="innerHTML"
                onclick="openModal()"
            """,
        },
        {
            "action": "Delete",
            "src": "assets/icons/a4.svg",
            "img_class": "w-4 h-4",
            "attrs": """
                hx-post="{get_delete_url}"
                hx-target="#deleteModeBox"
                hx-swap="innerHTML"
                hx-trigger="click"
                hx-vals='{{"check_dependencies": "true"}}'
                onclick="openDeleteModeModal()"
            """,
        },
    ]


@method_decorator(htmx_required, name="dispatch")
class CustomFieldFormView(LoginRequiredMixin, HorillaSingleFormView):
    """Create / update form view for a custom field definition."""

    model = CustomFieldDefinition
    form_class = CustomFieldDefinitionForm
    modal_height = False
    form_title = "Custom Field"
    save_and_new = False

    @cached_property
    def form_url(self):
        pk = self.kwargs.get("pk")
        if pk:
            return reverse_lazy("custom_fields:edit", kwargs={"pk": pk})
        return reverse_lazy("custom_fields:create")


@method_decorator(htmx_required, name="dispatch")
class CustomFieldDeleteView(LoginRequiredMixin, HorillaSingleDeleteView):
    """Delete view for custom field definitions."""

    model = CustomFieldDefinition
