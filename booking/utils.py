"""
Utility functions for horilla_booking — slot availability calculation.
Slots are derived from the BookingPage's linked BusinessHour, not BookingAvailability.
"""

# Standard library imports
from datetime import date, datetime, time, timedelta

# First party imports (Horilla)
from horilla.utils import timezone

# Maps Python weekday() (0=Mon…6=Sun) → BusinessHour day-code
_WEEKDAY_CODE = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# Maps day-code → BusinessHour field prefix (e.g. "mon" → "monday")
_DAY_PREFIX = {
    "mon": "monday",
    "tue": "tuesday",
    "wed": "wednesday",
    "thu": "thursday",
    "fri": "friday",
    "sat": "saturday",
    "sun": "sunday",
}


def _get_day_hours(bh, day_code):
    """
    Return (start_time, end_time) for a given day from a BusinessHour or ShiftHour.
    Returns (None, None) if the day is closed / not working.
    """
    bh_type = getattr(bh, "business_hour_type", None)

    if bh_type == "24_7":
        return time(0, 0), time(23, 59)

    if bh_type == "24_5":
        if day_code in ("sat", "sun"):
            return None, None
        return time(0, 0), time(23, 59)

    # "custom" BusinessHour or ShiftHour — both use normalized_week_day_codes + timing_type
    active_codes = set(bh.normalized_week_day_codes())
    if day_code not in active_codes:
        return None, None

    timing = getattr(bh, "timing_type", None) or "same"
    if timing == "same":
        return bh.default_start_time, bh.default_end_time

    # "different" — per-day fields
    prefix = _DAY_PREFIX[day_code]
    start = getattr(bh, f"{prefix}_start", None)
    end = getattr(bh, f"{prefix}_end", None)
    if start == time(0, 0) and end == time(0, 0):
        start, end = None, None
    return start, end


def _is_holiday(bh, target_date: date) -> bool:
    """Return True if target_date falls within any holiday in the BusinessHour."""
    for holiday in bh.holidays.all():
        h_start = getattr(holiday, "start_date", None)
        h_end = getattr(holiday, "end_date", h_start)
        if h_start and h_end and h_start <= target_date <= h_end:
            return True
        if h_start and not h_end and h_start == target_date:
            return True
    return False


def _get_unavailability_for_users(users, target_date: date, tz) -> list:
    """
    Return (from_datetime, to_datetime) blocks from UserAvailability for
    all given users that overlap target_date.
    """
    try:
        from horilla.contrib.calendar.models import UserAvailability

        day_start = timezone.make_aware(datetime.combine(target_date, time(0, 0)), tz)
        day_end = timezone.make_aware(
            datetime.combine(target_date, time(23, 59, 59)), tz
        )
        blocks = UserAvailability.objects.filter(
            user__in=users,
            from_datetime__lt=day_end,
            to_datetime__gt=day_start,
        ).values_list("from_datetime", "to_datetime")
        return list(blocks)
    except Exception:
        return []


def get_available_slots(page, target_date: date) -> list[time]:
    """
    Return a list of available start-time slots for `target_date` on `page`.

    Rules (in order):
    1. target_date must be within page.booking_window days from today.
    2. BookingPage must have a linked BusinessHour.
    3. The weekday must be a working day in that BusinessHour (not closed, not a holiday).
    4. Slots are generated from day start_time to end_time in steps of
       (duration + buffer_after) minutes.
    5. Slots earlier than now + advance_notice minutes are skipped.
    6. Slots that overlap existing confirmed/pending bookings are skipped.
    7. If max_per_day is set, only that many slots are returned.
    """
    today = timezone.localdate()
    now = timezone.now()
    max_date = today + timedelta(days=page.booking_window)

    if target_date < today or target_date > max_date:
        return []

    # Prefer shift_hour for slot times; fall back to business_hour
    schedule = page.shift_hour or page.business_hour
    if not schedule:
        return []

    # Holiday check only applies to BusinessHour (ShiftHour has no holidays)
    bh = page.business_hour
    if bh and _is_holiday(bh, target_date):
        return []

    day_code = _WEEKDAY_CODE[target_date.weekday()]
    start_time, end_time = _get_day_hours(schedule, day_code)
    if start_time is None or end_time is None:
        return []

    step_minutes = page.duration + page.buffer_after
    if step_minutes <= 0:
        step_minutes = page.duration or 30

    # Existing bookings that day (pending or confirmed)
    existing = list(
        page.bookings.filter(
            start_datetime__date=target_date,
            status__in=["pending", "confirmed"],
        ).values_list("start_datetime", "end_datetime")
    )

    # If max_per_day is set and already reached, hide the entire date
    if page.max_per_day and len(existing) >= page.max_per_day:
        return []

    advance_cutoff = now + timedelta(minutes=page.advance_notice)
    tz = timezone.get_current_timezone()

    # Collect host + all participants, then fetch their combined unavailability
    all_users = [page.host_id] + list(page.participants.values_list("id", flat=True))
    host_unavailable = _get_unavailability_for_users(all_users, target_date, tz)

    slots = []
    current = datetime.combine(target_date, start_time)
    end_boundary = datetime.combine(target_date, end_time)

    while True:
        slot_end = current + timedelta(minutes=page.duration)
        if slot_end > end_boundary:
            break

        current_aware = timezone.make_aware(current, tz)
        slot_end_aware = timezone.make_aware(slot_end, tz)

        # Skip if too soon
        if current_aware < advance_cutoff:
            current += timedelta(minutes=step_minutes)
            continue

        # Skip if overlaps existing booking
        overlaps = any(
            current_aware < bend and slot_end_aware > bstart
            for bstart, bend in existing
        )

        # Skip if host marked themselves unavailable during this slot
        host_blocked = any(
            current_aware < u_end and slot_end_aware > u_start
            for u_start, u_end in host_unavailable
        )

        if not overlaps and not host_blocked:
            slots.append(current.time())

        current += timedelta(minutes=step_minutes)

    return slots


