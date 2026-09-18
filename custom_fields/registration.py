"""
Feature registration for the custom_fields app.

Mirrors horilla.contrib.duplicates: custom_fields declares a feature here,
and any app opts its model in with a plain
``register_model_for_feature(..., features=["custom_fields_models"])``
call from its own ``registration.py`` (see ``horilla_crm/leads/registration.py``).
No form/view classes are registered by name — ``custom_fields/extensions.py``
and ``custom_fields/detail_extensions.py`` discover opted-in models from
this registry at runtime and register real ``FormExtension``/
``DetailExtension``/``DetailSectionExtension`` classes for them.
"""

# First party imports (Horilla)
from horilla.registry.feature import register_feature

register_feature(
    "custom_fields",
    "custom_fields_models",
    auto_register_all=False,
)
