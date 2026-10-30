"""
Public-facing booking views — slot availability, booking form, cancel, and reschedule.
No login required.
"""

# Standard library imports
import json
import logging
from datetime import date, datetime, timedelta

# Third-party imports (Django)
from django.conf import settings
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt

from horilla.shortcuts import get_object_or_404, redirect, render
from horilla.urls import reverse_lazy
from horilla.utils import timezone
from horilla.utils.choices import WEEK_ORDER
from horilla.utils.translation import gettext_lazy as _
from horilla.views.generic import View

# First party imports (Horilla)
from horilla.web import HttpResponse, JsonResponse

# Local imports
from ..models import Booking, BookingPage, build_public_booking_url
from ..signals import booking_submitted
from ..utils import get_available_slots

logger = logging.getLogger(__name__)


class AvailableSlotView(View):
    """
    JSON endpoint: returns available time slots for a given date.
    URL: /horilla_booking/book/<slug>/slots/?date=2026-05-20
    """

    def get(self, request, slug):
        """Return available and booked time slots as JSON for the requested date."""
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        from ..utils import _get_page_timezone, get_all_slots_for_tz

        page = get_object_or_404(BookingPage, slug=slug, is_active=True)
        date_str = request.GET.get("date", "")
        tz_name = request.GET.get("timezone", "")
        result = {"slots": [], "booked_slots": [], "unavailable_slots": []}
        if date_str:
            try:
                selected_date = date.fromisoformat(date_str)
                try:
                    booker_tz = (
                        ZoneInfo(tz_name) if tz_name else _get_page_timezone(page)
                    )
                except (ZoneInfoNotFoundError, KeyError):
                    booker_tz = _get_page_timezone(page)
                data = get_all_slots_for_tz(page, selected_date, booker_tz)
                result["slots"] = data["available"]
                result["booked_slots"] = data["booked"]
                result["unavailable_slots"] = data["unavailable"]
            except ValueError:
                pass

        response = JsonResponse(result)
        response["Cache-Control"] = "no-store"
        # Public, read-only data with no credentials: let other sites that build
        # their own booking form read the free slots
        response["Access-Control-Allow-Origin"] = "*"
        return response


def _booking_in_booker_tz(booking, request=None):
    """Set booking.local_start_date / local_start_time in the booker's timezone.

    Template date filters would show the server's timezone instead, which is not
    the time the booker picked (the confirmation page already uses their zone).
    """
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    from django.utils import dateformat

    try:
        tz = (
            ZoneInfo(booking.booker_timezone)
            if booking.booker_timezone
            else timezone.get_current_timezone()
        )
    except (ZoneInfoNotFoundError, KeyError):
        tz = timezone.get_current_timezone()
    local = booking.start_datetime.astimezone(tz)
    booking.local_start_date = dateformat.format(local, "N j, Y")
    booking.local_start_time = dateformat.format(local, "H:i")
    # Absolute link back to the confirmation page (uses SITE_URL when configured)
    booking.confirmed_url = build_public_booking_url(
        reverse_lazy(
            "booking:booking_confirmed", kwargs={"token": booking.cancellation_token}
        ),
        request=request,
    )
    return booking


