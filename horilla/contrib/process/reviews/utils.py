"""Utility helpers for matching review conditions and syncing jobs."""

# Standard library imports
from decimal import Decimal

# Third-party imports (Django)
from django.utils.dateparse import parse_date, parse_datetime

# First party imports (Horilla)
from horilla.auth.models import User
from horilla.contrib.core.models import HorillaContentType
from horilla.db import models as db_models
from horilla.urls import reverse_lazy
from horilla.utils.translation import gettext_lazy as _

# Local imports
from .models import ReviewJob, ReviewProcess


def _send_pending_review_notification(job, record):
    """Send a notification to the assigned approver for a newly created review job."""
    try:
        from horilla.contrib.notifications.methods import create_notification
    except Exception:
        return
    try:
        assignee = job.assigned_to
        if not getattr(assignee, "pk", None):
            return
        record_label = str(record) if record else "-"
        process_label = str(job.reviews)
        redirect_url = reverse_lazy("reviews:review_job_view")
        create_notification(
            user=assignee,
            message=_(
                "You have a pending review request for %(record)s in %(process)s."
            )
            % {"record": record_label, "process": process_label},
            sender=None,
            instance=record,
            url=redirect_url,
        )
    except Exception:
        pass


def _compare_date_operator(operator, raw_value, value, parser):
    if operator == "isnull":
        return raw_value is None
    if operator == "isnotnull":
        return raw_value is not None
    parsed = parser(value)
    if parsed is None or raw_value is None:
        return str(raw_value) == str(value) if operator == "exact" else False
    if operator == "exact":
        return raw_value == parsed
    if operator == "gt":
        return raw_value > parsed
    return raw_value < parsed


def _compare_numeric_operator(operator, left, right):
    try:
        left_dec = Decimal(left)
        right_dec = Decimal(right)
    except Exception:
        return False
    if operator == "gt":
        return left_dec > right_dec
    if operator == "gte":
        return left_dec >= right_dec
    if operator == "lt":
        return left_dec < right_dec
    return left_dec <= right_dec


def _compare_text_operator(operator, left, right):
    if operator == "exact":
        return left == right
    if operator == "ne":
        return left != right
    if operator == "icontains":
        return right.lower() in left.lower()
    if operator == "not_contains":
        return right.lower() not in left.lower()
    if operator == "istartswith":
        return left.lower().startswith(right.lower())
    return left.lower().endswith(right.lower())


def _compare_string_operator(operator, left, right):
    if operator in (
        "exact",
        "ne",
        "icontains",
        "not_contains",
        "istartswith",
        "iendswith",
    ):
        result = _compare_text_operator(operator, left, right)
    elif operator in ("gt", "gte", "lt", "lte"):
        result = _compare_numeric_operator(operator, left, right)
    elif operator == "isnull":
        result = not left.strip()
    elif operator == "isnotnull":
        result = bool(left.strip())
    else:
        result = False
    return result


def evaluate_condition(instance, condition):
    """Evaluate a single condition against a record instance."""
    field_name = getattr(condition, "field", "")
    operator = (getattr(condition, "operator", "") or "").strip()
    value = getattr(condition, "value", "")
    try:
        field = instance._meta.get_field(field_name)
        raw_value = getattr(instance, field_name, None)
    except Exception:
        return False

    if isinstance(field, db_models.ForeignKey):
        raw_value = getattr(instance, f"{field_name}_id", raw_value)

    field_type = getattr(field, "get_internal_type", lambda: "")()
    is_date = field_type == "DateField"
    is_datetime = field_type == "DateTimeField"

    if (is_date or is_datetime) and operator in (
        "isnull",
        "isnotnull",
        "exact",
        "gt",
        "lt",
    ):
        result = _compare_date_operator(
            operator, raw_value, value, parse_date if is_date else parse_datetime
        )
    else:
        left = "" if raw_value is None else str(raw_value)
        right = "" if value is None else str(value)
        result = _compare_string_operator(operator, left, right)
    return result


def evaluate_conditions(instance, conditions):
    """Evaluate a list of conditions against a record instance, respecting logical operators."""
    conditions = list(conditions)
    if not conditions:
        return True
    result = None
    for cond in conditions:
        current = evaluate_condition(instance, cond)
        if result is None:
            result = current
            continue
        result = (
            (result or current)
            if getattr(cond, "logical_operator", "and") == "or"
            else (result and current)
        )
    return bool(result)


def _get_approvers(rule):
    if not rule:
        return []
    if rule.approver_type == "role":
        return list(User.objects.filter(role__in=rule.approver_roles.all()).distinct())
    return list(rule.approver_users.all())


