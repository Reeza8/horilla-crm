"""Signals for the Horilla Calls Integration app."""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from horilla.contrib.activity.models import Activity
from horilla.contrib.core.models import HorillaContentType

from .models import CallLog

logger = logging.getLogger(__name__)

_TERMINAL_STATUSES = {
    CallLog.STATUS_COMPLETED,
    CallLog.STATUS_CANCELLED,
    CallLog.STATUS_FAILED,
    CallLog.STATUS_NO_ANSWER,
    CallLog.STATUS_BUSY,
}

_STATUS_TO_ACTIVITY_STATUS = {
    CallLog.STATUS_INITIATED: "scheduled",
    CallLog.STATUS_RINGING: "scheduled",
    CallLog.STATUS_IN_PROGRESS: "in_progress",
    CallLog.STATUS_COMPLETED: "completed",
    CallLog.STATUS_CANCELLED: "cancelled",
    CallLog.STATUS_FAILED: "cancelled",
    CallLog.STATUS_NO_ANSWER: "cancelled",
    CallLog.STATUS_BUSY: "cancelled",
}


@receiver(post_save, sender=CallLog)
def track_call_in_history(sender, instance, created, **kwargs):
    """
    Maintain a linked Activity for each CallLog so call events appear in the
    History tab of the related Account / Lead / Contact.

    - On creation: creates an Activity (log_call) linked via GFK to the related object.
    - On status change to a terminal status: updates that Activity's status so the
      change appears as an auditlog entry in History.
    - Skips live/in-progress status changes to avoid polluting history.
    """
    if not instance.related_model_name or not instance.related_object_id:
        return

    is_status_change = not created and "status" in (kwargs.get("update_fields") or [])

    if not created and not is_status_change:
        return

    if is_status_change and instance.status not in _TERMINAL_STATUSES:
        return

    try:
        related = instance.get_related_object()
        if not related:
            return

        content_type = HorillaContentType.objects.get_for_model(related.__class__)
        activity_status = _STATUS_TO_ACTIVITY_STATUS.get(instance.status, "scheduled")

        if created:
            activity = Activity.objects.create(
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
                status=activity_status,
                owner=instance.agent.user if instance.agent else None,
                company=instance.company,
                content_type=content_type,
                object_id=related.pk,
            )
            info = dict(instance.additional_info or {})
            info["linked_activity_id"] = activity.pk
            CallLog.all_objects.filter(pk=instance.pk).update(additional_info=info)
        else:
            linked_id = (instance.additional_info or {}).get("linked_activity_id")
            if linked_id:
                try:
                    activity = Activity.objects.get(pk=linked_id)
                    activity.status = activity_status
                    activity.call_duration_seconds = instance.duration_seconds
                    activity.call_duration_display = instance.get_duration_display()
                    activity.save(
                        update_fields=[
                            "status",
                            "call_duration_seconds",
                            "call_duration_display",
                        ]
                    )
                except Activity.DoesNotExist:
                    pass
    except Exception as exc:
        logger.warning(
            "Failed to track call in history for CallLog %s: %s", instance.pk, exc
        )
