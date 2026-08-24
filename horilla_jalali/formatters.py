"""
``_inherit_formatter`` for Jalali date/time display and parse.

Does not change stored values (database remains Gregorian).
"""

from horilla.contrib.generics.formatting import DateTimeFormatter
from horilla.extension.formatting import DateTimeFormatterExtension
from horilla_jalali.calendar import (
    format_gregorian_as_jalali,
    parse_jalali_date,
    parse_jalali_datetime,
    uses_jalali_calendar,
)


class JalaliDateTimeFormatterExtension(DateTimeFormatterExtension):
    """Override DateTimeFormatter format/parse when Shamsi calendar is active."""

    _inherit_formatter = (
        "horilla.contrib.generics.formatting.datetime.DateTimeFormatter"
    )

    def format_date(self, value, fmt, *, user=None):
        """Format a date as Jalali when the Shamsi calendar is active."""
        if not uses_jalali_calendar(user=user):
            return DateTimeFormatter.format_date(self, value, fmt, user=user)
        try:
            return format_gregorian_as_jalali(value, fmt)
        except Exception:
            return DateTimeFormatter.format_date(self, value, fmt, user=user)

    def format_datetime(self, value, fmt, *, user=None):
        """Format a datetime as Jalali when the Shamsi calendar is active."""
        if not uses_jalali_calendar(user=user):
            return DateTimeFormatter.format_datetime(self, value, fmt, user=user)
        try:
            return format_gregorian_as_jalali(value, fmt)
        except Exception:
            return DateTimeFormatter.format_datetime(self, value, fmt, user=user)

    def parse_date(self, value, *, user=None):
        """Parse a Jalali date string when the Shamsi calendar is active."""
        if uses_jalali_calendar(user=user):
            parsed = parse_jalali_date(value)
            if parsed is not None:
                return parsed
        return DateTimeFormatter.parse_date(self, value, user=user)

    def parse_datetime(self, value, *, user=None):
        """Parse a Jalali datetime string when the Shamsi calendar is active."""
        if uses_jalali_calendar(user=user):
            parsed = parse_jalali_datetime(value)
            if parsed is not None:
                return parsed
        return DateTimeFormatter.parse_datetime(self, value, user=user)
