"""Version and metadata for the Jalali calendar extension."""

from horilla.utils.translation import gettext_lazy as _

__version__ = "1.0.0"
__module_name__ = _("Jalali Calendar")
__release_date__ = ""
__description__ = _(
    "Optional Shamsi (Jalali) calendar extension. Persian users get Jalali "
    "display, date/time pickers, and FullCalendar month/year views. "
    "Stored values stay Gregorian. Enable via local_settings.py."
)
__icon__ = "assets/icons/calendar-red.svg"

__1_0_0__ = _(
    "Phase 1: DateTimeFormatter, calendar_system on HorillaUser, inline-edit "
    "parse hooks, Jalali date/time pickers, and FullCalendar Shamsi month/year "
    "views. No core template or settings patches."
)
