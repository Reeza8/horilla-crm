"""
Settings menu entries for the field requirements app.
"""

from horilla.menu import settings_menu

# First party imports (Horilla)
from horilla.urls import reverse_lazy
from horilla.utils.translation import gettext_lazy as _


@settings_menu.register
class FieldRequirementSettings:
    """Settings menu entries for configurable field requiredness."""

    title = _("Field Requirements")
    icon = "/assets/icons/data.svg"
    order = 6
    items = [
        {
            "label": _("Field Requirements"),
            "url": reverse_lazy("field_requirements:field_requirement_view"),
            "hx-target": "#settings-content",
            "hx-push-url": "true",
            "hx-select": "#field-requirement-view",
            "hx-select-oob": "#settings-sidebar",
            "perm": "field_requirements.view_fieldrequirement",
            "order": 1,
        },
    ]
