"""
Workflow Action views module.
"""

# Standard library imports
import logging
from functools import cached_property

# Third-party imports (Django)
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View

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
from horilla.utils.translation import gettext_lazy as _

# First party imports (Horilla)
from horilla.web import HxTriggerResponse, ScriptResponse

from ..forms import WorkflowRuleForm

# Local imports
from ..models import (
    WorkflowAction,
    WorkflowCondition,
    WorkflowRule,
    WorkflowTimeTriggerAction,
)

logger = logging.getLogger(__name__)


@method_decorator(htmx_required, name="dispatch")
class WorkflowActiveToggleView(LoginRequiredMixin, View):
    """Toggle the active status of a WorkflowRule, ensuring only one active rule per model."""

    def post(self, request, pk):
        """Toggle the active status of a WorkflowRule, ensuring only one active rule per model."""

        try:
            rule = WorkflowRule.objects.get(pk=pk)
            if not request.user.has_perm("workflow.change_workflowrule"):
                return ScriptResponse(reload=True)
            rule.is_active = not rule.is_active
            rule.save(update_fields=["is_active"])
            status = _("activated") if rule.is_active else _("deactivated")
            messages.success(
                request, _(f'Workflow rule "{rule.name}" has been {status}.')
            )
        except Exception as e:
            messages.error(
                request,
                _(f"An error occurred while toggling the workflow rule: {str(e)}"),
            )
        return ScriptResponse(reload=True)


@method_decorator(htmx_required, name="dispatch")
class WorkflowCreateUpdateView(LoginRequiredMixin, HorillaSingleFormView):
    """View for creating or updating a WorkflowRule. If a 'pk' is provided in the URL, it will update the existing rule; otherwise, it will create a new one."""

    model = WorkflowRule
    form_class = WorkflowRuleForm
    template_name = "workflow_rule_create_update.html"
    full_width_fields = ["name", "model", "description"]
    modal_height = False
    save_and_new = False

    condition_fields = ["field", "operator", "value", "logical_operator"]
    condition_model = WorkflowCondition
    condition_related_name = "conditions"
    condition_order_by = ["order"]
    condition_field_title = _("When should this rule apply?")
    content_type_field = None

    def get_model_name_from_content_type(self, request=None):
        pk = self.kwargs.get("pk")
        if pk:
            rule = WorkflowRule.objects.filter(pk=pk).select_related("model").first()
            if rule and rule.model_id and hasattr(rule.model, "model"):
                return rule.model.model
        return None

    def form_valid(self, form):
        submitted = self.get_submitted_condition_data()
        has_condition = any(data.get("field") for data in submitted.values())
        if not has_condition:
            form.add_error(None, _("At least one condition is required."))
            return self.form_invalid(form)
        return super().form_valid(form)

    @cached_property
    def form_url(self):
        """Return the form action URL, which differs for create vs update based on the presence of 'pk' in the URL or GET parameters."""
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if pk:
            return reverse_lazy(
                "workflow:workflow_rule_update_view",
                kwargs={"pk": pk},
            )
        return reverse_lazy("workflow:workflow_rule_create_view")


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("workflow.delete_workflowrule", modal=True),
    name="dispatch",
)
class WorkflowDeleteView(LoginRequiredMixin, HorillaSingleDeleteView):
    """View for deleting a WorkflowRule. Displays a confirmation modal and checks for dependencies before allowing deletion."""

    model = WorkflowRule

    def get_post_delete_response(self):
        return HxTriggerResponse()


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("workflow.change_workflowrule", modal=True),
    name="dispatch",
)
class WorkflowConditionDeleteView(LoginRequiredMixin, HorillaSingleDeleteView):
    """Delete a WorkflowCondition."""

    model = WorkflowCondition

    def get_post_delete_response(self):
        return ScriptResponse(reload=True)


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("workflow.change_workflowrule", modal=True),
    name="dispatch",
)
class WorkflowActionDeleteView(LoginRequiredMixin, HorillaSingleDeleteView):
    """Delete a WorkflowAction."""

    model = WorkflowAction

    def get_post_delete_response(self):
        return ScriptResponse(reload=True)


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("workflow.change_workflowrule", modal=True),
    name="dispatch",
)
class WorkflowTimeTriggerDeleteView(LoginRequiredMixin, HorillaSingleDeleteView):
    """Delete a WorkflowTimeTriggerAction."""

    model = WorkflowTimeTriggerAction

    def get_post_delete_response(self):
        return ScriptResponse(reload=True)
