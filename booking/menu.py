"""
This module registers Floating, Settings, My Settings, and Main Section menus
for the horilla_booking app.
"""

from horilla.contrib.core.menu import GeneralSettings
from horilla.menu import MAIN_CONTENT_HX_ATTRS, sub_section_menu
from horilla.urls import reverse_lazy
from horilla.utils.translation import gettext_lazy as _


@sub_section_menu.register
class MyBookingsSubSection:
    """My Jobs > My Bookings — visible to booking hosts and participants."""

    section = "my_jobs"
    app_label = "booking"
    position = 10

    verbose_name = _("My Bookings")
    icon = "/assets/icons/calendar.svg"

    url = reverse_lazy("booking:my_bookings")
    attrs = MAIN_CONTENT_HX_ATTRS

    perm = ["booking.view_booking", "booking.view_own_booking"]


GeneralSettings.items.append(
    {
        "label": _("Booking Pages"),
        "url": reverse_lazy("booking:booking_settings"),
        "hx-target": "#settings-content",
        "hx-push-url": "true",
        "hx-select": "#booking-settings-view",
        "hx-select-oob": "#settings-sidebar",
        "perm": "booking.view_bookingpage",
    }
)