def get_all_slots(page, target_date: date) -> dict:
    """
    Return all time slots for target_date split into 'available' and 'booked' lists.
    Booked slots are those that overlap an existing pending/confirmed booking.
    Slots blocked by advance_notice or host unavailability are excluded entirely.
    """
    today = timezone.localdate()
    now = timezone.now()
    max_date = today + timedelta(days=page.booking_window)

    if target_date < today or target_date > max_date:
        return {"available": [], "booked": []}

    schedule = page.shift_hour or page.business_hour
    if not schedule:
        return {"available": [], "booked": []}

    bh = page.business_hour
    if bh and _is_holiday(bh, target_date):
        return {"available": [], "booked": []}

    day_code = _WEEKDAY_CODE[target_date.weekday()]
    start_time, end_time = _get_day_hours(schedule, day_code)
    if start_time is None or end_time is None:
        return {"available": [], "booked": []}

    step_minutes = page.duration + page.buffer_after
    if step_minutes <= 0:
        step_minutes = page.duration or 30

    existing = list(
        page.bookings.filter(
            start_datetime__date=target_date,
            status__in=["pending", "confirmed"],
        ).values_list("start_datetime", "end_datetime")
    )

    advance_cutoff = now + timedelta(minutes=page.advance_notice)
    tz = timezone.get_current_timezone()

    all_users = [page.host_id] + list(page.participants.values_list("id", flat=True))
    host_unavailable = _get_unavailability_for_users(all_users, target_date, tz)

    available = []
    booked = []
    current = datetime.combine(target_date, start_time)
    end_boundary = datetime.combine(target_date, end_time)

    while True:
        slot_end = current + timedelta(minutes=page.duration)
        if slot_end > end_boundary:
            break

        current_aware = timezone.make_aware(current, tz)
        slot_end_aware = timezone.make_aware(slot_end, tz)

        if current_aware < advance_cutoff:
            current += timedelta(minutes=step_minutes)
            continue

        host_blocked = any(
            current_aware < u_end and slot_end_aware > u_start
            for u_start, u_end in host_unavailable
        )

        if not host_blocked:
            # A slot is "booked" when an existing booking starts within this slot's window
            overlaps = any(
                current_aware <= bstart < slot_end_aware for bstart, bend in existing
            )
            if overlaps:
                booked.append(current.strftime("%H:%M"))
            else:
                available.append(current.strftime("%H:%M"))

        current += timedelta(minutes=step_minutes)

    return {"available": available, "booked": booked}


def get_available_dates(page, year: int, month: int) -> list[date]:
    """Return dates in (year, month) that have at least one available slot."""
    import calendar as _cal

    today = timezone.localdate()
    max_date = today + timedelta(days=page.booking_window)

    result = []
    _, days_in_month = _cal.monthrange(year, month)
    for day in range(1, days_in_month + 1):
        d = date(year, month, day)
        if d < today or d > max_date:
            continue
        if get_available_slots(page, d):
            result.append(d)
    return result
