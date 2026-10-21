"""
This module is responsible for registering the notification template feature in the Horilla framework. It imports the necessary function to register the feature and then registers the "notification_template" feature with its corresponding models."
"""

# First party imports (Horilla)
from horilla.registry.feature import register_feature, register_models_for_feature

register_feature("notification_template", "notification_template_models")

# Personal preferences/logs: ignored in the delete dependency dialog.
register_models_for_feature(
    models=[
        ("notifications", "Notification"),
        ("notifications", "NotificationSoundPreference"),
    ],
    features=["delete_dependency"],
)
