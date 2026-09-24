"""
``_inherit_view`` — Jalali parse hooks for the bulk "Edit Details" save.

Native ``date`` / ``datetime-local`` / ``time`` widgets are wrapped in JS
(``horilla_jalali.js``) so datetime modals get a Shamsi date picker plus a
time picker. This view extension only parses submitted values.
"""

from horilla.contrib.generics.views.helpers.edit_field import FieldInfoResolver
from horilla.extension.formatting import get_datetime_formatter
from horilla.extension.view import ViewExtension


class JalaliFieldInfoResolverExtension(ViewExtension):
    """Parse Jalali or ISO bulk-edit submissions through the composed formatter."""

    _inherit_view = (
        "horilla.contrib.generics.views.helpers.edit_field.FieldInfoResolver"
    )

    def parse_date_field_value(self, value, user=None):
        """Parse a bulk-edit date value via the Jalali-aware formatter."""
        parsed = get_datetime_formatter().parse_date(value, user=user)
        if parsed is not None:
            return parsed
        return FieldInfoResolver.parse_date_field_value(self, value, user=user)

    def parse_datetime_field_value(self, value, user=None):
        """Parse a bulk-edit datetime value via the Jalali-aware formatter."""
        parsed = get_datetime_formatter().parse_datetime(value, user=user)
        if parsed is not None:
            return parsed
        return FieldInfoResolver.parse_datetime_field_value(self, value, user=user)
