"""
Settings menu entry for the field settings app.
"""

from horilla.menu import settings_menu

# First party imports (Horilla)
from horilla.urls import reverse_lazy
from horilla.utils.translation import gettext_lazy as _


@settings_menu.register
class FieldSettings:
    """Single Settings dropdown grouping the field configuration pages."""

    title = _("Field Settings")
    icon = "/assets/icons/field-requirement.svg"
    order = 6
    items = [
        {
            "label": _("Custom Fields"),
            "url": reverse_lazy("field_settings:custom_fields_view"),
            "hx-target": "#settings-content",
            "hx-push-url": "true",
            "hx-select": "#custom-fields-view",
            "hx-select-oob": "#settings-sidebar",
            "perm": "field_settings.view_customfielddefinition",
            "order": 1,
        },
        {
            "label": _("Field Requirements"),
            "url": reverse_lazy("field_settings:field_requirement_view"),
            "hx-target": "#settings-content",
            "hx-push-url": "true",
            "hx-select": "#field-requirement-view",
            "hx-select-oob": "#settings-sidebar",
            "perm": "field_settings.view_fieldrequirement",
            "order": 2,
        },
        {
            "label": _("Form Layout"),
            "url": reverse_lazy("field_settings:form_layout_view"),
            "hx-target": "#settings-content",
            "hx-push-url": "true",
            "hx-select": "#form-layout-view",
            "hx-select-oob": "#settings-sidebar",
            "perm": "field_settings.view_formlayoutfield",
            "order": 3,
        },
    ]
