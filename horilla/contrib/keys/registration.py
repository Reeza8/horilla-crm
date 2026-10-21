"""
Feature registration for Horilla Keyboard Shortcuts app.
"""

# First party imports (Horilla)
from horilla.registry.feature import register_models_for_feature

# Personal preferences: ignored in the delete dependency dialog.
register_models_for_feature(
    models=[
        ("keys", "ShortcutKey"),
    ],
    features=["delete_dependency"],
)
