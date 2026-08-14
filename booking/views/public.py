"""
Public-facing booking views — slot availability, booking form, cancel, and reschedule.
No login required.
"""

# Standard library imports
import json
import logging
from datetime import date, datetime, timedelta

# Third-party imports (Django)
from django.views.generic import View

from horilla.shortcuts import get_object_or_404, redirect, render
from horilla.urls import reverse_lazy

# First party imports (Horilla)
from horilla.utils import timezone
from horilla.utils.translation import gettext_lazy as _
from horilla.web import JsonResponse

# Local imports
from ..models import Booking, BookingPage
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
        result = {"slots": [], "booked_slots": []}
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
            except ValueError:
                pass

        response = JsonResponse(result)
        response["Cache-Control"] = "no-store"
        return response


class PublicBookingView(View):
    """
    Public 3-step booking page (calendar → slots → form).
    No login required.
    """

    template_name = "public/booking_form.html"

    def _available_days_json(self, page):
        """Return a JSON array of weekday codes that have available booking hours."""
        from ..utils import _WEEKDAY_CODE, _get_day_hours

        schedule = page.shift_hour or page.business_hour
        if not schedule:
            return json.dumps([])
        avail = [
            code
            for code in _WEEKDAY_CODE
            if _get_day_hours(schedule, code) != (None, None)
        ]
        return json.dumps(avail)

    def _fully_booked_dates_json(self, page):
        """Return a JSON array of ISO date strings that are within the booking window
        but have no available slots (all slots taken or max_per_day reached)."""
        from ..utils import _WEEKDAY_CODE, _get_day_hours, get_available_slots

        today = timezone.localdate()
        max_date = today + timedelta(days=page.booking_window)
        schedule = page.shift_hour or page.business_hour
        if not schedule:
            return json.dumps([])

        fully_booked = []
        current = today
        while current <= max_date:
            day_code = _WEEKDAY_CODE[current.weekday()]
            start_time, end_time = _get_day_hours(schedule, day_code)
            if start_time is not None and end_time is not None:
                slots = get_available_slots(page, current)
                if not slots:
                    fully_booked.append(current.isoformat())
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

        cancel_url = request.build_absolute_uri(
            reverse_lazy(
                "booking:booking_cancel", kwargs={"token": booking.cancellation_token}
            )
        )
        reschedule_url = request.build_absolute_uri(
            reverse_lazy(
                "booking:booking_reschedule",
                kwargs={"token": booking.cancellation_token},
            )
        )
        public_url = request.build_absolute_uri(
            reverse_lazy("booking:public_booking", kwargs={"slug": page.slug})
        )

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
        booking = get_object_or_404(Booking, cancellation_token=token)
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

        booking = get_object_or_404(Booking, cancellation_token=token)
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


class PublicBookingRescheduleView(View):
    """Allow booker to reschedule via cancellation_token. No login required."""

    template_name = "public/booking_reschedule.html"

    def _is_blocked(self, booking):
        """Return True if rescheduling is blocked by cutoff policy or not allowed."""
        page = booking.booking_page
        if not page.allow_reschedule:
            return True
        cutoff_dt = booking.start_datetime - timedelta(days=page.reschedule_cutoff_days)
        return timezone.now() >= cutoff_dt

    def get(self, request, token):
        """Render the reschedule page with available days and slot picker."""
        from ..utils import _WEEKDAY_CODE, _get_day_hours

        booking = get_object_or_404(Booking, cancellation_token=token)
        if booking.status in ("cancelled", "completed") or self._is_blocked(booking):
            return render(
                request, self.template_name, {"booking": booking, "blocked": True}
            )
        page = booking.booking_page
        now = timezone.now()
        bh = page.business_hour
        avail = [
            c for c in _WEEKDAY_CODE if bh and _get_day_hours(bh, c) != (None, None)
        ]
        ctx = {
            "booking": booking,
            "page": page,
            "today_iso": now.date().isoformat(),
            "max_date_iso": (
                now.date() + timedelta(days=page.booking_window)
            ).isoformat(),
            "available_days_json": json.dumps(avail),
            "blocked": False,
        }
        return render(request, self.template_name, ctx)

    def post(self, request, token):
        """Reschedule the booking to the new slot and send a confirmation email."""
        import threading

        from ..tasks import send_status_change_email

        booking = get_object_or_404(Booking, cancellation_token=token)
        if booking.status in ("cancelled", "completed") or self._is_blocked(booking):
            return render(
                request, self.template_name, {"booking": booking, "blocked": True}
            )

        page = booking.booking_page
        booking_date_str = request.POST.get("booking_date", "")
        booking_time_str = request.POST.get("booking_time", "")
        errors = {}

        start_dt = None
        if booking_date_str and booking_time_str:
            try:
                from ..utils import _get_page_timezone

                local_dt = datetime.fromisoformat(
                    f"{booking_date_str}T{booking_time_str}"
                )
                tz = _get_page_timezone(page)
                start_dt = timezone.make_aware(local_dt, tz)
            except ValueError:
                errors["booking_time"] = _("Invalid date or time.")
        else:
            errors["booking_time"] = _("Please select a date and time.")

        if start_dt and not errors:
            available_slots = get_available_slots(page, start_dt.date())
            slot_times = [s.strftime("%H:%M") for s in available_slots]
            if booking_time_str not in slot_times:
                errors["booking_time"] = _("That slot is no longer available.")

        if errors:
            now = timezone.now()
            return render(
                request,
                self.template_name,
                {
                    "booking": booking,
                    "page": page,
                    "errors": errors,
                    "today_iso": now.date().isoformat(),
                    "max_date_iso": (
                        now.date() + timedelta(days=page.booking_window)
                    ).isoformat(),
                    "blocked": False,
                    "post": request.POST,
                },
            )

        end_dt = start_dt + timedelta(minutes=page.duration)
        booking.start_datetime = start_dt
        booking.end_datetime = end_dt
        booking.status = "pending"
        booking.save(update_fields=["start_datetime", "end_datetime", "status"])

        threading.Thread(
            target=send_status_change_email,
            args=(booking, "pending"),
            daemon=True,
        ).start()

        confirmed_url = reverse_lazy(
            "booking:booking_confirmed", kwargs={"token": booking.cancellation_token}
        )
        return redirect(f"{confirmed_url}?rescheduled=1")
