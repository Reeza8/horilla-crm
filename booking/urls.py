"""
URLs for the horilla_booking app.
"""

from horilla.urls import path

from . import views

app_name = "booking"

urlpatterns = [
    # Settings views
    path(
        "booking-settings/",
        views.BookingSettingsView.as_view(),
        name="booking_settings",
    ),
    path(
        "goto-working-hours/",
        views.GoToWorkingHoursView.as_view(),
        name="goto_working_hours",
    ),
    path(
        "booking-page-nav/", views.BookingPageNavView.as_view(), name="booking_page_nav"
    ),
    path(
        "booking-page-list/",
        views.BookingPageListView.as_view(),
        name="booking_page_list",
    ),
    path(
        "booking-page-create/",
        views.BookingPageCreateView.as_view(),
        name="booking_page_create",
    ),
    path(
        "booking-page-edit/<int:pk>/",
        views.BookingPageCreateView.as_view(),
        name="booking_page_edit",
    ),
    path(
        "booking-page-delete/<int:pk>/",
        views.BookingPageDeleteView.as_view(),
        name="booking_page_delete",
    ),
    path(
        "booking-toggle-location/",
        views.BookingToggleLocationView.as_view(),
        name="toggle_location_field",
    ),
    path(
        "booking-toggle-reschedule-cutoff/",
        views.BookingToggleRescheduleCutoffView.as_view(),
        name="toggle_reschedule_cutoff",
    ),
    path(
        "booking-toggle-cancel-cutoff/",
        views.BookingToggleCancelCutoffView.as_view(),
        name="toggle_cancel_cutoff",
    ),
    path(
        "booking-availability/<int:pk>/",
        views.BookingAvailabilityView.as_view(),
        name="booking_availability",
    ),
    path(
        "booking-embed/<int:pk>/",
        views.BookingEmbedView.as_view(),
        name="booking_embed",
    ),
    path(
        "booking-page-detail/<int:pk>/",
        views.BookingPageDetailView.as_view(),
        name="booking_page_detail",
    ),
    path(
        "booking-list-nav/<int:pk>/",
        views.BookingListNavView.as_view(),
        name="booking_list_nav",
    ),
    path(
        "booking-list/<int:pk>/", views.BookingListView.as_view(), name="booking_list"
    ),
    path("my-bookings/", views.MyBookingsView.as_view(), name="my_bookings"),
    path("my-bookings/nav/", views.MyBookingsNavView.as_view(), name="my_bookings_nav"),
    path(
        "my-bookings/list/", views.MyBookingsListView.as_view(), name="my_bookings_list"
    ),
    path(
        "booking-status/<int:pk>/",
        views.BookingStatusUpdateView.as_view(),
        name="booking_status",
    ),
    path(
        "booking-detail-modal/<int:pk>/",
        views.BookingDetailModalView.as_view(),
        name="booking_detail_modal",
    ),
    # Public booking pages (no login required)
    path("book/<slug:slug>/", views.PublicBookingView.as_view(), name="public_booking"),
    path(
        "book/<slug:slug>/slots/",
        views.AvailableSlotView.as_view(),
        name="available_slots",
    ),
    path(
        "book/confirmed/<uuid:token>/",
        views.PublicBookingConfirmedView.as_view(),
        name="booking_confirmed",
    ),
    path(
        "book/cancel/<uuid:token>/",
        views.PublicBookingCancelView.as_view(),
        name="booking_cancel",
    ),
    path(
        "book/reschedule/<uuid:token>/",
        views.PublicBookingRescheduleView.as_view(),
        name="booking_reschedule",
    ),
]
