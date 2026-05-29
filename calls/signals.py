"""Signals for the Horilla Calls Integration app."""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import CallLog

logger = logging.getLogger(__name__)


@receiver(post_save, sender=CallLog)
def auto_create_activity_on_completion(sender, instance, created, **kwargs):
    """
    When a CallLog reaches 'completed' status, auto-create an Activity of
    type 'log_call' linked to the same Lead/Contact.

    Skips creation if no related object is set or if the activity already exists.
    Uses update_fields guard to prevent recursive signal triggering.
    """
    if instance.status != CallLog.STATUS_COMPLETED:
        return

    # Only run when status changed to completed, not on every save
    if not created and "status" not in (kwargs.get("update_fields") or []):
        return

    if not instance.related_model_name or not instance.related_object_id:
        return

    try:
        from horilla.contrib.activity.models import Activity

        related = instance.get_related_object()
        if not related:
            return

        Activity.objects.create(
            activity_type="log_call",
            subject=(
                f"Call {instance.get_direction_display()} — "
                f"{instance.from_number} → {instance.to_number}"
            ),
            call_duration_seconds=instance.duration_seconds,
            call_duration_display=instance.get_duration_display(),
            call_type=instance.direction,
            call_purpose="telephony",
            notes="",
            status="completed",
            owner=instance.agent.user if instance.agent else None,
            company=instance.company,
        )
    except Exception as exc:
        logger.warning(
            "Failed to auto-create Activity for CallLog %s: %s", instance.pk, exc
        )
