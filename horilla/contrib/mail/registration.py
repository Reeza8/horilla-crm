"""
Feature registration for Horilla Mail app.
"""

# First party imports (Horilla)
from horilla.registry.feature import register_feature, register_model_for_feature

register_feature("mail_template", "mail_template_models")

register_model_for_feature(
    app_label="mail",
    model_name="HorillaMail",
    features=["export_data"],
)
