"""
``_inherit_form`` — show calendar_system on regional settings and user forms.
"""

from horilla.extension.forms import FormExtension


class RegionalFormattingFormJalaliExtension(FormExtension):
    """Add calendar system after date format on My Settings → Regional Formatting."""

    _inherit_form = "horilla.contrib.core.forms.base.RegionalFormattingForm"

    fieldsets_insert = [
        ("date_format", "calendar_system"),
    ]
    field_order_insert = [
        ("date_format", "calendar_system"),
    ]

    class Meta:
        """Append calendar_system to the regional formatting form fields."""

        fields_append = ("calendar_system",)


class UserFormSingleJalaliExtension(FormExtension):
    """Add calendar system on the single-step user form."""

    _inherit_form = "horilla.contrib.core.forms.users.UserFormSingle"

    field_order_insert = [
        ("date_format", "calendar_system"),
    ]


class UserFormClassJalaliExtension(FormExtension):
    """Add calendar system on the multi-step user wizard (localization step)."""

    _inherit_form = "horilla.contrib.core.forms.users.UserFormClass"

    step_fields_insert = {
        4: [("date_format", "calendar_system")],
    }
