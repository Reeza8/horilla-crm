"""
Forms for the workflow app
"""

# Third-party imports (Django)
from django import forms

from horilla.contrib.generics.forms import HorillaModelForm

# First party imports (Horilla)
from horilla.utils.translation import gettext_lazy as _

# Local imports
from .models import WorkflowAction, WorkflowRule, WorkflowTimeTriggerAction


class WorkflowRuleForm(HorillaModelForm):
    """Create/edit workflow rule (module, name, triggers)."""

    field_order = [
        "name",
        "model",
        "description",
        "trigger_on_create",
        "trigger_on_edit",
        "is_active",
    ]

    class Meta:
        """Meta options for WorkflowRuleForm"""

        model = WorkflowRule
        fields = "__all__"
        keep_on_form = ("is_active",)


_INPUT_CLASS = (
    "text-color-600 p-2 placeholder:text-xs pr-[40px] w-full border border-dark-50 "
    "rounded-md focus-visible:outline-0 placeholder:text-dark-100 text-sm "
    "[transition:.3s] focus:border-primary-600"
)
_SELECT_CLASS = (
    "js-example-basic-single headselect text-color-600 p-2 placeholder:text-xs "
    "pr-[40px] w-full border border-dark-50 rounded-md focus-visible:outline-0 "
    "placeholder:text-dark-100 text-sm [transition:.3s] focus:border-primary-600"
)


_ACTION_CONFIG_FIELD_NAMES = [
    "update_field",
    "update_value",
    "task_title",
    "task_due_basis",
    "task_due_in_days",
    "task_status",
    "task_priority",
    "task_description",
    "email_template_id",
    "email_to",
    "email_also_send_to",
    "notification_template_id",
    "notification_to",
    "notification_also_notify_to",
    "notification_custom_message",
]


class ActionConfigMixin:
    """Shared hidden fields, init seeding, clean, and save logic for action_config."""

    def _inject_action_config_fields(self):
        """Add hidden action-config fields to self.fields at init time."""
        for name in _ACTION_CONFIG_FIELD_NAMES:
            self.fields[name] = forms.CharField(
                required=False, widget=forms.HiddenInput()
            )

    def _seed_action_config_initials(self):
        """Populate hidden-field initials from the saved action_config on the instance."""
        if not (self.instance and self.instance.pk):
            return
        cfg = self.instance.action_config or {}
        at = self.instance.action_type
        if at == "update_field":
            self.fields["update_field"].initial = cfg.get("field", "")
            self.fields["update_value"].initial = cfg.get("value", "")
        elif at == "assign_task":
            self.fields["task_title"].initial = cfg.get("title", "")
            self.fields["task_due_basis"].initial = cfg.get("due_basis", "")
            self.fields["task_due_in_days"].initial = cfg.get("due_in_days", "1")
            self.fields["task_status"].initial = cfg.get("status", "not_started")
            self.fields["task_priority"].initial = cfg.get("priority", "low")
            self.fields["task_description"].initial = cfg.get("description", "")
        elif at == "email":
            self.fields["email_template_id"].initial = cfg.get("template_id", "")
            self.fields["email_to"].initial = cfg.get("to", "")
            self.fields["email_also_send_to"].initial = cfg.get("also_send_to", "")
        elif at == "notification":
            self.fields["notification_template_id"].initial = cfg.get("template_id", "")
            self.fields["notification_to"].initial = cfg.get("to", "")
            self.fields["notification_also_notify_to"].initial = cfg.get(
                "also_notify_to", ""
            )
            self.fields["notification_custom_message"].initial = cfg.get(
                "custom_message", ""
            )

    def _build_action_config(self, cleaned_data):
        """Return the action_config dict built from cleaned hidden fields."""
        action_type = cleaned_data.get("action_type")
        if action_type == "update_field":
            return {
                "field": cleaned_data.get("update_field", ""),
                "value": cleaned_data.get("update_value", ""),
            }
        if action_type == "assign_task":
            return {
                "title": cleaned_data.get("task_title", ""),
                "due_basis": cleaned_data.get(
                    "task_due_basis", "record_submission_date"
                ),
                "due_in_days": cleaned_data.get("task_due_in_days", "1"),
                "status": cleaned_data.get("task_status", "not_started"),
                "priority": cleaned_data.get("task_priority", "low"),
                "description": cleaned_data.get("task_description", ""),
            }
        if action_type == "email":
            return {
                "template_id": cleaned_data.get("email_template_id", ""),
                "to": cleaned_data.get("email_to", ""),
                "also_send_to": cleaned_data.get("email_also_send_to", ""),
            }
        if action_type == "notification":
            return {
                "template_id": cleaned_data.get("notification_template_id", ""),
                "to": cleaned_data.get("notification_to", ""),
                "also_notify_to": cleaned_data.get("notification_also_notify_to", ""),
                "custom_message": cleaned_data.get("notification_custom_message", ""),
            }
        return {}

    def clean(self):
        """Build action_config from hidden fields and attach it to cleaned_data."""
        cleaned_data = super().clean()
        cleaned_data["action_config"] = self._build_action_config(cleaned_data)
        return cleaned_data

    def save(self, commit=True):
        """Persist the model with action_config from cleaned_data."""
        instance = super().save(commit=False)
        instance.action_config = self.cleaned_data.get("action_config", {})
        if commit:
            instance.save()
        return instance


