"""
Days and times on the phone pages, in the user's time zone and calendar.

Formatting goes through the platform's date formatter, so a calendar
extension (Jalali) shows the same dates here as on the desktop.
"""

# Standard library imports
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

# First party imports (Horilla)
from horilla.extension.formatting import get_datetime_formatter
from horilla.utils import timezone
from horilla.utils.translation import gettext_lazy as _

# Day headings: weekday, day and month name, in the user's calendar.
LONG_DATE_FORMAT = "%A %-d %B"
# Day number in the user's calendar (Agenda week strip).
DAY_NUMBER_FORMAT = "%-d"
# The top bar's date: day and month, then the weekday.
DAY_MONTH_FORMAT = "%-d %B"
WEEKDAY_FORMAT = "%A"


def user_now(user):
    """Now in the user's time zone (their profile's, else the server's)."""
    zone = getattr(user, "time_zone", None)
    if zone:
        try:
            return timezone.now().astimezone(ZoneInfo(zone))
        except Exception:  # pylint: disable=broad-except
            pass
    return timezone.localtime()


def day_start(day, tzinfo):
    """Midnight starting ``day`` in ``tzinfo``."""
    return datetime.combine(day, time.min, tzinfo=tzinfo)


def short_time_format(user):
    """The user's (else the company's) time format, without seconds."""
    company = getattr(user, "company", None)
    fmt = (
        getattr(user, "time_format", None)
        or getattr(company, "time_format", None)
        or "%H:%M"
    )
    return fmt.replace(":%S", "")


def format_time(user, value, tzinfo, fmt=None):
    """
    Time of ``value`` in ``tzinfo``, without seconds. Formatted as a datetime,
    so a calendar extension formats it like other dates (Jalali: 24-hour,
    Persian digits).
    """
    local = value.astimezone(tzinfo)
    return get_datetime_formatter().format_datetime(
        local, fmt or short_time_format(user), user=user
    )


def long_date(user, day):
    """Weekday, day and month name, e.g. "Thursday 22 October"."""
    return get_datetime_formatter().format_date(day, LONG_DATE_FORMAT, user=user)


def day_number(user, day):
    """The day of the month in the user's calendar, e.g. "22"."""
    return get_datetime_formatter().format_date(day, DAY_NUMBER_FORMAT, user=user)


def today_parts(user):
    """
    Today in the user's time zone and calendar, for the top bar:
    ``{"iso", "date", "weekday"}``, e.g. "22 October" and "Thursday".
    """
    today = user_now(user).date()
    formatter = get_datetime_formatter()
    return {
        "iso": today.isoformat(),
        "date": formatter.format_date(today, DAY_MONTH_FORMAT, user=user),
        "weekday": formatter.format_date(today, WEEKDAY_FORMAT, user=user),
    }


def day_label(user, day, today):
    """ "Tomorrow", or the weekday, day and month."""
    if day == today + timedelta(days=1):
        return str(_("Tomorrow"))
    return long_date(user, day)


def parse_day(user, value):
    """
    The day in a ``?date=`` value: ISO (``2026-10-25``) or the user's own
    calendar, read by the date formatter. Today when it is missing or not a
    date.
    """
    day = None
    if value:
        try:
            day = get_datetime_formatter().parse_date(value, user=user)
        except (TypeError, ValueError):
            day = None
    if isinstance(day, datetime):
        day = day.date()
    return day or user_now(user).date()
