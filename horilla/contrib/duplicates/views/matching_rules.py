"""Views for matching-rule workflows."""

# Standard library imports
import json
from functools import cached_property

# Third-party imports (Django)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View

# First party imports (Horilla)
from horilla.apps import apps

# First party imports (Horilla)
from horilla.contrib.core.models import HorillaContentType
from horilla.contrib.generics.views import (
    HorillaNavView,
    HorillaSingleDeleteView,
    HorillaSingleFormView,
    HorillaView,
)
from horilla.db import models
from horilla.db.models import Prefetch
from horilla.shortcuts import render
from horilla.urls import reverse_lazy
from horilla.utils.decorators import (
    htmx_required,
    method_decorator,
    permission_required,
    permission_required_or_denied,
)
from horilla.utils.html import escape
from horilla.utils.translation import gettext_lazy as _
from horilla.web import HttpResponse, ScriptResponse

# Local imports
from ..filters import MatchingRuleFilter
from ..forms import MatchingRuleForm
from ..models import MatchingRule, MatchingRuleCriteria


@method_decorator(
    permission_required_or_denied("duplicates.view_matchingrule"),
    name="dispatch",
)
class MatchingRuleView(LoginRequiredMixin, HorillaView):
    """
    Main view for matching rules page
    """

    template_name = "duplicates/matching_rule_view.html"
    nav_url = reverse_lazy("duplicates:matching_rule_nav_view")
    list_url = reverse_lazy("duplicates:matching_rule_list_view")


@method_decorator(htmx_required, name="dispatch")
@method_decorator(permission_required("duplicates.view_matchingrule"), name="dispatch")
class MatchingRuleNavView(LoginRequiredMixin, HorillaNavView):
    """
    Navbar view for Matching Rules
    """

    nav_description = _("Define which fields are compared to detect matching records.")
    search_url = reverse_lazy("duplicates:matching_rule_list_view")
    main_url = reverse_lazy("duplicates:matching_rule_view")
    model_name = "MatchingRule"
    model_app_label = "duplicates"
    filterset_class = MatchingRuleFilter
    nav_width = False
    all_view_types = False
    filter_option = False
    reload_option = False
    one_view_only = True

    @cached_property
    def new_button(self):
        """New button configuration for the navbar."""
        if self.request.user.has_perm("duplicates.add_matchingrule"):
            return {
                "url": f"""{reverse_lazy("duplicates:matching_rule_create_view")}?new=true""",
                "attrs": {"id": "matching-rule-create"},
            }
        return None


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("duplicates.view_matchingrule"),
    name="dispatch",
)
class MatchingRuleListView(LoginRequiredMixin, View):
    """
    Accordion view for Matching Rules
    Shows matching rules in accordion format similar to Big Deal Alerts
    """

    template_name = "duplicates/matching_rule_accordion.html"

    def get_queryset(self):
        """Get all matching rules with their criteria prefetched and ordered."""

        return MatchingRule.objects.all().prefetch_related(
            Prefetch(
                "criteria",
                queryset=MatchingRuleCriteria.objects.order_by("order", "created_at"),
            ),
            "content_type",
        )

    def get(self, request, *args, **kwargs):
        """Render the accordion view."""
        matching_rules = self.get_queryset()
        context = {
            "matching_rules": matching_rules,
            "request": request,
        }
        return render(request, self.template_name, context)


