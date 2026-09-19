"""
Models for the horilla_booking app
"""

# Standard library imports
import uuid

# Third-party imports (Django)
from django.conf import settings

from horilla.contrib.core.models import HorillaCoreModel
from horilla.contrib.utils.methods import render_template

# First party imports (Horilla)
from horilla.db import models
from horilla.urls import reverse
from horilla.utils.translation import gettext_lazy as _
from horilla.utils.urls import build_absolute_url as build_public_booking_url

MEETING_PROVIDER_CHOICES = [
    ("zoom", _("Zoom")),
    ("google_meet", _("Google Meet")),
    ("ms_teams", _("Microsoft Teams")),
]

BOOKING_STATUS_CHOICES = [
    ("pending", _("Pending")),
    ("confirmed", _("Confirmed")),
    ("cancelled", _("Cancelled")),
    ("completed", _("Completed")),
    ("no_show", _("No Show")),
]


class BookingPage(HorillaCoreModel):
    """
    Represents a public-facing booking calendar page.
    Visitors can book a meeting via the page's public URL.
    A company BusinessHour must exist before a page can be created.
    """

    business_hour = models.ForeignKey(
        "core.BusinessHour",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="booking_pages",
        verbose_name=_("Business Hour"),
        help_text=_("Company business hours that govern available booking slots."),
    )
    shift_hour = models.ForeignKey(
        "core.ShiftHour",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="booking_pages",
        verbose_name=_("Shift Hours"),
        help_text=_(
            "Use shift hours schedule for slot availability instead of business hours."
        ),
    )
    slug = models.SlugField(
        max_length=100,
        unique=True,
        verbose_name=_("Slug"),
        help_text=_("Unique URL identifier for the booking page."),
    )
    title = models.CharField(max_length=200, verbose_name=_("Title"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    duration = models.PositiveIntegerField(
        default=30,
        verbose_name=_("Duration (minutes)"),
    )
    is_online = models.BooleanField(
        default=True,
        verbose_name=_("Online Meeting"),
    )
    meeting_provider = models.CharField(
        max_length=20,
        choices=MEETING_PROVIDER_CHOICES,
        blank=True,
        verbose_name=_("Meeting Provider"),
        help_text=_("Required when Online Meeting is enabled."),
    )
    location = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Location"),
        help_text=_("Physical address for in-person meetings."),
    )
    buffer_before = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Buffer Before (minutes)"),
    )
    buffer_after = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Buffer After (minutes)"),
    )
    max_per_day = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Max Bookings Per Day"),
        help_text=_("Leave blank for unlimited."),
    )
    advance_notice = models.PositiveIntegerField(
        default=60,
        verbose_name=_("Advance Notice (minutes)"),
        help_text=_("Minimum notice required before a booking can be made."),
    )
    booking_window = models.PositiveIntegerField(
        default=30,
        verbose_name=_("Booking Window (days)"),
        help_text=_("How many days into the future visitors can book."),
    )
    questions = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Custom Questions"),
        help_text=_("List of questions to ask the booker."),
    )
    reminder_hours = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Reminder (hours before)"),
        help_text=_(
            "Send reminder email X hours before the meeting. Leave blank to disable."
        ),
    )
    allow_reschedule = models.BooleanField(
        default=True,
        verbose_name=_("Allow Rescheduling"),
    )
    reschedule_cutoff_days = models.PositiveIntegerField(
        default=1,
        verbose_name=_("Reschedule Cutoff (days)"),
        help_text=_("Prevent rescheduling if less than X days before the meeting."),
    )
    allow_cancel = models.BooleanField(
        default=True,
        verbose_name=_("Allow Cancellation"),
    )
    cancel_cutoff_days = models.PositiveIntegerField(
        default=1,
        verbose_name=_("Cancel Cutoff (days)"),
        help_text=_("Prevent cancellation if less than X days before the meeting."),
    )
    primary_color = models.CharField(
        max_length=7,
        default="#e54f38",
        verbose_name=_("Brand Color"),
        help_text=_("Hex color used on the public booking page (e.g. #e54f38)."),
    )
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="booking_pages",
        verbose_name=_("Host"),
    )
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="participant_booking_pages",
        verbose_name=_("Participants"),
        help_text=_(
            "Users who will be added as participants to every meeting booked via this page."
        ),
    )

    confirmation_mail_template = models.ForeignKey(
        "mail.HorillaMailTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="booking_confirmation_pages",
        verbose_name=_("Confirmation Email Template"),
        help_text=_("Optional. Overrides the default confirmation email design."),
    )
    cancellation_mail_template = models.ForeignKey(
        "mail.HorillaMailTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="booking_cancellation_pages",
        verbose_name=_("Cancellation Email Template"),
        help_text=_("Optional. Overrides the default cancellation email design."),
    )
    reschedule_mail_template = models.ForeignKey(
        "mail.HorillaMailTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="booking_reschedule_pages",
        verbose_name=_("Reschedule Email Template"),
        help_text=_("Optional. Overrides the default reschedule email design."),
    )

    OWNER_FIELDS = ["host"]

    class Meta:
        """Meta options for BookingPage."""

        verbose_name = _("Booking Page")
        verbose_name_plural = _("Booking Pages")
        ordering = ["-created_at"]

    def __str__(self):
        return str(self.title)

    def get_public_url(self, request=None):
        """Return the absolute public booking URL."""

        path = reverse("booking:public_booking", kwargs={"slug": self.slug})
        return build_public_booking_url(path, request=request)

    def get_edit_url(self):
        """Return the URL for editing this booking page."""

        return reverse("booking:booking_page_edit", kwargs={"pk": self.pk})

    def get_delete_url(self):
        """Return the URL for deleting this booking page."""

        return reverse("booking:booking_page_delete", kwargs={"pk": self.pk})

    def get_availability_url(self):
        """Return the URL for managing availability of this booking page."""

        return reverse("booking:booking_availability", kwargs={"pk": self.pk})

    def get_embed_url(self):
        """Return the embed URL for this booking page."""

        return reverse("booking:booking_embed", kwargs={"pk": self.pk})

    def get_detail_url(self):
        """Return the detail URL for this booking page."""

        return reverse("booking:booking_page_detail", kwargs={"pk": self.pk})


