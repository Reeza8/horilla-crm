"""
Feature registration for custom calendars.
"""

# First party imports (Horilla)
from horilla.registry.feature import register_feature, register_models_for_feature

register_feature("custom_calendar", "custom_calendar_models", auto_register_all=False)

# Personal preferences/logs: ignored in the delete dependency dialog.
register_models_for_feature(
    models=[
        ("calendar", "UserCalendarPreference"),
    ],
    features=["delete_dependency"],
)
