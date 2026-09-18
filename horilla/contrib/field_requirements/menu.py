"""
Settings menu entries for the field requirements app.
"""

from horilla.contrib.core.menu import FieldsAndFormsSettings

# First party imports (Horilla)
from horilla.urls import reverse_lazy
from horilla.utils.translation import gettext_lazy as _

# ── Admin: Settings → Fields & Forms → Field Requirements ────────────────────
FieldsAndFormsSettings.items.append(
    {
        "label": _("Field Requirements"),
        "url": reverse_lazy("field_requirements:field_requirement_view"),
        "hx-target": "#settings-content",
        "hx-push-url": "true",
        "hx-select": "#field-requirement-view",
        "hx-select-oob": "#settings-sidebar",
        "perm": "field_requirements.view_fieldrequirement",
        "order": 2,
    }
)
