"""Email and in-app notifications sent when a lead is assigned by a rule."""

# Standard library imports
import logging
import threading

# Third-party imports (Django)
from django.template import engines

# First party imports (Horilla)
from horilla.contrib.notifications.methods import create_notification
from horilla.contrib.utils.middlewares import _thread_local
from horilla.utils import timezone

logger = logging.getLogger(__name__)


def send_assignment_email(condition, lead, assigned_user):
    """Send assignment email to the assigned user using the condition's mail template."""
    try:
        from horilla.contrib.core.models import HorillaContentType
        from horilla.contrib.mail.models import HorillaMail, HorillaMailConfiguration
        from horilla.contrib.mail.services import HorillaMailManager

        tmpl = condition.mail_template
        if not tmpl or not assigned_user.email:
            return

        company = getattr(lead, "company", None)
        sender = None
        if company:
            sender = (
                HorillaMailConfiguration.objects.filter(
                    company=company, mail_channel="outgoing", is_primary=True
                ).first()
                or HorillaMailConfiguration.objects.filter(
                    company=company, mail_channel="outgoing"
                ).first()
            )

        content_type = HorillaContentType.objects.get_for_model(lead)
        mail = HorillaMail.objects.create(
            sender=sender,
            to=assigned_user.email,
            subject=tmpl.subject or "",
            body=tmpl.body or "",
            content_type=content_type,
            object_id=lead.pk,
            mail_status="draft",
            company=company,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

        context = {"instance": lead, "user": assigned_user, "lead": lead}

        def _send():
            try:
                if sender:
                    setattr(_thread_local, "from_mail_id", sender.pk)
                HorillaMailManager.send_mail(mail, context=context)
            except Exception as exc:
                logger.error(
                    "Assignment rule email send error (lead=%s): %s", lead.pk, exc
                )
            finally:
                if hasattr(_thread_local, "from_mail_id"):
                    delattr(_thread_local, "from_mail_id")

        threading.Thread(target=_send, daemon=True).start()

    except Exception as exc:
        logger.error("Assignment rule email setup error (lead=%s): %s", lead.pk, exc)


def send_assignment_notification(condition, lead, assigned_user):
    """Send in-app notification to the assigned user using the condition's notification template."""
    try:
        tmpl = condition.notification_template
        if not tmpl:
            return

        context = {"instance": lead, "lead": lead}
        django_engine = engines["django"]
        msg_src = (
            ("{% load horilla_tags %}\n" + tmpl.message).strip() if tmpl.message else ""
        )
        message = (
            django_engine.from_string(msg_src).render(context)[:500]
            if msg_src
            else f"New lead assigned: {lead}"
        )

        lead_url = (
            str(lead.get_detail_url()) if hasattr(lead, "get_detail_url") else None
        )
        create_notification(
            user=assigned_user,
            message=message,
            sender=None,
            url=lead_url,
            instance=lead,
            read=False,
        )
    except Exception as exc:
        logger.error("Assignment rule notification error (lead=%s): %s", lead.pk, exc)


def deliver_assignment_notifications(condition, lead, assigned_user):
    """Send whatever the condition's ``notify_method`` asks for."""
    method = condition.notify_method
    if method in ("email", "both"):
        send_assignment_email(condition, lead, assigned_user)
    if method in ("notification", "both"):
        send_assignment_notification(condition, lead, assigned_user)


def notify_assignment(condition_id, lead_id):
    """
    Notify the owner of a lead that a form assigned it through a rule.

    Used when the owner was already chosen in the form (the "Apply assignment
    rule" option), so the engine does not pick anyone again and only the
    notifications configured on the condition are sent.
    """
    # Local imports
    from horilla_crm.leads.assignment.pool import OWNER_FIELD
    from horilla_crm.leads.models import Lead, LeadAssignmentCondition

    try:
        condition = LeadAssignmentCondition.all_objects.get(pk=condition_id)
        lead = Lead.all_objects.select_related(OWNER_FIELD).get(pk=lead_id)
    except (LeadAssignmentCondition.DoesNotExist, Lead.DoesNotExist):
        return
    deliver_assignment_notifications(condition, lead, getattr(lead, OWNER_FIELD))