def _booking_rate_limited(request, page_id):
    """Count a booking attempt per page and client IP; True once over the limit.

    Configurable with settings.BOOKING_RATE_LIMIT = (max_attempts, seconds);
    the default is 5 attempts per hour.
    """
    limit, window = getattr(settings, "BOOKING_RATE_LIMIT", (5, 3600))
    if not limit:
        return False
    key = f"booking:{page_id}:{request.META.get('REMOTE_ADDR', '')}"
    cache.add(key, 0, window)
    try:
        return cache.incr(key) > limit
    except ValueError:
        return False


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(xframe_options_exempt, name="dispatch")
class PublicBookingView(View):
    """
    Public 3-step booking page (calendar → slots → form).
    No login required.
    """

    template_name = "public/booking_form.html"

    def _available_days_json(self, page):
        """Return a JSON array of weekday codes that have available booking hours."""
        from ..utils import _get_day_hours

        schedule = page.shift_hour or page.business_hour
        if not schedule:
            return json.dumps([])
        avail = [
            code
            for code in WEEK_ORDER
            if _get_day_hours(schedule, code) != (None, None)
        ]
        return json.dumps(avail)

    def _fully_booked_dates_json(self, page):
        """Return a JSON object {ISO date: reason} for dates within the booking window
        that have no available slots. The reason is "unavailable" when the host or a
        participant has an unavailability block that day, otherwise "booked"
        (all slots taken or max_per_day reached)."""
        from ..utils import (
            _get_day_hours,
            _get_page_timezone,
            _get_unavailability_for_users,
            get_available_slots,
        )

        today = timezone.localdate()
        max_date = today + timedelta(days=page.booking_window)
        schedule = page.shift_hour or page.business_hour
        if not schedule:
            return json.dumps({})

        tz = _get_page_timezone(page)
        all_users = [page.host_id] + list(
            page.participants.values_list("id", flat=True)
        )
        fully_booked = {}
        current = today
        while current <= max_date:
            day_code = WEEK_ORDER[current.weekday()]
            start_time, end_time = _get_day_hours(schedule, day_code)
            if start_time is not None and end_time is not None:
                slots = get_available_slots(page, current)
                if not slots:
                    # Tell the visitor why the day can't be picked
                    blocked = _get_unavailability_for_users(all_users, current, tz)
                    fully_booked[current.isoformat()] = (
                        "unavailable" if blocked else "booked"
                    )
            current += timedelta(days=1)

        return json.dumps(fully_booked)

    def get(self, request, slug):
        """Render the public booking page with calendar and slot picker."""
        page = get_object_or_404(BookingPage, slug=slug, is_active=True)
        now = timezone.now()
        ctx = {
            "page": page,
            "today_iso": now.date().isoformat(),
            "max_date_iso": (
                now.date() + timedelta(days=page.booking_window)
            ).isoformat(),
            "available_days_json": self._available_days_json(page),
            "fully_booked_dates_json": self._fully_booked_dates_json(page),
        }
        return render(request, self.template_name, ctx)

    def post(self, request, slug):
        """Validate the submitted slot, create a Booking, and render the confirmation page."""
        page = get_object_or_404(BookingPage, slug=slug, is_active=True)
        if request.POST.get("website") or _booking_rate_limited(request, page.pk):
            return HttpResponse(status=429)
        booking_date_str = request.POST.get("booking_date", "")
        booking_time_str = request.POST.get("booking_time", "")
        booker_name = request.POST.get("booker_name", "").strip()
        booker_email = request.POST.get("booker_email", "").strip()
        tz_name = request.POST.get("timezone", "")

        errors = {}
        if not booker_name:
            errors["booker_name"] = _("Your name is required.")
        if not booker_email:
            errors["booker_email"] = _("Your email is required.")
        if not booking_date_str:
            errors["booking_date"] = _("Please select a date.")
        if not booking_time_str:
            errors["booking_time"] = _("Please select a time slot.")

        start_dt = None
        if booking_date_str and booking_time_str and not errors:
            try:
                from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

                from ..utils import _get_page_timezone

                local_dt = datetime.fromisoformat(
                    f"{booking_date_str}T{booking_time_str}"
                )
                try:
                    booker_tz = (
                        ZoneInfo(tz_name) if tz_name else _get_page_timezone(page)
                    )
                except (ZoneInfoNotFoundError, KeyError):
                    booker_tz = _get_page_timezone(page)
                start_dt = local_dt.replace(tzinfo=booker_tz)
            except ValueError:
                errors["booking_time"] = _("Invalid date or time.")

        if start_dt and not errors:
            host_tz = _get_page_timezone(page)
            start_in_host_tz = start_dt.astimezone(host_tz)
            selected_date = start_in_host_tz.date()
            available_slots = get_available_slots(page, selected_date)
            slot_times = [s.strftime("%H:%M") for s in available_slots]
            if start_in_host_tz.strftime("%H:%M") not in slot_times:
                errors["booking_time"] = _(
                    "That slot is no longer available. Please choose another."
                )

        # One address may not fill the calendar
        max_active = getattr(settings, "BOOKING_MAX_ACTIVE_PER_EMAIL", 2)
        if max_active and booker_email and "booker_email" not in errors:
            active = page.bookings.filter(
                booker_email__iexact=booker_email,
                status__in=["pending", "confirmed"],
                start_datetime__gte=timezone.now(),
            ).count()
            if active >= max_active:
                errors["booker_email"] = _(
                    "This email already has the maximum number of upcoming "
                    "bookings for this page. Cancel one to book another."
                )

        if errors:
            now = timezone.now()
            error_list = list(errors.values())
            ctx = {
                "page": page,
                "errors": error_list,
                "selected_date": booking_date_str,
                "selected_time": booking_time_str,
                "today_iso": now.date().isoformat(),
                "max_date_iso": (
                    now.date() + timedelta(days=page.booking_window)
                ).isoformat(),
                "available_days_json": self._available_days_json(page),
                "fully_booked_dates_json": self._fully_booked_dates_json(page),
                "form": type(
                    "F",
                    (),
                    {
                        "booker_name": type("F", (), {"value": lambda: booker_name})(),
                        "booker_email": type(
                            "F", (), {"value": lambda: booker_email}
                        )(),
                    },
                )(),
            }
            return render(request, self.template_name, ctx)

        end_dt = start_dt + timedelta(minutes=page.duration)

        answers = {}
        for q in page.questions or []:
            q_id = q.get("id", "")
            answers[q_id] = request.POST.get(f"q_{q_id}", "")

        booking = Booking.objects.create(
            booking_page=page,
            booker_name=booker_name,
            booker_email=booker_email,
            start_datetime=start_dt,
            end_datetime=end_dt,
            meeting_url="",
            status="pending",
            answers=answers,
            company=page.company,
            booker_timezone=tz_name,
        )

        if page.is_online and page.meeting_provider:
            try:
                from horilla.contrib.activity.views.create_view.meeting_helpers import (
                    generate_meeting_url,
                )

                class _BookingAdapter:
                    """Thin adapter so generate_meeting_url sees the fields it expects."""

                    title = page.title
                    start_datetime = booking.start_datetime
                    end_datetime = booking.end_datetime

                class _FakeView:
                    pass

                _v = _FakeView()
                _v.request = request
                meet_url = generate_meeting_url(
                    _v, page.meeting_provider, page.host, _BookingAdapter()
                )
                if meet_url:
                    booking.meeting_url = meet_url
                    booking.save(update_fields=["meeting_url"])
            except Exception:
                logger.exception(
                    "Failed to generate meeting URL for booking pk=%s", booking.pk
                )

        booking_submitted.send(
            sender=Booking,
            booker_name=booking.booker_name,
            booker_email=booking.booker_email,
            booking_instance=booking,
            company=page.company,
        )

        return redirect("booking:booking_confirmed", token=booking.cancellation_token)


