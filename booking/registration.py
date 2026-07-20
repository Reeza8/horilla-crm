"""
Feature registration for the horilla_booking app.
"""

# First party imports (Horilla)
from horilla.registry.feature import register_model_for_feature

register_model_for_feature(
    app_label="booking",
    model_name="Booking",
    features=["export_data"],
)
