"""Aggregate view modules for the `booking.views` package."""

from booking.views.booking_page import (
    GoToWorkingHoursView,
    BookingSettingsView,
    BookingPageNavView,
    BookingPageListView,
    BookingPageCreateView,
    BookingToggleLocationView,
    BookingPageDeleteView,
    BookingToggleRescheduleCutoffView,
    BookingToggleCancelCutoffView,
    BookingAvailabilityView,
    BookingEmbedView,
)
from booking.views.booking_list import (
    BookingPageDetailView,
    BookingListNavView,
    BookingListView,
    MyBookingsView,
    MyBookingsNavView,
    MyBookingsListView,
    BookingStatusUpdateView,
    BookingDetailModalView,
)
from booking.views.public import (
    AvailableSlotView,
    PublicBookingView,
    PublicBookingConfirmedView,
    PublicBookingCancelView,
    PublicBookingRescheduleView,
)

__all__ = [
    # Booking page settings
    "GoToWorkingHoursView",
    "BookingSettingsView",
    "BookingPageNavView",
    "BookingPageListView",
    "BookingPageCreateView",
    "BookingToggleLocationView",
    "BookingPageDeleteView",
    "BookingToggleRescheduleCutoffView",
    "BookingToggleCancelCutoffView",
    "BookingAvailabilityView",
    "BookingEmbedView",
    # Booking list + management
    "BookingPageDetailView",
    "BookingListNavView",
    "BookingListView",
    "MyBookingsView",
    "MyBookingsNavView",
    "MyBookingsListView",
    "BookingStatusUpdateView",
    "BookingDetailModalView",
    # Public views
    "AvailableSlotView",
    "PublicBookingView",
    "PublicBookingConfirmedView",
    "PublicBookingCancelView",
    "PublicBookingRescheduleView",
]
