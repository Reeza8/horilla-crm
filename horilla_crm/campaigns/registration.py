"""
Feature registration for Campaigns app.
"""

# Third-party imports (Django)
from django.db.models import Case, ExpressionWrapper, F, FloatField, Value, When

# First party imports (Horilla)
from horilla.contrib.reports.utils import register_virtual_field
from horilla.registry.feature import register_model_for_feature
from horilla.utils.translation import gettext_lazy as _

register_model_for_feature(
    app_label="campaigns",
    model_name="Campaign",
    all=True,
    features=["workflow_models"],
)

register_virtual_field(
    app_label="campaigns",
    model_name="Campaign",
    field_name="roi_percentage",
    verbose_name=_("ROI %"),
    annotation=Case(
        When(
            actual_cost__gt=0,
            then=ExpressionWrapper(
                (F("value_won_opportunities") - F("actual_cost"))
                * 100.0
                / F("actual_cost"),
                output_field=FloatField(),
            ),
        ),
        default=Value(0.0),
        output_field=FloatField(),
    ),
)
