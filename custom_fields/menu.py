"""
Settings menu entry for the Custom Fields app.
"""

from horilla.contrib.core.menu import FieldsAndFormsSettings

# First party imports (Horilla)
from horilla.urls import reverse_lazy
from horilla.utils.translation import gettext_lazy as _

# ── Admin: Settings → Fields & Forms → Custom Fields ─────────────────────────
FieldsAndFormsSettings.items.append(
    {
        "label": _("Custom Fields"),
        "url": reverse_lazy("custom_fields:view"),
        "hx-target": "#settings-content",
        "hx-push-url": "true",
        "hx-select": "#custom-fields-view",
        "hx-select-oob": "#settings-sidebar",
        "perm": "custom_fields.view_customfielddefinition",
        "order": 1,
    }
)