def _get_snapshot(record, review_fields):
    snapshot = {}
    for field_name in review_fields or []:
        value = getattr(record, field_name, None)
        snapshot[field_name] = None if value is None else str(value)
    return snapshot


def sync_approval_for_record_if_available(record):
    """
    Trigger approval resync if approvals app is installed.

    Uses created=None to run an explicit reconciliation pass (both create/edit
    trigger types), while approval-side logic suppresses instances when review
    is still pending.
    """
    if not record:
        return
    try:
        from horilla.contrib.process.approvals.utils import (
            sync_approval_instances_for_record,
        )
    except Exception:
        return
    try:
        sync_approval_instances_for_record(record, created=None)
    except Exception:
        # Review flow should stay resilient even if approval sync fails.
        pass


def record_has_pending_review_jobs(record):
    """Return True when the record has any active pending review jobs."""
    if not record:
        return False
    content_type = HorillaContentType.objects.get_for_model(record.__class__)
    return ReviewJob.all_objects.filter(
        content_type=content_type,
        object_id=record.pk,
        status=ReviewJob.STATUS_PENDING,
        is_active=True,
    ).exists()


def refresh_review_jobs_for_record(record):
    """
    Create/refresh pending review jobs when a record satisfies conditions.

    Does not call approval sync; safe to invoke from the approvals app so review
    runs before approval matching regardless of INSTALLED_APPS order or which app
    is enabled.
    """
    if not record:
        return
    content_type = HorillaContentType.objects.get_for_model(record.__class__)
    processes = ReviewProcess.objects.filter(model=content_type, is_active=True)
    record_company_id = getattr(record, "company_id", None)

    for process in processes:
        entry_ok = evaluate_conditions(
            record, process.conditions.all().order_by("order", "created_at")
        )
        rules = list(process.rules.all())
        if not rules:
            continue

        snapshot = _get_snapshot(record, process.review_fields)

        for rule in rules:
            rule_ok = evaluate_conditions(
                record, rule.conditions.all().order_by("order", "created_at")
            )
            is_match = entry_ok and rule_ok
            approvers = _get_approvers(rule)
            approver_ids = {u.pk for u in approvers}

            pending_qs = ReviewJob.all_objects.filter(
                reviews=process,
                review_rule=rule,
                content_type=content_type,
                object_id=record.pk,
                status=ReviewJob.STATUS_PENDING,
            )

            if not is_match:
                pending_qs.delete()
                continue

            pending_qs.exclude(assigned_to_id__in=approver_ids).delete()

            for user in approvers:
                job, created = ReviewJob.all_objects.get_or_create(
                    reviews=process,
                    review_rule=rule,
                    content_type=content_type,
                    object_id=record.pk,
                    assigned_to=user,
                    defaults={
                        "review_fields_snapshot": snapshot,
                        "company_id": record_company_id,
                    },
                )
                if created:
                    _notify_approver_pending_review(job)
                if not created and job.status == ReviewJob.STATUS_PENDING:
                    changed = False
                    job.review_fields_snapshot = snapshot
                    changed = True
                    if record_company_id and job.company_id != record_company_id:
                        job.company_id = record_company_id
                        changed = True
                    if changed:
                        job.save(
                            update_fields=[
                                "review_fields_snapshot",
                                "company",
                                "updated_at",
                            ]
                        )


def _notify_approver_pending_review(job):
    """
    Send a notification to the assigned approver when a new review job is created.
    Only fires when notify_on_submission is enabled on the review process.
    """
    if not job:
        return
    try:
        from horilla.contrib.notifications.methods import create_notification
    except Exception:
        return

    process = job.reviews
    if not getattr(process, "notify_on_submission", False):
        return

    approver = job.assigned_to
    if not getattr(approver, "pk", None):
        return

    record = job.content_object
    redirect_url = reverse_lazy("reviews:review_job_view")
    try:
        create_notification(
            user=approver,
            message=_(
                "You have a pending review request for %(record)s in %(process)s."
            )
            % {
                "record": str(record) if record else "-",
                "process": str(process),
            },
            instance=record,
            url=redirect_url,
        )
    except Exception:
        pass


def sync_jobs_for_record(record):
    """
    Create/refresh pending review jobs (used by review post_save).

    Approval resync is handled by approvals (which calls
    refresh_review_jobs_for_record before matching rules) and by
    sync_approval_for_record_if_available when review completes in the UI.
    """
    refresh_review_jobs_for_record(record)
