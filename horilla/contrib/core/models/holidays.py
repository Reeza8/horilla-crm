"""
This module defines the Holiday models for holidays in the Horilla platform.
"""

# Standard library imports
import logging

# Django imports
from django.conf import settings

# Third-party imports (Django)
from multiselectfield import MultiSelectField

from horilla.contrib.utils.methods import render_template
from horilla.core.exceptions import ValidationError

# First party imports (Horilla)
from horilla.db import models
from horilla.urls import reverse_lazy
from horilla.utils.choices import DAY_CHOICES, MONTH_CHOICES
from horilla.utils.translation import gettext_lazy as _

# Local imports
from .base import HorillaCoreModel

logger = logging.getLogger(__name__)


class Holiday(HorillaCoreModel):
    """
    Holiday model for managing company holidays
    """

    FREQUENCY_CHOICES = [
        ("weekly", _("Weekly")),
        ("monthly", _("Monthly")),
        ("yearly", _("Yearly")),
    ]

    MONTHLY_REPEAT_CHOICES = [
        ("day_of_month", _("On Day")),
        ("weekday_of_month", _("On the")),
    ]

    YEARLY_REPEAT_CHOICES = [
        ("day_of_month", _("On every")),  # e.g., July 14th
        ("weekday_of_month", _("On the")),  # e.g., 2nd Monday of July
    ]

    name = models.CharField(max_length=255, verbose_name=_("Holiday Name"))
    start_date = models.DateTimeField(verbose_name=_("Start Date"))
    end_date = models.DateTimeField(verbose_name=_("End Date"))

    all_users = models.BooleanField(default=False, verbose_name=_("All Users"))
    specific_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="holidays",
        verbose_name=_("Specific Users"),
    )

    is_recurring = models.BooleanField(default=False, verbose_name=_("Recurring"))
    frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        blank=True,
        null=True,
        verbose_name=_("Holiday Frequency"),
    )

    recurs_every_weeks = models.PositiveIntegerField(
        default=1, blank=True, null=True, verbose_name=_("Recurs Every (weeks)")
    )
    weekly_days = MultiSelectField(
        choices=DAY_CHOICES, blank=True, verbose_name=_("Weekly Days")
    )

    monthly_repeat_type = models.CharField(
        max_length=20,
        choices=MONTHLY_REPEAT_CHOICES,
        blank=True,
        null=True,
        verbose_name=_("Monthly Repeat Type"),
    )
    monthly_day_of_month = models.PositiveIntegerField(
        null=True, blank=True, verbose_name=_("Day of Month")
    )
    monthly_interval = models.PositiveIntegerField(
        default=1, blank=True, null=True, verbose_name=_("Monthly Interval")
    )
    monthly_day_of_week = models.CharField(
        max_length=10,
        choices=DAY_CHOICES,
        blank=True,
        null=True,
        verbose_name=_("Day of Week"),
    )
    monthly_week_of_month = models.PositiveIntegerField(
        null=True, blank=True, verbose_name=_("Week of Month")
    )

    yearly_repeat_type = models.CharField(
        max_length=20,
        choices=YEARLY_REPEAT_CHOICES,
        blank=True,
        null=True,
        verbose_name=_("Yearly Repeat Type"),
    )
    yearly_week_of_month = models.PositiveIntegerField(
        null=True, blank=True, verbose_name=_("Week of Month")
    )
    yearly_day_of_month = models.PositiveIntegerField(
        null=True, blank=True, verbose_name=_("Day of Month")
    )
    yearly_day_of_week = models.CharField(
        max_length=10,
        choices=DAY_CHOICES,
        blank=True,
        null=True,
        verbose_name=_("Day of Week"),
    )
    yearly_month = models.CharField(
        max_length=15,
        choices=MONTH_CHOICES,
        blank=True,
        null=True,
        verbose_name=_("Month"),
    )

    OWNER_FIELDS = ["specific_users"]

    class Meta:
        """
        Meta options for the Holiday model.
        """

        verbose_name = _("Holiday")
        verbose_name_plural = _("Holidays")
        ordering = ["-start_date"]

    def __str__(self):
        return str(self.name)

    def clean(self):
        """
        Validate holiday data
        """

        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValidationError(_("Start date cannot be after end date"))

        if self.is_recurring and not self.frequency:
            raise ValidationError(_("Frequency is required for recurring holidays"))

        if self.frequency == "weekly":
            if not self.weekly_days:
                raise ValidationError(
                    _("Weekly days must be specified for weekly recurrence")
                )
            if self.recurs_every_weeks < 1:
                raise ValidationError(_("Recurs every weeks must be at least 1"))

        if self.frequency == "monthly":
            if self.monthly_repeat_type == "day_of_month":
                if not self.monthly_day_of_month:
                    raise ValidationError(
                        _("Day of month is required for monthly recurrence")
                    )
            elif self.monthly_repeat_type == "weekday_of_month":
                if not (self.monthly_day_of_week and self.monthly_week_of_month):
                    raise ValidationError(
                        _(
                            "Both day of week and week of month are required for monthly recurrence"
                        )
                    )
            else:
                raise ValidationError(_("Please select a valid monthly repeat type"))

        if self.frequency == "yearly":
            if not self.yearly_month:
                raise ValidationError(_("Month is required for yearly recurrence"))

            if self.yearly_repeat_type == "day_of_month":
                if not self.yearly_day_of_month:
                    raise ValidationError(
                        _("Day of month is required for yearly recurrence")
                    )
            elif self.yearly_repeat_type == "weekday_of_month":
                if not (self.yearly_day_of_week and self.yearly_week_of_month):
                    raise ValidationError(
                        _(
                            "Both week of month and day of week are required for yearly recurrence"
                        )
                    )
            else:
                raise ValidationError(_("Please select a valid yearly repeat type"))

    def save(self, *args, **kwargs):
        """
        Override save to perform validation
        """
        self.full_clean()
        super().save(*args, **kwargs)

    def get_avatar(self):
        """
        Method will retun the api to the avatar or path to the profile image
        """
        url = f"https://ui-avatars.com/api/?name={self.name}&background=random"
        return url

    def get_edit_url(self):
        """
        Get the URL for editing the holiday
        """
        return reverse_lazy("core:holiday_update_form", kwargs={"pk": self.pk})

    def get_detail_url(self):
        """
        Get the URL for holiday detail view
        """
        return reverse_lazy("core:holiday_detail_view", kwargs={"pk": self.pk})

    def get_bh_readonly_detail_url(self):
        """Read-only detail URL used inside the business hour holiday list."""
        return reverse_lazy(
            "core:business_hour_holiday_readonly_detail", kwargs={"pk": self.pk}
        )

    def get_user_detail_url(self):
        """
        Get the URL for holiday detail view for users
        """
        return reverse_lazy("core:user_holiday_detail", kwargs={"pk": self.pk})

    def detail_view_actions(self):
        """
        method for rendering detail view action
        """

        return render_template(
            path="holidays/detail_view_actions.html",
            context={"instance": self},
        )

    def get_delete_url(self):
        """
        Get the URL for deleting the holiday
        """
        return reverse_lazy("core:holiday_delete_view", kwargs={"pk": self.pk})

    def specific_users_enable(self):
        """
        Return user pills if specific users are enabled,
        otherwise a short note when all users are included or none are set
        """
        if self.all_users:
            return "All users are included"
        specific_users = list(self.specific_users.all())
        if specific_users:
            # Local imports: generics template tags import core models
            from horilla.contrib.generics.templatetags.horilla_tags._shared import (
                _get_request_user_company,
            )
            from horilla.contrib.generics.templatetags.horilla_tags.display_tags import (
                render_user_chip_list,
            )

            _request, viewer, _company = _get_request_user_company()
            return render_user_chip_list(
                specific_users,
                viewer,
                self,
                "detail",
                str(self._meta.get_field("specific_users").verbose_name),
            )
        return "No Users specified"

    def holiday_type(self):
        """
        Return comma-separated employee names if specific users are enabled,
        otherwise return 'All users are enabled'
        """
        if self.all_users:
            return "Company Holiday"
        specific_users_qs = self.specific_users.all()
        if specific_users_qs is not None and specific_users_qs.exists():
            # Ensure each user has a valid string representation
            user_names = [str(user) for user in specific_users_qs if str(user).strip()]
            if user_names:
                return "Personal Holiday"
            return "No valid user names found"
        return "No Users specified"

    def get_ordinal_number(self, number):
        """
        Convert number to ordinal (1st, 2nd, 3rd, etc.)
        """
        ordinals = {
            1: _("1st"),
            2: _("2nd"),
            3: _("3rd"),
            4: _("4th"),
            5: _("5th"),
        }
        return ordinals.get(number, f"{number}th")

    def is_recurring_holiday(self):
        """
        Return a human-readable string describing the recurring holiday pattern.
        """
        if not self.is_recurring or not self.frequency:
            return "Not a recurring holiday"

        # WEEKLY
        if self.frequency == "weekly" and self.weekly_days:
            day_map = dict(DAY_CHOICES)
            days = ", ".join(day_map[day] for day in self.weekly_days)

            return f"Recur every {self.recurs_every_weeks or 1} week on {days}"

        # MONTHLY
        if self.frequency == "monthly" and self.monthly_repeat_type:
            if self.monthly_repeat_type == "day_of_month":
                return (
                    f"Recur on {self.get_ordinal_number(self.monthly_day_of_month)} day "
                    f"of every {self.monthly_interval or 1} month"
                )
            if self.monthly_repeat_type == "weekday_of_month":
                return (
                    f"Recur on the {self.get_ordinal_number(self.monthly_week_of_month)} "
                    f"{self.monthly_day_of_week.capitalize()} of every {self.monthly_interval or 1} month"
                )

        # YEARLY
        if self.frequency == "yearly" and self.yearly_repeat_type:
            if self.yearly_repeat_type == "day_of_month":
                return (
                    f"Recur on every {self.yearly_month.capitalize()} "
                    f"{self.get_ordinal_number(self.yearly_day_of_month)}"
                )
            if self.yearly_repeat_type == "weekday_of_month":
                return (
                    f"Recur on the {self.get_ordinal_number(self.yearly_week_of_month)} "
                    f"{self.yearly_day_of_week.capitalize()} of {self.yearly_month.capitalize()}"
                )

        return "Not a recurring holiday"

    def get_eligible_users(self):
        """
        Get all users eligible for this holiday
        """
        from horilla.auth.models import User

        if self.all_users:
            return User.objects.filter(is_active=True)
        return self.specific_users.all()

    def is_user_eligible(self, user):
        """
        Check if a specific user is eligible for this holiday
        """
        if self.all_users:
            return user.is_active
        return self.specific_users.filter(pk=user.pk).exists()

    def get_recurrence_description(self):
        """
        Get human-readable description of recurrence pattern
        """
        if not self.is_recurring:
            return _("One-time holiday")

        if self.frequency == "weekly":
            days = ", ".join([dict(DAY_CHOICES)[day] for day in self.weekly_days])
            if self.recurs_every_weeks == 1:
                return _("Weekly on {}").format(days)

            return _("Every {} weeks on {}").format(self.recurs_every_weeks, days)

        if self.frequency == "monthly":
            if self.monthly_day_of_month:
                if self.monthly_interval == 1:
                    return _("Monthly on day {}").format(self.monthly_day_of_month)
                return _("Every {} months on day {}").format(
                    self.monthly_interval, self.monthly_day_of_month
                )

            day_name = dict(DAY_CHOICES)[self.monthly_day_of_week]
            ordinal = self.get_ordinal_number(self.monthly_week_of_month)
            if self.monthly_interval == 1:
                return _("Monthly on {} {} of month").format(ordinal, day_name)

            return _("Every {} months on {} {} of month").format(
                self.monthly_interval, ordinal, day_name
            )

        if self.frequency == "yearly":
            month_name = dict(self.MONTH_CHOICES)[self.yearly_month]
            if self.yearly_day_of_month:
                return _("Yearly on {} {}").format(month_name, self.yearly_day_of_month)

            day_name = dict(DAY_CHOICES)[self.yearly_day_of_week]
            ordinal = self.get_ordinal_number(self.yearly_week_of_month)
            return _("Yearly on {} {} of {}").format(ordinal, day_name, month_name)

        return _("Custom recurrence")

    @property
    def duration_days(self):
        """
        Calculate the duration of the holiday in days
        """
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 0
