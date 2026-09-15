"""Celery tasks for activity reminders."""

# Standard library imports
import logging
from datetime import timedelta

# Third-party imports (Django)
from celery import shared_task

# First party imports (Horilla)
from horilla.utils import timezone
from horilla.utils.branding import load_branding

logger = logging.getLogger(__name__)


@shared_task
def send_meeting_reminders():
    """
    Periodic task: find meetings whose reminder time has arrived and send reminder emails.
    Runs every minute via Celery Beat.
    """
    from horilla.contrib.activity.models import Activity

    now = timezone.now()

    # Find all scheduled/not-started online meetings with a reminder set and a start time
    meetings = Activity.objects.filter(
        activity_type="meeting",
        reminder__isnull=False,
        start_datetime__isnull=False,
        status__in=["not_started", "scheduled"],
    ).exclude(reminder="")

    sent_count = 0
    for meeting in meetings:
        try:
            reminder_minutes = int(meeting.reminder)
        except (ValueError, TypeError):
            continue

        remind_at = meeting.start_datetime - timedelta(minutes=reminder_minutes)

        # Fire only within this minute's window (now <= remind_at < now + 1 min)
        if not now <= remind_at < now + timedelta(minutes=1):
            continue

        _send_reminder_for_meeting(meeting)
        sent_count += 1

    logger.info("Meeting reminders sent: %d", sent_count)
    return f"Sent {sent_count} meeting reminders"


def _localtime_for_meeting(dt, meeting):
    """Convert a UTC-aware datetime using user.time_zone → company.time_zone → UTC."""
    if dt is None:
        return None
    try:
        from zoneinfo import ZoneInfo

        host_user = meeting.meeting_host or meeting.owner
        tz_name = (
            getattr(host_user, "time_zone", None) if host_user else None
        ) or getattr(meeting.company, "time_zone", None)
        if tz_name:
            return dt.astimezone(ZoneInfo(tz_name))
    except Exception:
        pass
    return dt  # return as-is (UTC) rather than silently wrong local time


def _send_reminder_for_meeting(meeting):
    """Send reminder email to all participants and external participants."""
    from django.conf import settings
    from django.core.mail import EmailMultiAlternatives, get_connection

    title = meeting.title or meeting.subject or "Meeting"
    meeting_url = meeting.meeting_url or ""
    start = meeting.start_datetime
    reminder_minutes = int(meeting.reminder)
    host_user = meeting.meeting_host or meeting.owner
    host_name = str(host_user or "")

    local_start = _localtime_for_meeting(start, meeting)
    start_str = (
        local_start.strftime("%A, %B %d, %Y at %I:%M %p") if local_start else "TBD"
    )

    if reminder_minutes >= 1440:
        reminder_label = "1 day"
    elif reminder_minutes >= 60:
        reminder_label = f"{reminder_minutes // 60} hour(s)"
    else:
        reminder_label = f"{reminder_minutes} minutes"

    # Collect recipients: internal participants + external
    recipient_emails = list(
        meeting.participants.exclude(email="").values_list("email", flat=True)
    )
    external = meeting.external_participants or []
    if isinstance(external, list):
        recipient_emails += external
    all_recipients = list(dict.fromkeys(recipient_emails))  # dedup

    if not all_recipients:
        return

    # Resolve outgoing mail config
    mail_config = None
    try:
        from horilla.contrib.mail.models import HorillaMailConfiguration

        company = meeting.company
        mail_config = (
            HorillaMailConfiguration.objects.filter(
                company=company, mail_channel="outgoing", is_primary=True
            ).first()
            or HorillaMailConfiguration.objects.filter(
                mail_channel="outgoing", is_primary=True
            ).first()
            or HorillaMailConfiguration.objects.filter(mail_channel="outgoing").first()
        )
    except Exception:
        pass

    company_name = (
        str(meeting.company) if meeting.company else str(load_branding()["TITLE"])
    )

    html_body = f"""
<div style="max-width:650px;margin:auto;background:white;border-radius:12px;padding:35px;box-shadow:0 4px 12px rgba(0,0,0,0.08)">
  <h2 style="color:#000000;text-align:center;font-size:24px;margin-bottom:25px">
    Meeting Reminder
  </h2>

  <p style="font-size:14px;color:#333;line-height:1.6">
    Your meeting starts in <strong>{reminder_label}</strong>.
  </p>

  <div style="margin:20px 0;padding:15px;background:#fdf2f1;border-left:4px solid #e54f38;border-radius:6px">
    <p style="margin:6px 0;font-size:14px;color:#333">
      &#128197; <strong>Title:</strong> {title}
    </p>
    <p style="margin:6px 0;font-size:14px;color:#333">
      &#128336; <strong>When:</strong> {start_str}
    </p>
    <p style="margin:6px 0;font-size:14px;color:#333">
      &#128100; <strong>Host:</strong> {host_name}
    </p>
    {f'<p style="margin:6px 0;font-size:14px;color:#333">&#128279; <strong>Join Link:</strong> <a href="{meeting_url}" style="color:#e54f38;">{meeting_url}</a></p>' if meeting_url else ""}
  </div>

  {f'<div style="text-align:center;margin-top:25px"><a href="{meeting_url}" style="display:inline-block;padding:10px 20px;background-color:#e54f38;color:white;text-decoration:none;border-radius:6px;font-weight:500;margin:5px">Join Meeting</a></div>' if meeting_url else ""}

  <hr style="margin:30px 0;border:none;border-top:1px solid #eee">

  <p style="font-size:12px;color:#888;text-align:center;line-height:1.5">
    This reminder was sent via <strong>{company_name}</strong>.<br>
    If you were not expecting this, please ignore this email.
  </p>
</div>"""

    plain_body = (
        f"Reminder: Your meeting '{title}' starts in {reminder_label}.\n\n"
        f"When: {start_str}\nHost: {host_name}\n"
        + (f"Join: {meeting_url}\n" if meeting_url else "")
    )

    from_email = (
        mail_config.from_email
        if mail_config and mail_config.from_email
        else getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com")
    )

    try:
        connection = (
            get_connection("horilla.contrib.mail.backends.HorillaDefaultMailBackend")
            if mail_config
            else get_connection()
        )
        msg = EmailMultiAlternatives(
            subject=f"Reminder: {title} starts in {reminder_label}",
            body=plain_body,
            from_email=from_email,
            to=all_recipients,
            connection=connection,
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=True)
        logger.info("Reminder sent for meeting %d to %s", meeting.pk, all_recipients)
    except Exception as e:
        logger.error("Failed to send reminder for meeting %d: %s", meeting.pk, e)
