"""
Feature registration for Horilla Automations app.
"""

# First party imports (Horilla)
from horilla.registry.feature import register_feature, register_models_for_feature

register_feature("automation", "automation_models")

# Personal preferences/logs: ignored in the delete dependency dialog.
register_models_for_feature(
    models=[
        ("automations", "AutomationRunLog"),
    ],
    features=["delete_dependency"],
)