# Embeddable on any site (iframe). Anonymous visitors only: the session cookie is
# not sent in cross-site frames, so there is no logged-in action to hijack.
@method_decorator(xframe_options_exempt, name="dispatch")
class PublicBookingConfirmedView(View):
    """
    Render the booking confirmation page for an existing booking.

    Reached via a redirect after PublicBookingView/PublicBookingRescheduleView
    create or update a booking, so reloading this page just re-runs a GET
    instead of resubmitting the booking.
    """

    def get(self, request, token):
        """Render the confirmation page for the booking identified by token."""
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        booking = get_object_or_404(Booking, cancellation_token=token)
        page = booking.booking_page
        tz_name = booking.booker_timezone

        try:
            booker_tz = (
                ZoneInfo(tz_name) if tz_name else timezone.get_current_timezone()
            )
        except (ZoneInfoNotFoundError, KeyError):
            booker_tz = timezone.get_current_timezone()

        local_start = booking.start_datetime.astimezone(booker_tz)
        local_end = booking.end_datetime.astimezone(booker_tz)
        local_date_str = local_start.strftime("%B %d, %Y")
        local_time_str = (
            f"{local_start.strftime('%I:%M %p')} – {local_end.strftime('%I:%M %p')}"
        )

        cancel_url = build_public_booking_url(
            reverse_lazy(
                "booking:booking_cancel", kwargs={"token": booking.cancellation_token}
            ),
            request=request,
        )
        reschedule_url = build_public_booking_url(
            reverse_lazy(
                "booking:booking_reschedule",
                kwargs={"token": booking.cancellation_token},
            ),
            request=request,
        )
        public_url = page.get_public_url(request)

        return render(
            request,
            "public/booking_confirmed.html",
            {
                "page": page,
                "booking": booking,
                "local_date_str": local_date_str,
                "local_time_str": local_time_str,
                "booker_tz": str(booker_tz),
                "cancel_url": cancel_url,
                "reschedule_url": reschedule_url,
                "public_url": public_url,
                "rescheduled": request.GET.get("rescheduled") == "1",
            },
        )


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(xframe_options_exempt, name="dispatch")
class PublicBookingCancelView(View):
    """Allow booker to cancel via cancellation_token. No login required."""

    def _is_blocked(self, booking):
        """Return True if cancellation is blocked by cutoff policy."""
        page = booking.booking_page
        if not page.allow_cancel:
            return True
        cutoff_dt = booking.start_datetime - timedelta(days=page.cancel_cutoff_days)
        return timezone.now() >= cutoff_dt

    def get(self, request, token):
        """Render the cancellation confirmation page for the given token."""
        booking = _booking_in_booker_tz(
            get_object_or_404(Booking, cancellation_token=token), request
        )
        if booking.status in ("cancelled", "completed"):
            return render(
                request,
                "public/booking_cancel.html",
                {"booking": booking, "already_done": True},
            )
        blocked = self._is_blocked(booking)
        return render(
            request,
            "public/booking_cancel.html",
            {"booking": booking, "already_done": False, "blocked": blocked},
        )

    def post(self, request, token):
        """Cancel the booking and send a confirmation email to the booker."""
        import threading

        from ..tasks import send_status_change_email

        booking = _booking_in_booker_tz(
            get_object_or_404(Booking, cancellation_token=token), request
        )
        if booking.status in ("cancelled", "completed") or self._is_blocked(booking):
            return render(
                request,
                "public/booking_cancel.html",
                {"booking": booking, "already_done": True},
            )
        booking.cancellation_reason = request.POST.get("reason", "")
        booking.status = "cancelled"
        booking.save(update_fields=["status", "cancellation_reason"])
        threading.Thread(
            target=send_status_change_email,
            args=(booking, "cancelled"),
            daemon=True,
        ).start()
        return render(
            request,
            "public/booking_cancel.html",
            {"booking": booking, "cancelled": True},
        )


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(xframe_options_exempt, name="dispatch")
class PublicBookingRescheduleView(View):
    """Allow booker to reschedule via cancellation_token. No login required."""

    template_name = "public/booking_form.html"
    blocked_template_name = "public/booking_reschedule.html"

    def _form_context(self, booking, **extra):
        """Context for the shared booking page in reschedule mode."""
        page = booking.booking_page
        now = timezone.now()
        helper = PublicBookingView()
        return {
            "reschedule": True,
            "booking": booking,
            "page": page,
            "today_iso": now.date().isoformat(),
            "max_date_iso": (
                now.date() + timedelta(days=page.booking_window)
            ).isoformat(),
            "available_days_json": helper._available_days_json(page),
            "fully_booked_dates_json": helper._fully_booked_dates_json(page),
            **extra,
        }

    def _is_blocked(self, booking):
        """Return True if rescheduling is blocked by cutoff policy or not allowed."""
        page = booking.booking_page
        if not page.allow_reschedule:
            return True
        cutoff_dt = booking.start_datetime - timedelta(days=page.reschedule_cutoff_days)
        return timezone.now() >= cutoff_dt

    def get(self, request, token):
        """Render the booking page in reschedule mode (same design as booking)."""
        booking = _booking_in_booker_tz(
            get_object_or_404(Booking, cancellation_token=token), request
        )
        if booking.status in ("cancelled", "completed") or self._is_blocked(booking):
            return render(
                request,
                self.blocked_template_name,
                {"booking": booking, "blocked": True},
            )
        return render(request, self.template_name, self._form_context(booking))

    def post(self, request, token):
        """Reschedule the booking to the new slot and send a confirmation email."""
        import threading

        from ..tasks import send_status_change_email

        booking = _booking_in_booker_tz(
            get_object_or_404(Booking, cancellation_token=token), request
        )
        if booking.status in ("cancelled", "completed") or self._is_blocked(booking):
            return render(
                request,
                self.blocked_template_name,
                {"booking": booking, "blocked": True},
            )

        page = booking.booking_page
        booking_date_str = request.POST.get("booking_date", "")
        booking_time_str = request.POST.get("booking_time", "")
        errors = {}
        tz_name = ""

        start_dt = None
        if booking_date_str and booking_time_str:
            try:
                from ..utils import _get_page_timezone

                local_dt = datetime.fromisoformat(
                    f"{booking_date_str}T{booking_time_str}"
                )
                from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

                tz_name = request.POST.get("timezone") or booking.booker_timezone
                try:
                    booker_tz = (
                        ZoneInfo(tz_name) if tz_name else _get_page_timezone(page)
                    )
                except (ZoneInfoNotFoundError, KeyError):
                    booker_tz = _get_page_timezone(page)
                    tz_name = ""
                start_dt = local_dt.replace(tzinfo=booker_tz)
            except ValueError:
                errors["booking_time"] = _("Invalid date or time.")
        else:
            errors["booking_time"] = _("Please select a date and time.")

        if start_dt and not errors:
            host_start = start_dt.astimezone(_get_page_timezone(page))
            available_slots = get_available_slots(page, host_start.date())
            slot_times = [s.strftime("%H:%M") for s in available_slots]
            if host_start.strftime("%H:%M") not in slot_times:
                errors["booking_time"] = _("That slot is no longer available.")

        if errors:
            return render(
                request,
                self.template_name,
                self._form_context(
                    booking,
                    errors=list(errors.values()),
                    selected_date=booking_date_str,
                    selected_time=booking_time_str,
                ),
            )

        end_dt = start_dt + timedelta(minutes=page.duration)
        booking.start_datetime = start_dt
        booking.end_datetime = end_dt
        booking.status = "pending"
        update_fields = ["start_datetime", "end_datetime", "status"]
        if tz_name:
            booking.booker_timezone = tz_name
            update_fields.append("booker_timezone")
        booking.save(update_fields=update_fields)

        threading.Thread(
            target=send_status_change_email,
            args=(booking, "pending"),
            daemon=True,
        ).start()

        return redirect(f"{booking.confirmed_url}?rescheduled=1")
