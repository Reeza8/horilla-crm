"""
Settings menu entries for the form layouts app.
"""

from horilla.contrib.core.menu import FieldsAndFormsSettings

# First party imports (Horilla)
from horilla.urls import reverse_lazy
from horilla.utils.translation import gettext_lazy as _

# ── Admin: Settings → Fields & Forms → Create Form Layout ────────────────────
FieldsAndFormsSettings.items.append(
    {
        "label": _("Create Form Layout"),
        "url": reverse_lazy("form_layouts:form_layout_view"),
        "hx-target": "#settings-content",
        "hx-push-url": "true",
        "hx-select": "#form-layout-view",
        "hx-select-oob": "#settings-sidebar",
        "perm": "form_layouts.view_formlayoutfield",
        "order": 3,
    }
)