@method_decorator(htmx_required, name="dispatch")
class MatchingRuleFormView(LoginRequiredMixin, HorillaSingleFormView):
    """
    Form view for creating and updating Matching Rule with criteria
    """

    model = MatchingRule
    form_class = MatchingRuleForm
    modal_height = False
    full_width_fields = ["description"]
    condition_fields = ["field_name", "matching_method", "match_blank_fields"]
    condition_model = MatchingRuleCriteria
    condition_field_title = _("Matching Criteria")
    condition_related_name = "criteria"
    condition_order_by = ["order", "created_at"]
    content_type_field = "content_type"  # Enable automatic model_name extraction
    condition_hx_include = (
        "[name='content_type']"  # Include content_type when adding condition rows
    )
    save_and_new = False

    @cached_property
    def form_url(self):
        """Get the URL for the form view."""
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if pk:
            return reverse_lazy(
                "duplicates:matching_rule_update_view", kwargs={"pk": pk}
            )
        return reverse_lazy("duplicates:matching_rule_create_view")


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("duplicates.delete_matchingrule", modal=True),
    name="dispatch",
)
class MatchingRuleDeleteView(LoginRequiredMixin, HorillaSingleDeleteView):
    """
    Delete view for MatchingRule
    """

    model = MatchingRule

    def get_post_delete_response(self):
        """Return response after successful deletion"""
        return ScriptResponse(reload=True)


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        [
            "duplicates.add_matchingrule",
            "duplicates.change_matchingrule",
        ]
    ),
    name="dispatch",
)
class MatchingRuleCriteriaFieldChoicesView(LoginRequiredMixin, View):
    """
    View to return matching rule field choices based on selected content type
    """

    def get(self, request, *args, **kwargs):
        """Return matching rules filtered by content type"""

        content_type_id = request.GET.get("content_type")

        if not content_type_id:
            return HttpResponse(
                '<select name="matching_rule" id="id_matching_rule" class="js-example-basic-single headselect w-full"><option value="">---------</option></select>'
            )

        try:
            content_type = HorillaContentType.objects.get(pk=content_type_id)
            matching_rules = MatchingRule.objects.filter(content_type=content_type)

            options = '<option value="">---------</option>'
            for rule in matching_rules:
                options += (
                    f'<option value="{escape(str(rule.pk))}">'
                    f"{escape(str(rule.name))}</option>"
                )

            # Matching rule select (ensure Select2 is re-initialized when swapped)
            select_html = (
                '<select name="matching_rule" id="id_matching_rule" '
                'class="js-example-basic-single headselect w-full" '
                "hx-on::load=\"if(window.jQuery){var $el=jQuery(this);try{if($el.data('select2')){$el.select2('destroy');}}catch(e){} "
                "var next=$el.next(); if(next && next.hasClass && next.hasClass('select2')){next.remove();} "
                'if(jQuery.fn.select2){$el.select2();}}">'
                f"{options}"
                "</select>"
            )

            # Additionally, update DuplicateRule Condition row-0 field choices OOB so conditions reflect module
            model_name = content_type.model
            # Build field choices for conditions (include ForeignKey fields; skip reverse relations)
            field_options = '<option value="">---------</option>'
            try:
                model_class = None
                for app_config in apps.get_app_configs():
                    try:
                        model_class = apps.get_model(
                            app_config.label, model_name.lower()
                        )
                        break
                    except (LookupError, ValueError):
                        continue
                if model_class:
                    for field in model_class._meta.get_fields():
                        # Skip reverse relations / auto-created non-concrete fields
                        if not hasattr(field, "name"):
                            continue
                        if getattr(field, "auto_created", False) and not getattr(
                            field, "concrete", False
                        ):
                            continue
                        # Skip M2M (usually not meaningful for simple rule conditions)
                        if getattr(field, "many_to_many", False):
                            continue
                        if field.name in [
                            "id",
                            "pk",
                            "created_at",
                            "updated_at",
                            "created_by",
                            "updated_by",
                            "company",
                            "additional_info",
                        ]:
                            continue
                        # Allow normal fields + ForeignKey/OneToOne
                        if getattr(field, "concrete", False) or isinstance(
                            field, (models.ForeignKey, models.OneToOneField)
                        ):
                            verbose_name = (
                                getattr(field, "verbose_name", None)
                                or field.name.replace("_", " ").title()
                            )
                            field_options += (
                                f'<option value="{escape(field.name)}">'
                                f"{escape(str(verbose_name))}</option>"
                            )
            except Exception:
                pass

            hx_vals_json = json.dumps({"model_name": model_name, "row_id": "0"})
            field_select_html = (
                '<select name="field_0" id="id_field_0" class="js-example-basic-single headselect w-full" '
                f'hx-get="{reverse_lazy("generics:get_field_value_widget")}" '
                'hx-target="#id_value_0_container" '
                'hx-swap="innerHTML" '
                f'hx-vals="{escape(hx_vals_json)}" '
                "hx-include=\"[name='field_0'],#id_value_0,[name='content_type']\" "
                'hx-trigger="change,load"'
                f">{field_options}</select>"
            )
            # OOB swap for the field container
            oob_container = f'<div id="id_field_0_container" hx-swap-oob="true">{field_select_html}</div>'

            reinit_script = """
            <script>
            (function() {
            if (!window.jQuery) return;
            function rebuildSelect2(selector) {
                var $el = jQuery(selector);
                if (!$el.length) return;
                try {
                if ($el.data('select2')) {
                    $el.select2('destroy');
                }
                } catch (e) {}
                // Remove stale Select2 DOM if any (usually inserted right after the select)
                var next = $el.next();
                if (next && next.hasClass && next.hasClass('select2')) {
                next.remove();
                }
                if (jQuery.fn.select2) {
                $el.select2();
                }
            }
            rebuildSelect2('#id_matching_rule');
            rebuildSelect2('#id_field_0');
            })();
            </script>
            """

            return HttpResponse(select_html + oob_container + reinit_script)
        except HorillaContentType.DoesNotExist:
            return HttpResponse(
                '<select name="matching_rule" id="id_matching_rule" class="js-example-basic-single headselect"><option value="">---------</option></select>'
            )
