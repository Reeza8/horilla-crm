"""Views for duplicate-rule workflows."""

# Standard library imports
from functools import cached_property

# Third-party imports (Django)
from django.contrib.auth.mixins import LoginRequiredMixin

from horilla.contrib.generics.views import (
    HorillaListView,
    HorillaModalDetailView,
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
from horilla.web import ScriptResponse

# Local imports
from ..filters import DuplicateRuleFilter
from ..forms import DuplicateRuleForm
from ..models import DuplicateRule, DuplicateRuleCondition


@method_decorator(
    permission_required_or_denied(
        "duplicates.view_duplicaterule", wrapper_id="duplicate-rule-view"
    ),
    name="dispatch",
)
class DuplicateRuleView(LoginRequiredMixin, HorillaView):
    """
    Main view for duplicate rules page
    """

    template_name = "settings/settings_list_shell.html"
    view_id = "duplicate-rule-view"
    nav_url = reverse_lazy("duplicates:duplicate_rule_nav_view")
    list_url = reverse_lazy("duplicates:duplicate_rule_list_view")


@method_decorator(htmx_required, name="dispatch")
@method_decorator(permission_required("duplicates.view_duplicaterule"), name="dispatch")
class DuplicateRuleNavView(LoginRequiredMixin, HorillaNavView):
    """
    Navbar view for Duplicate Rules
    """

    nav_description = _("Set how duplicate records are handled once matched.")
    search_url = reverse_lazy("duplicates:duplicate_rule_list_view")
    main_url = reverse_lazy("duplicates:duplicate_rule_view")
    model_name = "DuplicateRule"
    model_app_label = "duplicates"
    filterset_class = DuplicateRuleFilter
    nav_width = False
    all_view_types = False
    filter_option = False
    reload_option = False
    one_view_only = True

    @cached_property
    def new_button(self):
        """New button configuration for the navbar."""
        if self.request.user.has_perm("duplicates.add_duplicaterule"):
            return {
                "url": f"""{reverse_lazy("duplicates:duplicate_rule_create_view")}?new=true""",
                "attrs": {"id": "duplicate-rule-create"},
            }
        return None


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("duplicates.view_duplicaterule"),
    name="dispatch",
)
class DuplicateRuleListView(LoginRequiredMixin, HorillaListView):
    """
    List view of Duplicate Rules
    """

    model = DuplicateRule
    view_id = "duplicate-rule-list"
    search_url = reverse_lazy("duplicates:duplicate_rule_list_view")
    main_url = reverse_lazy("duplicates:duplicate_rule_view")
    filterset_class = DuplicateRuleFilter
    bulk_update_two_column = True
    bulk_delete_enabled = False
    bulk_select_option = False
    list_column_visibility = False
    store_ordered_ids = True

    @cached_property
    def no_record_add_button(self):
        """
        Get the configuration for the "Add" button when no record exist.
        """
        if self.request.user.has_perm("duplicates.add_duplicaterule"):
            return {
                "url": f"""{reverse_lazy("duplicates:duplicate_rule_create_view")}?new=true""",
                "attrs": 'id="duplicate-rule-create"',
            }
        return None

    columns = [
        "name",
        "content_type",
        "matching_rule",
        "action_on_create",
        "action_on_edit",
    ]

    actions = [
        {
            "action": "Edit",
            "src": "assets/icons/edit.svg",
            "img_class": "w-4 h-4",
            "permission": "duplicates.change_duplicaterule",
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
            "permission": "duplicates.delete_duplicaterule",
            "attrs": """
                    hx-get="{get_delete_url}"
                    hx-target="#deleteModeBox"
                    hx-swap="innerHTML"
                    hx-trigger="click"
                    hx-vals='{{"check_dependencies": "false"}}'
                    onclick="openDeleteModeModal()"
                """,
        },
    ]

    col_attrs = [
        {
            "name": {
                "hx-get": "{get_detail_view_url}",
                "hx-target": "#detailModalBox",
                "hx-swap": "innerHTML",
                "onclick": "openDetailModal();",
                "hx-push-url": "false",
            }
        }
    ]


@method_decorator(htmx_required, name="dispatch")
class DuplicateRuleFormView(LoginRequiredMixin, HorillaSingleFormView):
    """
    Form view for creating and updating Duplicate Rule with optional conditions
    """

    model = DuplicateRule
    form_class = DuplicateRuleForm
    full_width_fields = ["description", "alert_message"]
    condition_fields = ["field", "operator", "value", "logical_operator"]
    condition_model = DuplicateRuleCondition
    condition_field_title = _("Conditions")
    condition_related_name = "conditions"
    condition_order_by = ["order", "created_at"]
    content_type_field = "content_type"
    condition_hx_include = "[name='content_type']"
    return_response = ScriptResponse(
        close=True, reload=True, extra="$('#detailViewReloadButton').click();"
    )

    @cached_property
    def form_url(self):
        """Get the URL for the form view."""
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if pk:
            return reverse_lazy(
                "duplicates:duplicate_rule_update_view", kwargs={"pk": pk}
            )
        return reverse_lazy("duplicates:duplicate_rule_create_view")


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("duplicates.delete_duplicaterule", modal=True),
    name="dispatch",
)
class DuplicateRuleDeleteView(LoginRequiredMixin, HorillaSingleDeleteView):
    """
    Delete view for DuplicateRule
    """

    model = DuplicateRule

    def get_post_delete_response(self):
        """Return response after successful deletion"""
        return ScriptResponse(reload=True)


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("duplicates.view_duplicaterule"),
    name="dispatch",
)
class DuplicateRuleDetailView(LoginRequiredMixin, HorillaModalDetailView):
    """
    Detail view for DuplicateRule
    """

    model = DuplicateRule
    title = _("Details")
    header = {
        "title": "name",
        "subtitle": "",
        "avatar": "",
    }

    body = [
        "name",
        "description",
        "content_type",
        "matching_rule",
        "action_on_create",
        "action_on_edit",
        "show_duplicate_records",
        "alert_title",
        "alert_message",
    ]

    actions = [
        {
            "action": "Edit",
            "src": "assets/icons/edit_white.svg",
            "img_class": "w-3 h-3 flex gap-4 filter brightness-0 invert",
            "permission": "duplicates.change_duplicaterule",
            "attrs": """
                class="w-24 justify-center px-4 py-2 bg-primary-600 text-white rounded-md text-xs flex items-center gap-2 hover:bg-primary-800 transition duration-300 disabled:cursor-not-allowed"
                hx-get="{get_edit_url}?new=true"
                hx-target="#modalBox"
                hx-swap="innerHTML"
                onclick="openModal();"
            """,
        },
        {
            "action": "Delete",
            "src": "assets/icons/a4-red.svg",
            "img_class": "svg-themed w-3 h-3",
            "permission": "duplicates.delete_duplicaterule",
            "attrs": """
                    class="w-24 justify-center px-4 py-2 bg-[white] rounded-md text-xs flex items-center gap-2 border border-primary-500 hover:border-primary-600 transition duration-300 disabled:cursor-not-allowed text-primary-600"
                    hx-get="{get_delete_url}"
                    hx-target="#deleteModeBox"
                    hx-swap="innerHTML"
                    hx-trigger="click"
                    hx-vals='{{"check_dependencies": "false"}}'
                    onclick="openDeleteModeModal();"
                    hx-on::after-request="closeDetailModal();"
                """,
        },
    ]
