"""History tab datetime display and date-field detection."""

# Standard library imports
import logging
from datetime import date, datetime

# Third-party imports
from dateutil import parser as dateutil_parser

# First party imports (Horilla)
from horilla.registry.history_registry import get_history_datetime_formatters
from horilla.utils.translation import gettext

# Local imports
from ._registry import register
from ._shared import _get_request_user_company, format_datetime_value
from .history_display import is_date_field

logger = logging.getLogger(__name__)


def _parse_datetime_string(value):
    """Parse a stored diff display string into a date/datetime, or None."""
    if not isinstance(value, str) or value in ("", "--", "None", "none"):
        return None
    try:
        return dateutil_parser.parse(value)
    except (ValueError, TypeError, OverflowError):
        return None


_DATE_LIKE_FIELD_TYPES = ("DateTimeField", "DateField", "TimeField")
_DATE_LABEL_HINTS = (
    "تاریخ",
    "start date",
    "end date",
    "due date",
    "updated at",
    "created at",
    "به‌روزرسانی شده در",
    "ایجاد شده در",
)


@register.filter
def history_is_date_field(entry, field_label):
    """True for date/datetime fields, including translated History labels."""
    try:
        if is_date_field(entry, field_label):
            return True
    except Exception:
        pass
    label = str(field_label or "").strip().lower()
    if not label:
        return False
    if any(hint in label for hint in _DATE_LABEL_HINTS):
        return True
    try:
        model = entry.content_type.model_class()
    except Exception:
        return False
    if model is None:
        return False

    for field in model._meta.get_fields():
        if type(field).__name__ not in _DATE_LIKE_FIELD_TYPES:
            continue
        verbose = str(getattr(field, "verbose_name", "") or "").strip().lower()
        name = getattr(field, "name", "").replace("_", " ").strip().lower()
        translated = (
            gettext(str(getattr(field, "verbose_name", "") or "")).strip().lower()
        )
        if label in {verbose, name, translated}:
            return True
    return False


@register.filter
def history_datetime(value):
    """
    Format a History tab timestamp or date/datetime diff value.

    Formatters registered with
    ``horilla.registry.history_registry.register_history_datetime_formatter``
    are tried first (e.g. an app showing another calendar system); otherwise the
    user/company datetime format is used.
    """
    _, user, company = _get_request_user_company()
    for formatter in get_history_datetime_formatters():
        try:
            result = formatter(value, user=user, company=company)
        except Exception:
            logger.exception("History datetime formatter %r failed", formatter)
            continue
        if result:
            return result

    parsed = value
    if not isinstance(value, (date, datetime)):
        parsed = _parse_datetime_string(value)

    formatted = format_datetime_value(
        parsed if parsed is not None else value,
        user=user,
        company=company,
        convert_timezone=True,
    )
    return formatted if formatted is not None else value
