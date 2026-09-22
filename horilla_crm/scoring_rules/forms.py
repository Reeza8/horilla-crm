"""Forms for the scoring_rules app."""

# Third-party imports (Django)
from django import forms

from horilla.contrib.generics.forms import HorillaModelForm

# First party imports (Horilla)
from horilla.core.exceptions import ValidationError
from horilla.utils.translation import gettext_lazy as _
from horilla_crm.scoring_rules.models import (
    ScoringCondition,
    ScoringCriterion,
    ScoringRule,
)


class ScoringRuleForm(HorillaModelForm):
    """Form for creating and editing scoring rules."""

    class Meta:
        """Meta options for ScoringRuleForm."""

        model = ScoringRule
        fields = "__all__"


class ScoringCriterionForm(HorillaModelForm):
    """Form for creating and editing scoring criteria."""

    def __init__(self, *args, **kwargs):
        """Initialize scoring criterion form with condition model."""
        kwargs["condition_model"] = ScoringCondition
        super().__init__(*args, **kwargs)

    def clean(self):
        """Process multiple condition rows from form data."""
        cleaned_data = super().clean()
        condition_rows = self._extract_condition_rows()
        if not condition_rows:
            raise ValidationError(_("At least one condition must be provided."))
        cleaned_data["condition_rows"] = condition_rows
        return cleaned_data

    class Meta:
        """Meta options for ScoringCriterionForm."""

        model = ScoringCriterion
        fields = "__all__"
        exclude = ["name", "order"]
        widgets = {
            "points": forms.NumberInput(
                attrs={
                    "class": "text-color-600 p-2 w-full border border-dark-50 rounded-md mt-1"
                }
            ),
        }
