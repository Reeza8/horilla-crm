"""Forms for the Horilla Calls Integration app."""

# Third-party imports (Django)
from django import forms

# First party imports (Horilla)
from horilla.contrib.generics.forms import HorillaModelForm
from horilla.urls import reverse_lazy
from horilla.utils.translation import gettext_lazy as _

# Local imports
from .models import (
    CallIntegrationSetting,
    CallProvider,
    AgentMapping,
    CallLog,
)

# Keys injected by HorillaSingleFormView.get_form_kwargs() that plain forms.Form doesn't accept
_SINGLE_FORM_VIEW_KWARGS = (
    "full_width_fields",
    "dynamic_create_fields",
    "hidden_fields",
    "condition_fields",
    "condition_model",
    "condition_field_choices",
    "condition_hx_include",
    "condition_related_name",
    "condition_related_name_candidates",
    "field_permissions",
    "duplicate_mode",
    "instance",
    "request",
)


def _pop_single_form_view_kwargs(form_instance, kwargs):
    """Remove all extra kwargs injected by HorillaSingleFormView.get_form_kwargs()."""
    for key in _SINGLE_FORM_VIEW_KWARGS:
        val = kwargs.pop(key, None)
        if val is not None:
            setattr(form_instance, key, val)


class CallIntegrationSettingForm(HorillaModelForm):
    """Form to enable/configure the calls integration for a company."""

    class Meta:
        model = CallIntegrationSetting
        fields = ["is_enabled", "access_type", "allowed_roles", "allowed_users"]

    condition_fields = {
        "allowed_roles": {
            "field": "access_type",
            "value": "roles",
        },
        "allowed_users": {
            "field": "access_type",
            "value": "users",
        },
    }


class CallProviderForm(HorillaModelForm):
    """Form for creating and editing call providers."""

    class Meta:
        model = CallProvider
        fields = [
            "name",
            "provider_type",
            "status",
            "account_sid",
            "api_key",
            "api_secret",
            "api_base_url",
            "caller_id",
            "webhook_secret",
            "notes",
        ]


class AgentMappingForm(HorillaModelForm):
    """Form for mapping CRM users to telephony agent credentials."""

    class Meta:
        model = AgentMapping
        fields = ["provider", "user", "extension", "agent_id", "is_available"]


class CallAccessRolesForm(forms.Form):
    """Modal form: select which roles can access call integration (Select2)."""

    allowed_roles = forms.ModelMultipleChoiceField(
        queryset=None,
        required=False,
        label=_("Roles"),
        widget=forms.SelectMultiple(
            attrs={
                "class": "select2-pagination w-full",
                "data-url": reverse_lazy(
                    "generics:model_select2",
                    kwargs={"app_label": "core", "model_name": "role"},
                ),
                "data-placeholder": _("Select roles"),
                "multiple": "multiple",
                "data-field-name": "allowed_roles",
                "id": "id_allowed_roles",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        _pop_single_form_view_kwargs(self, kwargs)
        super().__init__(*args, **kwargs)


class CallAccessUsersForm(forms.Form):
    """Modal form: select which users can access call integration (Select2)."""

    allowed_users = forms.ModelMultipleChoiceField(
        queryset=None,
        required=False,
        label=_("Users"),
        widget=forms.SelectMultiple(
            attrs={
                "class": "select2-pagination w-full",
                "data-url": reverse_lazy(
                    "generics:model_select2",
                    kwargs={"app_label": "core", "model_name": "HorillaUser"},
                ),
                "data-placeholder": _("Select users"),
                "multiple": "multiple",
                "data-field-name": "allowed_users",
                "id": "id_allowed_users",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        _pop_single_form_view_kwargs(self, kwargs)
        super().__init__(*args, **kwargs)


class CallLogForm(HorillaModelForm):
    """Form for manually creating or editing a call log entry."""

    class Meta:
        model = CallLog
        fields = [
            "provider",
            "direction",
            "status",
            "from_number",
            "to_number",
            "duration_seconds",
            "started_at",
            "ended_at",
            "recording_url",
            "notes",
            "related_model_name",
            "related_object_id",
        ]
