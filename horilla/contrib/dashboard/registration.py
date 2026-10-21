"""
Feature registration for Horilla Dashboard app.
"""

# First party imports (Horilla)
from horilla.registry.feature import (
    register_feature,
    register_model_for_feature,
    register_models_for_feature,
)

register_feature("dashboard_component", "dashboard_component_models")

register_model_for_feature(
    app_label="dashboard",
    model_name="DashboardFolder",
    features=["global_search"],
)

# Personal preferences/logs: ignored in the delete dependency dialog.
register_models_for_feature(
    models=[
        ("dashboard", "DefaultHomeLayoutOrder"),
    ],
    features=["delete_dependency"],
)
