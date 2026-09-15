"""
Signals for the cadences app
"""

import logging

# Standard library imports
import sys
from datetime import timedelta

# Third-party imports (Django)
from django.dispatch import receiver

from horilla.contrib.activity.models import Activity
from horilla.contrib.automations.methods import (
    evaluate_condition,
    resolve_mail_recipients,
)
from horilla.contrib.core.models import HorillaContentType
from horilla.contrib.mail.models import HorillaMail, HorillaMailConfiguration
from horilla.contrib.mail.services import HorillaMailManager
from horilla.contrib.utils.middlewares import _thread_local
from horilla.db import transaction
from horilla.db.models.signals import post_save, pre_save

# First party imports (Horilla)
from horilla.utils import timezone

# Local imports
from .models import Cadence, CadenceFollowUp

logger = logging.getLogger(__name__)


def _is_migrate_command():
    return "migrate" in sys.argv


def _is_cadence_supported_instance(instance):
    from horilla.registry.feature import FEATURE_REGISTRY

    return instance.__class__ in FEATURE_REGISTRY["cadence_models"]


def _evaluate_cadence_conditions(cadence, instance):
    conditions = getattr(cadence, "_prefetched_objects_cache", {}).get("conditions")
    if conditions is None:
        conditions = cadence.conditions.all()
    conditions = sorted(
        conditions, key=lambda condition: (condition.order, condition.id)
    )
    if not conditions:
        return True
    result = None
    for idx, condition in enumerate(conditions):
        current = evaluate_condition(condition, instance)
        if idx == 0 or condition.logical_operator == "and":
            result = current if result is None else (result and current)
        elif condition.logical_operator == "or":
            result = current if result is None else (result or current)
        else:
            result = current if result is None else (result and current)
    return bool(result)


def _existing_runtime_followup_ids(instance):
    content_type = HorillaContentType.objects.get_for_model(instance.__class__)
    existing = set()
    qs = Activity.all_objects.filter(content_type=content_type, object_id=instance.pk)
    for activity in qs.only("additional_info"):
        info = activity.additional_info or {}
        runtime = info.get("cadence_runtime") if isinstance(info, dict) else None
        if runtime and runtime.get("followup_id"):
            if getattr(instance, "company_id", None) and not activity.company_id:
                Activity.all_objects.filter(pk=activity.pk).update(
                    company_id=instance.company_id
                )
            existing.add(runtime["followup_id"])
    mail_qs = HorillaMail.objects.filter(
        content_type=content_type, object_id=instance.pk
    )
    for mail in mail_qs.only("additional_info"):
        info = mail.additional_info or {}
        runtime = info.get("cadence_runtime") if isinstance(info, dict) else None
        if runtime and runtime.get("followup_id"):
            existing.add(runtime["followup_id"])
    return existing


def _dedupe_runtime_activities_for_instance(instance):
    """
    Keep only one runtime activity per (cadence_id, followup_id) for a record.
    Older buggy runs may have inserted duplicates; we keep the earliest one.
    """
    content_type = HorillaContentType.objects.get_for_model(instance.__class__)
    qs = Activity.all_objects.filter(
        content_type=content_type, object_id=instance.pk
    ).order_by("created_at", "id")
    seen = set()
    duplicate_ids = []
    for activity in qs.only("id", "additional_info"):
        info = activity.additional_info or {}
        runtime = info.get("cadence_runtime") if isinstance(info, dict) else None
        if not runtime:
            continue
        cadence_id = runtime.get("cadence_id")
        followup_id = runtime.get("followup_id")
        if not cadence_id or not followup_id:
            continue
        key = (cadence_id, followup_id)
        if key in seen:
            duplicate_ids.append(activity.id)
        else:
            seen.add(key)
    if duplicate_ids:
        Activity.all_objects.filter(id__in=duplicate_ids).delete()


def _activity_status_key(activity):
    if activity.activity_type == "task":
        return activity.status
    if activity.activity_type == "log_call":
        return activity.status
    return None


