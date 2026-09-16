"""
Feature registration for the custom_fields app.

Mirrors horilla.contrib.duplicates: custom_fields declares a feature here,
and any app opts its model in with a plain
``register_model_for_feature(..., features=["custom_fields_models"])``
call from its own ``registration.py`` (see ``horilla_crm/leads/registration.py``).
No form/view classes are registered by name — ``inject.py`` patches the
generic base form/detail classes once and checks this registry at runtime.
"""

# First party imports (Horilla)
from horilla.registry.feature import register_feature

register_feature(
    "custom_fields",
    "custom_fields_models",
    auto_register_all=False,
)
