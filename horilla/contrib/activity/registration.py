"""
Feature registration for Horilla Activity app, Such as import, export,
global search, and other pluggable capabilities.
"""

# First party imports (Horilla)
from horilla.registry.feature import register_feature, register_model_for_feature

register_feature("activity_related", "activity_related_models")

register_model_for_feature(
    app_label="activity",
    model_name="Activity",
    features=["global_search", "automation", "mail_template", "export_data"],
)