def _resolve_outgoing_mail_sender(company):
    sender = None
    if company:
        sender = (
            HorillaMailConfiguration.all_objects.filter(
                company=company, mail_channel="outgoing", is_primary=True
            ).first()
            or HorillaMailConfiguration.all_objects.filter(
                company=company, mail_channel="outgoing"
            ).first()
        )
    if not sender:
        sender = HorillaMailConfiguration.all_objects.filter(
            mail_channel="outgoing", is_primary=True
        ).first()
    return sender


def _create_email_draft_for_followup(instance, cadence, followup, content_type):
    if not followup.email_template_id:
        return None
    template = followup.email_template
    actor = getattr(instance, "updated_by", None) or getattr(
        instance, "created_by", None
    )
    company = getattr(instance, "company", None)
    sender = _resolve_outgoing_mail_sender(company)
    if not sender:
        logger.warning(
            "Cadence email follow-up skipped (no outgoing server): cadence=%s followup=%s record=%s:%s",
            cadence.pk,
            followup.pk,
            instance.__class__.__name__,
            instance.pk,
        )
        return None
    recipients = resolve_mail_recipients(followup.to or "", instance, actor)
    draft = HorillaMail.objects.create(
        sender=sender,
        to=",".join(recipients),
        subject=template.subject or "",
        body=template.body or "",
        content_type=content_type,
        object_id=instance.pk,
        mail_status="draft",
        company=company,
        created_by=actor if getattr(actor, "pk", None) else None,
        updated_by=actor if getattr(actor, "pk", None) else None,
        additional_info={
            "cadence_runtime": {
                "cadence_id": cadence.pk,
                "followup_id": followup.pk,
                "followup_number": followup.followup_number,
                "branch_from_id": followup.branch_from_id,
            }
        },
    )
    # Send cadence emails immediately; status is updated to sent/failed by mail service.
    try:
        template_context = {
            "instance": instance,
            "user": actor,
            "active_company": company,
            "request": getattr(_thread_local, "request", None),
        }
        HorillaMailManager.send_mail(draft, context=template_context)
        draft.refresh_from_db()
    except Exception:
        logger.exception(
            "Cadence email follow-up send failed: cadence=%s followup=%s record=%s:%s",
            cadence.pk,
            followup.pk,
            instance.__class__.__name__,
            instance.pk,
        )
    return draft


def _create_activity_for_followup(instance, cadence, followup, trigger_time=None):
    if followup.followup_type not in {"task", "call", "email"}:
        return None
    content_type = HorillaContentType.objects.get_for_model(instance.__class__)
    now = trigger_time or timezone.now()
    if followup.followup_type == "email":
        return _create_email_draft_for_followup(
            instance, cadence, followup, content_type
        )
    if followup.followup_type == "task":
        due_dt = now + timedelta(days=(followup.due_after_days or 0))
        subject_text = followup.subject or f"{cadence.name} - Task"
        activity = Activity.objects.create(
            activity_type="task",
            subject=subject_text,
            title=subject_text,
            status=followup.task_status or "not_started",
            task_priority=followup.task_priority or "medium",
            due_datetime=due_dt,
            start_datetime=now,
            owner=followup.task_owner,
            company=getattr(instance, "company", None),
            content_type=content_type,
            object_id=instance.pk,
            additional_info={
                "cadence_runtime": {
                    "cadence_id": cadence.pk,
                    "followup_id": followup.pk,
                    "followup_number": followup.followup_number,
                    "branch_from_id": followup.branch_from_id,
                }
            },
        )
        if followup.task_owner:
            activity.assigned_to.add(followup.task_owner)
        return activity
    start_dt = now + timedelta(days=(followup.call_start_after_days or 0))
    call_text = followup.purpose or f"{cadence.name} - Call"
    return Activity.objects.create(
        activity_type="log_call",
        subject=call_text,
        title=call_text,
        status=followup.call_status or "scheduled",
        call_type=followup.call_type or "outbound",
        call_purpose=followup.purpose,
        start_datetime=start_dt,
        due_datetime=start_dt,
        owner=followup.call_owner,
        company=getattr(instance, "company", None),
        content_type=content_type,
        object_id=instance.pk,
        additional_info={
            "cadence_runtime": {
                "cadence_id": cadence.pk,
                "followup_id": followup.pk,
                "followup_number": followup.followup_number,
                "branch_from_id": followup.branch_from_id,
            }
        },
    )


