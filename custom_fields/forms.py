from django import forms

from horilla.contrib.core.models import HorillaContentType
from horilla.contrib.generics.forms import HorillaModelForm
from horilla.utils.translation import gettext_lazy as _

from .models import CustomFieldDefinition

SUPPORTED_MODELS = ["leads.lead", "opportunities.opportunity"]


class CustomFieldDefinitionForm(HorillaModelForm):
    """Form for creating / editing a custom field definition."""

    class Meta:
        model = CustomFieldDefinition
        fields = [
            "content_type",
            "name",
            "field_type",
            "is_required",
            "choices",
            "order",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        supported_cts = HorillaContentType.objects.filter(
            app_label__in=["leads", "opportunities"],
            model__in=["lead", "opportunity"],
        )
        self.fields["content_type"].queryset = supported_cts
        self.fields["content_type"].label = _("Model")

        self.fields["choices"].widget = forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": _("Option 1, Option 2, Option 3"),
                "class": "text-color-600 p-2 placeholder:text-xs w-full border border-dark-50 rounded-md mt-1 focus-visible:outline-0 placeholder:text-dark-100 text-sm transition duration-300 focus:border-primary-600",
            }
        )
        self.fields["choices"].required = False

    def clean(self):
        cleaned_data = super().clean()
        field_type = cleaned_data.get("field_type")
        choices = cleaned_data.get("choices", "")
        if field_type == "choice" and not choices.strip():
            self.add_error(
                "choices", _("Choices are required for Multiple Choice fields.")
            )
        ct = cleaned_data.get("content_type")
        if ct and f"{ct.app_label}.{ct.model}" not in SUPPORTED_MODELS:
            self.add_error(
                "content_type",
                _("Custom fields are only supported for Leads and Opportunities."),
            )
        return cleaned_data
