"""
This module defines the BusinessHour for managing business hours in the Horilla platform.
"""

# Standard library imports
import logging

# Third-party imports
from datetime import time

# Django imports
from django.conf import settings
from django.utils.formats import time_format

# Third-party imports (Django)
from multiselectfield import MultiSelectField

# First party imports (Horilla)
from horilla.db import models
from horilla.urls import reverse_lazy
from horilla.utils.choices import (
    DAY_CHOICES,
    DAY_LABELS,
    SHORT_TO_DAY_PREFIX,
    TIMEZONE_CHOICES,
    TIMING_CHOICES,
    WEEK_ORDER,
)
from horilla.utils.html import format_html, format_html_join
from horilla.utils.translation import gettext_lazy as _

# Local imports
from .base import HorillaCoreModel

logger = logging.getLogger(__name__)


def _format_card_time_range(start_label: str, end_label: str) -> str:
    """
    Join formatted times with a spaced en dash.
    Uses NBSP so HTML does not collapse the gaps (normal spaces render as one).
    """
    nbsp = "\u00a0"
    sep = f"{nbsp}{nbsp}{nbsp}\u2013{nbsp}{nbsp}{nbsp}"
    return f"{start_label}{sep}{end_label}"


class BusinessHourDayMixin(models.Model):
    """
    Model to add start and end time fields for each day of the week.
    """

    monday_start = models.TimeField(
        null=True, blank=True, verbose_name=_("Monday Start Time")
    )
    monday_end = models.TimeField(
        null=True, blank=True, verbose_name=_("Monday End Time")
    )

    tuesday_start = models.TimeField(
        null=True, blank=True, verbose_name=_("Tuesday Start Time")
    )
    tuesday_end = models.TimeField(
        null=True, blank=True, verbose_name=_("Tuesday End Time")
    )

    wednesday_start = models.TimeField(
        null=True, blank=True, verbose_name=_("Wednesday Start Time")
    )
    wednesday_end = models.TimeField(
        null=True, blank=True, verbose_name=_("Wednesday End Time")
    )

    thursday_start = models.TimeField(
        null=True, blank=True, verbose_name=_("Thursday Start Time")
    )
    thursday_end = models.TimeField(
        null=True, blank=True, verbose_name=_("Thursday End Time")
    )

    friday_start = models.TimeField(
        null=True, blank=True, verbose_name=_("Friday Start Time")
    )
    friday_end = models.TimeField(
        null=True, blank=True, verbose_name=_("Friday End Time")
    )

    saturday_start = models.TimeField(
        null=True, blank=True, verbose_name=_("Saturday Start Time")
    )
    saturday_end = models.TimeField(
        null=True, blank=True, verbose_name=_("Saturday End Time")
    )

    sunday_start = models.TimeField(
        null=True, blank=True, verbose_name=_("Sunday Start Time")
    )
    sunday_end = models.TimeField(
        null=True, blank=True, verbose_name=_("Sunday End Time")
    )

    class Meta:
        """
        Abstract model for business hour day model.
        """

        abstract = True