def _trigger_initial_followups(instance):
    if not instance.pk:
        return []
    content_type = HorillaContentType.objects.get_for_model(instance.__class__)
    cadences = list(
        Cadence.objects.filter(module=content_type, is_active=True)
        .prefetch_related("conditions", "followups")
        .order_by("-created_at")
    )
    existing_followup_ids = _existing_runtime_followup_ids(instance)
    for cadence in cadences:
        if not _evaluate_cadence_conditions(cadence, instance):
            continue
        first_followups = cadence.followups.filter(followup_number=1).order_by(
            "order", "id"
        )
        for followup in first_followups:
            if followup.pk in existing_followup_ids:
                continue
            created_activity = _create_activity_for_followup(
                instance, cadence, followup
            )
            if created_activity:
                existing_followup_ids.add(followup.pk)
    return cadences


def ensure_initial_followups_for_instance(instance):
    """Public helper: create missing FU1 runtime activities for one record."""
    if not instance or not getattr(instance, "pk", None):
        return []
    if not _is_cadence_supported_instance(instance):
        return []
    _dedupe_runtime_activities_for_instance(instance)
    return _trigger_initial_followups(instance)


def _trigger_initial_followups_for_cadence(cadence):
    model = cadence.module.model_class() if cadence.module_id else None
    if not model:
        return
    try:
        records = model.objects.all()
    except Exception:
        return
    for instance in records.iterator():
        try:
            if not _evaluate_cadence_conditions(cadence, instance):
                continue
            existing_followup_ids = _existing_runtime_followup_ids(instance)
            first_followups = cadence.followups.filter(followup_number=1).order_by(
                "order", "id"
            )
            for followup in first_followups:
                if followup.pk in existing_followup_ids:
                    continue
                created_activity = _create_activity_for_followup(
                    instance, cadence, followup
                )
                if created_activity:
                    existing_followup_ids.add(followup.pk)
        except Exception:
            logger.exception(
                "Cadence backfill failed for record %s:%s in cadence %s",
                instance.__class__.__name__,
                getattr(instance, "pk", None),
                cadence.pk,
            )


def _trigger_next_followups_from_activity(activity):
    info = activity.additional_info or {}
    runtime = info.get("cadence_runtime") if isinstance(info, dict) else None
    if not runtime:
        return
    cadence_id = runtime.get("cadence_id")
    source_followup_id = runtime.get("followup_id")
    if not cadence_id or not source_followup_id:
        return
    model = activity.content_type.model_class() if activity.content_type_id else None
    if not model:
        return
    instance = model.objects.filter(pk=activity.object_id).first()
    if not instance:
        return
    cadence = Cadence.objects.filter(pk=cadence_id, is_active=True).first()
    if not cadence:
        return
    if not _evaluate_cadence_conditions(cadence, instance):
        return
    status_key = _activity_status_key(activity)
    if not status_key:
        return
    source_followup = CadenceFollowUp.objects.filter(pk=source_followup_id).first()
    if not source_followup:
        return
    existing_followup_ids = _existing_runtime_followup_ids(instance)
    next_stage = source_followup.followup_number + 1
    next_followups = cadence.followups.filter(
        branch_from_id=source_followup_id,
        followup_number=next_stage,
        previous_status=status_key,
    ).order_by("followup_number", "order", "id")
    for followup in next_followups:
        if followup.pk in existing_followup_ids:
            continue
        created_activity = _create_activity_for_followup(
            instance, cadence, followup, trigger_time=timezone.now()
        )
        if created_activity:
            existing_followup_ids.add(followup.pk)


