"""
``_inherit_model`` — add calendar_system on HorillaUser without core migrations.
"""

from horilla.contrib.core.models import HorillaCoreModel
from horilla.db import models
from horilla.utils.translation import gettext_lazy as _
from horilla_jalali.calendar import CALENDAR_SYSTEM_CHOICES


class HorillaUserJalaliExtension(HorillaCoreModel):
    """Inject Shamsi/Gregorian preference onto the user model."""

    _inherit_model = "core.HorillaUser"

    calendar_system = models.CharField(
        max_length=20,
        choices=CALENDAR_SYSTEM_CHOICES,
        default="jalali",
        help_text=_(
            "Choose Shamsi (Jalali) or Gregorian dates when your language is Persian."
        ),
        verbose_name=_("Calendar System"),
    )