class WorkflowActionForm(ActionConfigMixin, forms.ModelForm):
    """Form to create/edit a WorkflowAction; action_config is built from hidden fields."""

    class Meta:
        """Meta options for WorkflowActionForm"""

        model = WorkflowAction
        fields = ["rule", "action_type", "order"]
        widgets = {
            "rule": forms.HiddenInput(),
            "order": forms.HiddenInput(),
            "action_type": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._inject_action_config_fields()
        self._seed_action_config_initials()


class WorkflowTimeTriggerActionForm(ActionConfigMixin, forms.ModelForm):
    """Form for creating/editing a WorkflowTimeTriggerAction.

    The timing row (delay_value / delay_unit / delay_direction / trigger_date_field)
    is rendered as four inline fields. Action-specific config is collected via the
    same hidden-field pattern as WorkflowActionForm and assembled in clean().
    """

    class Meta:
        """Meta options for WorkflowTimeTriggerActionForm"""

        model = WorkflowTimeTriggerAction
        fields = [
            "rule",
            "delay_value",
            "delay_unit",
            "delay_direction",
            "trigger_date_field",
            "action_type",
            "order",
        ]
        widgets = {
            "rule": forms.HiddenInput(),
            "order": forms.HiddenInput(),
            "action_type": forms.HiddenInput(),
            "delay_value": forms.NumberInput(
                attrs={
                    "class": _INPUT_CLASS,
                    "id": "tt-delay-value",
                    "min": "1",
                }
            ),
            "delay_unit": forms.Select(
                attrs={
                    "class": (
                        "js-example-basic-single headselect text-color-600 px-2 py-1 "
                        "border border-dark-50 rounded-md focus-visible:outline-0 "
                        "text-xs [transition:.3s] focus:border-primary-600"
                    ),
                    "id": "tt-delay-unit",
                    "style": "width: auto;",
                }
            ),
            "delay_direction": forms.Select(
                attrs={
                    "class": (
                        "js-example-basic-single headselect text-color-600 px-2 py-1 "
                        "border border-dark-50 rounded-md focus-visible:outline-0 "
                        "text-xs [transition:.3s] focus:border-primary-600"
                    ),
                    "id": "tt-delay-direction",
                    "style": "width: auto;",
                }
            ),
            "trigger_date_field": forms.Select(
                attrs={
                    "class": "w-full text-sm border border-dark-50 rounded-md p-2 focus-visible:outline-0 focus:border-primary-600 text-color-600",
                    "id": "tt-trigger-date-field",
                }
            ),
        }

    def __init__(self, *args, date_field_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._inject_action_config_fields()
        choices = [("rule_trigger_date", _("Rule Trigger Date"))]
        if date_field_choices:
            choices += date_field_choices
        self.fields["trigger_date_field"].widget.choices = choices
        self._seed_action_config_initials()