class Booking(HorillaCoreModel):
    """
    Represents an individual booking made via a BookingPage.
    Linked to a Lead or Contact and a Meeting Activity upon creation.
    """

    booking_page = models.ForeignKey(
        BookingPage,
        on_delete=models.CASCADE,
        related_name="bookings",
        verbose_name=_("Booking Page"),
    )
    booker_name = models.CharField(max_length=200, verbose_name=_("Booker Name"))
    booker_email = models.EmailField(verbose_name=_("Booker Email"))
    start_datetime = models.DateTimeField(verbose_name=_("Start Date & Time"))
    end_datetime = models.DateTimeField(verbose_name=_("End Date & Time"))
    status = models.CharField(
        max_length=20,
        choices=BOOKING_STATUS_CHOICES,
        default="pending",
        verbose_name=_("Status"),
    )
    answers = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Question Answers"),
    )
    meeting_url = models.URLField(
        blank=True,
        verbose_name=_("Meeting URL"),
    )
    cancellation_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name=_("Cancellation Token"),
    )
    cancellation_reason = models.TextField(
        blank=True,
        verbose_name=_("Cancellation Reason"),
    )
    booker_timezone = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name=_("Booker Timezone"),
    )
    activity = models.OneToOneField(
        "activity.Activity",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="booking",
        verbose_name=_("Meeting Activity"),
    )

    class Meta:
        """Meta options for Booking."""

        verbose_name = _("Booking")
        verbose_name_plural = _("Bookings")
        ordering = ["-start_datetime"]
        indexes = [
            models.Index(fields=["booking_page", "start_datetime"]),
            models.Index(fields=["booker_email"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.booker_name} — {self.start_datetime:%Y-%m-%d %H:%M}"

    def get_status_url(self):
        """Return the URL for checking the status of this booking."""

        return reverse("booking:booking_status", kwargs={"pk": self.pk})

    def get_detail_url(self):
        """Return the URL for viewing this booking's detail modal."""

        return reverse("booking:booking_detail_modal", kwargs={"pk": self.pk})

    def meeting_link_col(self):
        """Return a clickable Join link when this booking has a meeting URL."""
        if self.meeting_url:
            return render_template(
                path="booking_meeting_link_col.html",
                context={"meeting_url": self.meeting_url},
            )
        return "—"