class BusinessHour(BusinessHourDayMixin, HorillaCoreModel):
    """
    Model to handle business hours with support for:
    - 24/7 operations
    - Weekdays only (Mon-Fri)
    - Custom hours with different times per day
    """

    BUSINESS_HOUR_TYPES = [
        ("24_7", _("24 Hours x 7 days")),
        ("24_5", _("24 Hours x 5 days")),
        ("custom", _("Custom Hours")),
    ]

    TIMING_CHOICES = TIMING_CHOICES
    DAY_LABELS = DAY_LABELS
    WEEK_ORDER = WEEK_ORDER
    SHORT_TO_DAY_PREFIX = SHORT_TO_DAY_PREFIX

    # Basic Information
    name = models.CharField(max_length=255, verbose_name=_("Name"))
    time_zone = models.CharField(
        max_length=100,
        choices=TIMEZONE_CHOICES,
        default="UTC",
        verbose_name=_("Time Zone"),
    )

    # Business Hour Type
    business_hour_type = models.CharField(
        max_length=10,
        choices=BUSINESS_HOUR_TYPES,
        default="24_7",
        help_text=_("Type of business hours"),
        verbose_name=_("Business Hour Type"),
    )

    # Week Configuration
    week_start_day = models.CharField(
        max_length=10,
        choices=DAY_CHOICES,
        default="monday",
        help_text=_("Week Start Day"),
        verbose_name=_("Week Start Day"),
    )
    week_days = MultiSelectField(
        choices=DAY_CHOICES, blank=True, verbose_name=_("Week days")
    )

    # Timing Configuration (for custom hours)
    timing_type = models.CharField(
        max_length=10,
        choices=TIMING_CHOICES,
        default="same",
        blank=True,
        null=True,
        help_text=_("Same hours every day or different hours per day"),
        verbose_name=_("Timing Type"),
    )

    # For "Same Hour Every Day"
    default_start_time = models.TimeField(
        null=True,
        blank=True,
        help_text=_("Default start time"),
        verbose_name=_("Default Start Time"),
    )
    default_end_time = models.TimeField(
        null=True,
        blank=True,
        help_text=_("Default end time"),
        verbose_name=_("Default End Time"),
    )

    # Status
    is_default = models.BooleanField(
        default=False,
        help_text=_("Default Business Hour"),
        verbose_name=_("Is Default"),
    )

    holidays = models.ManyToManyField(
        "Holiday",
        blank=True,
        related_name="business_hours",
        verbose_name=_("Holidays"),
        help_text=_("Company holidays associated with this business hour schedule."),
    )

    class Meta:
        """
        Meta options for the BusinessHour model.
        """

        verbose_name = _("Business Hour")
        verbose_name_plural = _("Business Hours")
        ordering = ["name"]

    #: At most one row per company in the UI (enforced in :class:`BusinessHourForm`).
    BUSINESS_HOUR_PER_COMPANY_LIMIT = 1

    def __str__(self):
        return f"{self.name} ({self.get_business_hour_type_display()})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def get_edit_url(self):
        """
        Get the URL for editing the business hour
        """
        return reverse_lazy("core:business_hour_update_form", kwargs={"pk": self.pk})

    def get_card_active_day_codes(self):
        """Weekday short codes (mon..sun) when the business is open."""
        if self.business_hour_type == "24_7":
            return list(self.WEEK_ORDER)
        if self.business_hour_type == "24_5":
            sel = self.normalized_week_day_codes()
            return sel if sel else list(self.WEEK_ORDER[:5])
        if self.business_hour_type == "custom":
            return self.normalized_week_day_codes()
        return []

    def get_card_business_days_label(self):
        """Comma-separated open days for the summary card."""
        active = set(self.get_card_active_day_codes())
        labels = [str(self.DAY_LABELS[d]) for d in self.WEEK_ORDER if d in active]
        return ", ".join(labels) if labels else "—"

    def get_card_business_days_compact(self):
        """
        Compact label for open days: \"Monday – Sunday\", \"Monday – Friday\",
        or a comma list when days are not one contiguous block.
        """
        active_ordered = [
            d for d in self.WEEK_ORDER if d in set(self.get_card_active_day_codes())
        ]
        if not active_ordered:
            return "—"
        if len(active_ordered) == 7:
            return _format_card_time_range(
                str(self.DAY_LABELS[active_ordered[0]]),
                str(self.DAY_LABELS[active_ordered[-1]]),
            )
        idxs = [self.WEEK_ORDER.index(d) for d in active_ordered]
        consecutive = all(idxs[i + 1] - idxs[i] == 1 for i in range(len(idxs) - 1))
        if consecutive and len(active_ordered) > 1:
            return _format_card_time_range(
                str(self.DAY_LABELS[active_ordered[0]]),
                str(self.DAY_LABELS[active_ordered[-1]]),
            )
        return ", ".join(str(self.DAY_LABELS[d]) for d in active_ordered)

    def get_card_different_hours_week_rows(self):
        """
        For custom + different timing: one row per weekday (Mon→Sun) with hours
        or \"Closed\" (Zoho-style business days block).
        """
        if (
            self.business_hour_type != "custom"
            or (self.timing_type or "") != "different"
        ):
            return None

        def fmt(t):
            if not t:
                return "—"
            return time_format(t, "P")

        selected = set(self.normalized_week_day_codes())
        rows = []
        for day_code in self.WEEK_ORDER:
            label = str(self.DAY_LABELS[day_code])
            if day_code not in selected:
                rows.append({"day": label, "hours": str(_("Closed"))})
                continue
            prefix = self.SHORT_TO_DAY_PREFIX[day_code]
            start_val = getattr(self, f"{prefix}_start", None)
            end_val = getattr(self, f"{prefix}_end", None)
            if self._is_midnight(start_val) and self._is_midnight(end_val):
                rows.append({"day": label, "hours": str(_("Closed"))})
            else:
                rows.append(
                    {
                        "day": label,
                        "hours": _format_card_time_range(fmt(start_val), fmt(end_val)),
                    }
                )
        return rows

    def get_card_closed_days_label(self):
        """Comma-separated closed days (or none)."""
        if self.business_hour_type == "24_7":
            return str(_("None"))
        active = set(self.get_card_active_day_codes())
        closed = [str(self.DAY_LABELS[d]) for d in self.WEEK_ORDER if d not in active]
        if not closed:
            return str(_("None"))
        return ", ".join(closed)

    def get_card_hours_lines(self):
        """
        Lines for the “Business hours” block on the summary card (one string per row).
        """

        def fmt(t):
            if not t:
                return "—"
            return time_format(t, "P")

        if self.business_hour_type in ("24_7", "24_5"):
            return [str(_("24 hours"))]
        if self.business_hour_type == "custom" and (self.timing_type or "") == "same":
            if not self.default_start_time or not self.default_end_time:
                return ["—"]
            return [
                _format_card_time_range(
                    fmt(self.default_start_time),
                    fmt(self.default_end_time),
                )
            ]
        if (
            self.business_hour_type == "custom"
            and (self.timing_type or "") == "different"
        ):
            # Per-day lines are rendered via get_card_different_hours_week_rows().
            return []
        return ["—"]

    def normalized_week_day_codes(self):
        """
        Return weekday short codes (mon, tue, ...) stored on week_days / multiselect.
        """
        raw = self.week_days
        if isinstance(raw, (list, tuple)):
            selected = list(raw)
        elif isinstance(raw, str) and raw.strip():
            selected = [p.strip() for p in raw.replace(",", " ").split() if p.strip()]
        else:
            selected = []
        return selected

    def get_card_holidays_label(self):
        """Comma-separated holiday names for the summary card (by start date)."""
        all_h = list(self.holidays.order_by("start_date", "name"))
        if not all_h:
            return ""
        if len(all_h) > 50:
            return ", ".join(str(h.name) for h in all_h[:50]) + " (+{})".format(
                len(all_h) - 50
            )
        return ", ".join(str(h.name) for h in all_h)

    @staticmethod
    def _is_midnight(t):
        return t is None or t == time(0, 0)


