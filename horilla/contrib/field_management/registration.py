"""
Feature registration for the field settings app.

The feature names and registry keys are shared with other apps (for example
``horilla_crm/leads/registration.py`` lists ``"field_requirements"``,
``"form_layouts"`` and ``"custom_fields_models"``), so they are unchanged by
the merge: any app opts a model in with a plain
``register_model_for_feature(..., features=[...])`` call.

Custom field extensions (``extensions/custom_fields_forms.py`` and
``extensions/custom_fields_detail.py``) discover opted-in models from the
``custom_fields_models`` registry at runtime and register real
``FormExtension``/``DetailExtension``/``DetailSectionExtension`` classes.
"""

# First party imports (Horilla)
from horilla.registry.feature import register_feature

register_feature(
    "field_requirements",
    "field_requirement_models",
    auto_register_all=False,
)

register_feature(
    "form_layouts",
    "form_layout_models",
    auto_register_all=False,
)

register_feature(
    "custom_fields",
    "custom_fields_models",
    auto_register_all=False,
)
