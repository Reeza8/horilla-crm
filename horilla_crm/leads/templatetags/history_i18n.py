"""History tab datetime display (Shamsi when the UI language is Persian)."""

from datetime import date, datetime

from django import template
from django.utils.translation import get_language

from horilla.contrib.generics.templatetags.horilla_tags._shared import (
    _get_request_user_company,
    format_datetime_value,
)
from horilla.extension.formatting import get_datetime_formatter

register = template.Library()


def _format_shamsi(value, *, user=None, company=None, convert_timezone=True):
    """Timezone-adjust then format with the Jalali calendar."""
    formatter = get_datetime_formatter()
    try:
        from horilla_jalali.calendar import format_gregorian_as_jalali
    except Exception:
        format_gregorian_as_jalali = None

    if isinstance(value, datetime):
        if convert_timezone:
            value = formatter._apply_timezone(
                value, user=user, company=company, convert_timezone=True
            )
        fmt = formatter._resolve_datetime_format(user=user, company=company)
        try:
            from horilla_jalali.calendar import to_24h_strftime

            fmt = to_24h_strftime(fmt)
        except Exception:
            fmt = (
                (
                    fmt.replace("%-I", "%-H")
                    .replace("%I", "%H")
                    .replace(" %p", "")
                    .replace(" %P", "")
                    .replace("%p", "")
                    .replace("%P", "")
                    .replace("%S", "")
                    .replace("%f", "")
                )
                .strip()
                .rstrip(":")
            )
    elif isinstance(value, date):
        fmt = formatter._resolve_date_format(user=user, company=company)
    else:
        return None

    if format_gregorian_as_jalali is not None:
        try:
            return format_gregorian_as_jalali(value, fmt)
        except Exception:
            pass

    import jdatetime

    if isinstance(value, datetime):
        jalali_value = jdatetime.datetime.fromgregorian(
            datetime=value, locale=jdatetime.FA_LOCALE
        )
    else:
        jalali_value = jdatetime.date.fromgregorian(
            date=value, locale=jdatetime.FA_LOCALE
        )
    formatted = jalali_value.strftime(fmt.replace("%b", "%B"))
    try:
        from horilla_jalali.calendar import to_persian_datetime_digits

        return to_persian_datetime_digits(formatted)
    except Exception:
        return formatted


def _parse_datetime_string(value):
    if not isinstance(value, str) or value in ("", "--", "None", "none"):
        return None
    try:
        from horilla_jalali.calendar import parse_localized_gregorian_display

        localized = parse_localized_gregorian_display(value)
        if localized is not None:
            return localized
    except Exception:
        pass
    try:
        from dateutil import parser as dateutil_parser
    except Exception:
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
        from horilla.contrib.generics.templatetags.horilla_tags.history_display import (
            is_date_field,
        )

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
    from django.utils.translation import gettext

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
    Format a history timestamp. Persian UI always uses Shamsi (Jalali);
    other languages keep the user/company datetime format.
    """
    _, user, company = _get_request_user_company()
    lang = (get_language() or "").replace("_", "-").split("-")[0].lower()
    try:
        from horilla_jalali.calendar import uses_jalali_calendar

        use_shamsi = uses_jalali_calendar(user=user)
    except Exception:
        use_shamsi = lang == "fa"

    parsed = value
    parsed_from_string = False
    if not isinstance(value, (date, datetime)):
        parsed = _parse_datetime_string(value)
        parsed_from_string = parsed is not None

    if use_shamsi and isinstance(parsed, (date, datetime)):
        result = _format_shamsi(
            parsed,
            user=user,
            company=company,
            convert_timezone=not parsed_from_string,
        )
        if result:
            return result

    formatted = format_datetime_value(
        parsed if parsed is not None else value,
        user=user,
        company=company,
        convert_timezone=True,
    )
    return formatted if formatted is not None else value