class ShiftHour(BusinessHourDayMixin, HorillaCoreModel):
    """
    Stand-alone named shift ,main working hours, optional breaks, optional users.
    """

    SHIFT_HOUR_LIMIT = 50

    TIMING_CHOICES = TIMING_CHOICES
    DAY_LABELS = DAY_LABELS
    WEEK_ORDER = WEEK_ORDER
    SHORT_TO_DAY_PREFIX = SHORT_TO_DAY_PREFIX
    BREAK_MODE_CHOICES = [
        ("none", _("No break hours")),
        ("same", _("Same hours every day")),
        ("different", _("Different hours every day")),
    ]

    name = models.CharField(max_length=255, verbose_name=_("Name"))
    time_zone = models.CharField(
        max_length=100,
        choices=TIMEZONE_CHOICES,
        default="UTC",
        verbose_name=_("Time zone"),
    )
    timing_type = models.CharField(
        max_length=10,
        choices=TIMING_CHOICES,
        default="same",
        help_text=_("Same hours every day or different hours per day"),
        verbose_name=_("Shift hours"),
    )
    week_days = MultiSelectField(
        choices=DAY_CHOICES, blank=True, verbose_name=_("Week days")
    )
    default_start_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name=_("Default start time"),
    )
    default_end_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name=_("Default end time"),
    )

    break1_mode = models.CharField(
        max_length=12,
        choices=BREAK_MODE_CHOICES,
        default="none",
        verbose_name=_("Break hours 1"),
    )
    break1_week_days = MultiSelectField(choices=DAY_CHOICES, blank=True)
    break1_default_start = models.TimeField(
        null=True,
        blank=True,
        verbose_name=_("Break 1 default start"),
    )
    break1_default_end = models.TimeField(
        null=True,
        blank=True,
        verbose_name=_("Break 1 default end"),
    )
    break1_per_day = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Per-day break times when mode is "different" (mon..sun keys).'),
        verbose_name=_("Break 1 per-day times"),
    )

    break2_mode = models.CharField(
        max_length=12,
        choices=BREAK_MODE_CHOICES,
        default="none",
        verbose_name=_("Break hours 2"),
    )
    break2_week_days = MultiSelectField(choices=DAY_CHOICES, blank=True)
    break2_default_start = models.TimeField(
        null=True,
        blank=True,
        verbose_name=_("Break 2 default start"),
    )
    break2_default_end = models.TimeField(
        null=True,
        blank=True,
        verbose_name=_("Break 2 default end"),
    )
    break2_per_day = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Per-day break times when mode is "different" (mon..sun keys).'),
        verbose_name=_("Break 2 per-day times"),
    )

    assigned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="shift_hours",
        verbose_name=_("Assigned users"),
    )

    class Meta:
        """
        Meta options for the ShiftHour model.
        """

        verbose_name = _("Shift hour")
        verbose_name_plural = _("Shift hours")
        ordering = ["name"]

    def __str__(self):
        return str(self.name)

    @staticmethod
    def _is_midnight(t):
        return t is None or t == time(0, 0)

    def normalized_week_day_codes(self):
        """Weekday codes selected for this shift."""
        raw = self.week_days
        if isinstance(raw, (list, tuple)):
            selected = list(raw)
        elif isinstance(raw, str) and raw.strip():
            selected = [p.strip() for p in raw.replace(",", " ").split() if p.strip()]
        else:
            selected = []
        return selected

    def get_shift_bounds_for_day(self, short_code):
        """Return (start, end) for the main shift on a weekday code, or None if closed."""
        if short_code not in WEEK_ORDER:
            return None
        selected = set(self.normalized_week_day_codes())
        if short_code not in selected:
            return None
        if self.timing_type == "same":
            if not self.default_start_time or not self.default_end_time:
                return None
            return (self.default_start_time, self.default_end_time)
        if self.timing_type == "different":
            prefix = self.SHORT_TO_DAY_PREFIX[short_code]
            start_val = getattr(self, f"{prefix}_start", None)
            end_val = getattr(self, f"{prefix}_end", None)
            if self._is_midnight(start_val) and self._is_midnight(end_val):
                return None
            return (start_val, end_val)
        return None

    def get_avatar(self):
        """Method will return the API to the avatar or path to the profile image. For now, using ui-avatars.com with random background."""
        url = f"https://ui-avatars.com/api/?name={self.name}&background=random"
        return url

    def get_edit_url(self):
        """Get the URL for editing the shift hour."""
        return reverse_lazy("core:shift_hour_update_form", kwargs={"pk": self.pk})

    def get_delete_url(self):
        """Get the URL for deleting the shift hour."""
        return reverse_lazy("core:shift_hour_delete_view", kwargs={"pk": self.pk})

    def get_detail_url(self):
        """Get the URL for shift hour detail view."""
        return reverse_lazy("core:shift_hour_detail_view", kwargs={"pk": self.pk})

    def get_active_display(self):
        """Return "Yes" if the shift hour is active (has any assigned days), otherwise "No". This can be used in list displays."""
        return _("Yes") if self.is_active else _("No")

    def get_assigned_users_count_display(self):
        """Return the count of assigned users, or "—" if none. For list display."""
        n = self.assigned_users.count()
        return str(n) if n else "—"

    def get_formatted_week_days(self):
        """HTML summary of shift timing (custom-style only)."""

        def format_time_value(value):
            if not value:
                return "--:--"
            return time_format(value, "P")

        selected = self.normalized_week_day_codes()

        if self.timing_type == "same":
            start = format_time_value(self.default_start_time)
            end = format_time_value(self.default_end_time)
            labels = [DAY_LABELS[d] for d in WEEK_ORDER if d in selected]
            if labels == [DAY_LABELS[d] for d in WEEK_ORDER[:5]]:
                return format_html(
                    "Monday - Friday<br><strong>({} – {})</strong>",
                    start,
                    end,
                )
            if labels == [DAY_LABELS[d] for d in WEEK_ORDER]:
                return format_html(
                    "Monday - Sunday<br><strong>({} – {})</strong>",
                    start,
                    end,
                )
            if labels:
                return format_html(
                    "{}<br><strong>({} – {})</strong>",
                    ", ".join(str(lab) for lab in labels),
                    start,
                    end,
                )
            return format_html("{} – {}", start, end)

        if self.timing_type == "different":

            def is_midnight(t):
                return t is None or t == time(0, 0)

            rows = []
            for day_code in WEEK_ORDER:
                day_label = DAY_LABELS[day_code]
                is_open = day_code in selected
                prefix = day_label.lower()
                if is_open:
                    start_val = getattr(self, f"{prefix}_start", None)
                    end_val = getattr(self, f"{prefix}_end", None)
                    if is_midnight(start_val) and is_midnight(end_val):
                        time_range = str(_("Closed"))
                    else:
                        time_range = "{} – {}".format(
                            format_time_value(start_val),
                            format_time_value(end_val),
                        )
                else:
                    time_range = str(_("Closed"))
                rows.append((day_label, time_range))

            return format_html(
                "<table class='text-left align-top space-y-1'>{}</table>",
                format_html_join(
                    "",
                    "<tr class='text-sm'>"
                    "<td class='pr-4 text-gray-600 whitespace-nowrap w-24 mb-5'>{}</td>"
                    "<td class='font-semibold text-black whitespace-nowrap'>{}</td>"
                    "</tr>",
                    rows,
                ),
            )

        return format_html("—")

    def get_assigned_users_label(self):
        """Plain-text summary of assigned users for detail views."""
        qs = list(self.assigned_users.all()[:20])
        if not qs:
            return "—"
        names = [u.get_full_name() or u.username for u in qs]
        total = self.assigned_users.count()
        text = ", ".join(names)
        if total > len(names):
            text = f"{text} (+{total - len(names)})"
        return text

    def get_break_slot_brief(self, slot):
        """Short text for break 1 or 2 (slot is 'break1' or 'break2')."""
        mode = getattr(self, f"{slot}_mode", "none")
        if mode == "none":
            return str(_("None"))
        if mode == "same":
            ds = getattr(self, f"{slot}_default_start")
            de = getattr(self, f"{slot}_default_end")
            if ds and de:
                return f"{time_format(ds, 'P')} – {time_format(de, 'P')}"
            return str(_("Same (incomplete)"))
        return str(_("Different per day"))

    def get_break1_brief(self):
        """Short text for break 1 to show in detail view."""
        return self.get_break_slot_brief("break1")

    def get_break2_brief(self):
        """Short text for break 2 to show in detail view."""
        return self.get_break_slot_brief("break2")