def _sync_runtime_activities_for_followup(followup):
    """
    Keep existing cadence runtime activities in sync when follow-up config changes.
    Focus on pending activities so completed history is not rewritten.
    """
    qs = Activity.all_objects.filter(
        additional_info__cadence_runtime__followup_id=followup.pk
    ).exclude(status="completed")
    now = timezone.now()
    for activity in qs:
        start_base = activity.start_datetime or activity.created_at or now
        if followup.followup_type == "task" and activity.activity_type == "task":
            subject_text = followup.subject or activity.subject
            activity.subject = subject_text
            activity.title = subject_text
            activity.task_priority = followup.task_priority or activity.task_priority
            if followup.task_owner_id:
                activity.owner_id = followup.task_owner_id
            activity.due_datetime = start_base + timedelta(
                days=(followup.due_after_days or 0)
            )
            activity.save(
                update_fields=[
                    "subject",
                    "title",
                    "task_priority",
                    "owner",
                    "due_datetime",
                    "updated_at",
                    "updated_by",
                ]
            )
            if followup.task_owner_id:
                activity.assigned_to.set([followup.task_owner_id])
        elif followup.followup_type == "call" and activity.activity_type == "log_call":
            call_text = followup.purpose or activity.subject
            activity.subject = call_text
            activity.title = call_text
            activity.call_purpose = followup.purpose
            if followup.call_owner_id:
                activity.owner_id = followup.call_owner_id
            shifted = start_base + timedelta(days=(followup.call_start_after_days or 0))
            activity.start_datetime = shifted
            activity.due_datetime = shifted
            activity.save(
                update_fields=[
                    "subject",
                    "title",
                    "call_purpose",
                    "owner",
                    "start_datetime",
                    "due_datetime",
                    "updated_at",
                    "updated_by",
                ]
            )


@receiver(post_save)
def cadence_apply_on_record_save(sender, instance, **kwargs):
    """On save of any record, trigger cadence FU1 creation if conditions are met and not already created."""
    if _is_migrate_command():
        return
    if sender in {Cadence, Activity}:
        return
    if not _is_cadence_supported_instance(instance):
        return
    try:
        _trigger_initial_followups(instance)
    except Exception:
        logger.exception(
            "Cadence initial trigger failed for %s:%s", sender, instance.pk
        )


@receiver(pre_save, sender=Activity)
def cache_previous_activity_status(sender, instance, **kwargs):
    """Cache the previous status of the activity before saving, so we can detect status changes in post_save."""
    if not instance.pk:
        instance._cadence_previous_status = None
        return
    prev = (
        Activity.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
    )
    instance._cadence_previous_status = prev


@receiver(post_save, sender=Activity)
def cadence_progress_on_activity_status(sender, instance, created, **kwargs):
    """When an activity is saved, if it has cadence runtime info and its status changed, trigger next follow-ups."""
    if _is_migrate_command():
        return
    # Only advance cadence on status changes after creation.
    if created:
        return
    prev_status = getattr(instance, "_cadence_previous_status", None)
    if prev_status == instance.status:
        return
    try:
        _trigger_next_followups_from_activity(instance)
    except Exception:
        logger.exception("Cadence progression failed for activity %s", instance.pk)


@receiver(post_save, sender=Cadence)
def cadence_backfill_existing_records(sender, instance, **kwargs):
    """When cadence is saved/updated, create FU1 runtime activities for matching existing records."""
    if _is_migrate_command() or not instance.is_active:
        return
    transaction.on_commit(lambda: _trigger_initial_followups_for_cadence(instance))


@receiver(post_save, sender=CadenceFollowUp)
def cadence_fu1_backfill_on_followup_save(sender, instance, **kwargs):
    """When FU1 is saved, backfill initial runtime activities for matching existing records."""
    if _is_migrate_command():
        return
    if instance.followup_number != 1 or not instance.cadence_id:
        return
    cadence = instance.cadence
    if not cadence.is_active:
        return
    transaction.on_commit(lambda: _trigger_initial_followups_for_cadence(cadence))
    transaction.on_commit(lambda: _sync_runtime_activities_for_followup(instance))


@receiver(post_save, sender=CadenceFollowUp)
def cadence_runtime_sync_on_followup_update(sender, instance, **kwargs):
    """Sync existing runtime activities whenever a follow-up is updated."""
    if _is_migrate_command():
        return
    try:
        _sync_runtime_activities_for_followup(instance)
    except Exception:
        logger.exception("Cadence runtime sync failed for followup %s", instance.pk)
