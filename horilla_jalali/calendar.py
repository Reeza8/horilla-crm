"""
Jalali (Shamsi) calendar helpers.

Gregorian values stay in the database. These utilities convert for display
and parse user-facing Jalali input when the Shamsi calendar is active.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time
from typing import Any

import jdatetime
from django.utils.translation import get_language

from horilla.utils.translation import gettext_lazy as _

CALENDAR_SYSTEM_CHOICES = [
    ("jalali", _("Shamsi (Jalali)")),
    ("gregorian", _("Gregorian")),
]

JALALI_DATE_FORMATS = (
    "%Y/%m/%d",
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
)

JALALI_DATETIME_FORMATS = (
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
)


def normalize_language_code(language: str | None) -> str:
    """Return the primary language subtag (e.g. ``fa`` from ``fa-ir``)."""
    if not language:
        return ""
    return language.replace("_", "-").split("-")[0].lower()


def get_active_language(user: Any = None) -> str:
    """Return the active UI language."""
    return normalize_language_code(get_language())


def uses_jalali_calendar(user: Any = None, language: str | None = None) -> bool:
    """
    Return True when the UI should use the Shamsi calendar.

    Applies to Persian (``fa``) unless the user opted into Gregorian
    via ``calendar_system``.
    """
    lang = language or get_active_language(user)
    if lang != "fa":
        return False
    if user is None:
        return True
    system = getattr(user, "calendar_system", None) or "jalali"
    return system == "jalali"


def _is_plausible_jalali_year(year: int) -> bool:
    return 1200 <= year <= 1600


def _first_directive_index(fmt: str, chars: str) -> int | None:
    for match in re.finditer(r"%-?[A-Za-z]", fmt):
        if match.group(0)[-1] in chars:
            return match.start()
    return None


def jalali_strftime_format(fmt: str) -> str:
    """
    Adapt a Gregorian ``strftime`` pattern for Persian Jalali display.

    Named-month formats such as ``%b %d %Y`` become ``%d %B %Y`` so the
    result is ``23 مرداد 1405`` instead of ``Mor 23 1405``.
    Datetime patterns with time before date are reordered to date-first.
    """
    if not fmt:
        return fmt
    out = fmt.replace("%b", "%B").replace("%a", "%A")
    out = re.sub(r"%B(\s*),?\s*%d", r"%d\1%B", out)
    out = re.sub(r"%d\s*,\s*%B", "%d %B", out)
    out = re.sub(r"%B\s*,\s*%Y", "%B %Y", out)

    date_idx = _first_directive_index(out, "YymdbBAUWwxX")
    time_idx = _first_directive_index(out, "HIMSf")
    if date_idx is not None and time_idx is not None and time_idx < date_idx:
        parts = out.split()
        if len(parts) == 2:
            return f"{parts[1]} {parts[0]}"
    return out


def preserve_rtl_datetime_order(text: str) -> str:
    """
    Keep date-before-time visual order on RTL pages.

    Numeric datetimes such as ``1405-05-12 19:52:00`` are two LTR runs; in
    RTL layout the browser often shows ``19:52:00 1405-05-12``. Wrapping in
    LRI/PDI keeps the formatted order.
    """
    if not text:
        return text
    return f"\u2066{text}\u2069"


def format_gregorian_as_jalali(value: date | datetime | time, fmt: str) -> str:
    """Format a Gregorian value using Jalali calendar parts and Persian names."""
    if isinstance(value, time) and not isinstance(value, datetime):
        return value.strftime(fmt)

    jalali_fmt = jalali_strftime_format(fmt)
    if isinstance(value, datetime):
        jalali_value = jdatetime.datetime.fromgregorian(
            datetime=value, locale=jdatetime.FA_LOCALE
        )
        formatted = jalali_value.strftime(jalali_fmt)
        return preserve_rtl_datetime_order(formatted)
    jalali_value = jdatetime.date.fromgregorian(date=value, locale=jdatetime.FA_LOCALE)
    return jalali_value.strftime(jalali_fmt)


def parse_jalali_date(value: str) -> date | None:
    """Parse a Jalali date string into a Gregorian ``date``."""
    if not value or not str(value).strip():
        return None
    raw = str(value).strip()
    for fmt in JALALI_DATE_FORMATS:
        try:
            jalali_value = jdatetime.datetime.strptime(raw, fmt)
        except ValueError:
            continue
        if _is_plausible_jalali_year(jalali_value.year):
            return jalali_value.togregorian().date()
    return None


def parse_jalali_datetime(value: str) -> datetime | None:
    """Parse a Jalali datetime string into a Gregorian ``datetime``."""
    if not value or not str(value).strip():
        return None
    raw = str(value).strip()
    candidates = (raw, raw.replace("T", " "))
    for candidate in candidates:
        for fmt in JALALI_DATETIME_FORMATS:
            try:
                jalali_value = jdatetime.datetime.strptime(candidate, fmt)
            except ValueError:
                continue
            if _is_plausible_jalali_year(jalali_value.year):
                return jalali_value.togregorian()
    return None
