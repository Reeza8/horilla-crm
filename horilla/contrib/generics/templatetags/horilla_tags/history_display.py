"""Template filters for history/audit log display (handles M2M and normal changes)."""

# Third-party imports (Django)
from auditlog.models import LogEntry

# First party imports (Horilla)
from horilla.core.exceptions import FieldDoesNotExist
from horilla.utils.translation import gettext_lazy as _

# Local imports
from ._registry import register


def _is_redundant_history_entry(entry, same_group_entries):
    """
    Return True if this entry should be hidden: any UPDATE for an object that
    has a CREATE in the same group is collapsed (one create + many updates = one entry).
    Works for any model; no model names.
    """
    try:
        if getattr(entry, "action", None) != LogEntry.Action.UPDATE:
            return False
        ct = getattr(entry, "content_type", None)
        if ct is None:
            return False
        entry_pk = str(
            getattr(entry, "object_pk", None) or getattr(entry, "object_id", "")
        )
        for other in same_group_entries:
            if other is entry:
                continue
            if getattr(other, "action", None) != LogEntry.Action.CREATE:
                continue
            if getattr(other, "content_type", None) != ct:
                continue
            other_pk = str(
                getattr(other, "object_pk", None) or getattr(other, "object_id", "")
            )
            if other_pk == entry_pk:
                return True
    except Exception:
        pass
    return False


@register.filter
def collapse_redundant_history(entries):
    """
    Collapse redundant updates: for any object, if the same group has a CREATE,
    hide that object's UPDATE entries so one create+updates shows as one entry.
    Use in template: {% for entry in entries|collapse_redundant_history %}
    """
    if not entries:
        return entries
    return [e for e in entries if not _is_redundant_history_entry(e, entries)]


# Map Activity.activity_type (db value) to history label
ACTIVITY_TYPE_ADDED_LABELS = {
    "task": _("Task added"),
    "event": _("Event added"),
    "meeting": _("Meeting added"),
    "log_call": _("Call added"),
}

# Map mail_status (or similar) to history label for create entries (any model with mail_status)
MAIL_STATUS_CREATE_LABELS = {
    "sent": _("Email sent"),
    "draft": _("Draft saved"),
    "scheduled": _("Scheduled mail"),
    "failed": _("Mail failed"),
}


@register.filter
def history_changes_display(entry):
    """
    Return a display-safe changes dict for a log entry.

    Auditlog stores M2M changes as {"type": "m2m", "operation": "add", "objects": [...]}.
    The default changes_display_dict iterates over that dict and shows keys "type" and
    "operation" as if they were old/new values. This filter fixes that by replacing
    such entries with human-readable text (e.g. "Added: Adam Lui").
    """
    if entry is None:
        return {}
    display_dict = getattr(entry, "changes_display_dict", None) or {}
    changes_dict = getattr(entry, "changes_dict", None) or {}
    if not changes_dict:
        return display_dict

    model = None
    try:
        if hasattr(entry, "content_type") and entry.content_type:
            model = entry.content_type.model_class()
    except Exception:
        pass

    result = dict(display_dict)

    for field_name, value in changes_dict.items():
        if not isinstance(value, dict) or value.get("type") != "m2m":
            continue
        verbose_name = field_name.replace("_", " ").title()
        if model:
            try:
                field = model._meta.get_field(field_name)
                verbose_name = getattr(field, "verbose_name", verbose_name)
                if hasattr(verbose_name, "_proxy____args"):
                    verbose_name = str(verbose_name)
            except FieldDoesNotExist:
                pass
        operation = value.get("operation", "")
        objects = value.get("objects") or []
        objects_str = ", ".join(str(o) for o in objects)
        if operation == "add":
            label = "Added"
        elif operation == "delete":
            label = "Removed"
        else:
            label = str(operation)
        display = f"{label}: {objects_str}" if objects_str else label
        result[verbose_name] = ["--", display]

    # Remove bogus entries that are M2M keys shown as "type" -> "operation"
    for key in list(result):
        val = result[key]
        if isinstance(val, (list, tuple)) and len(val) >= 2:
            if val[0] == "type" and val[1] == "operation":
                del result[key]

    return result


def _get_activity_type_from_entry(entry):
    """Return activity_type string (task, event, meeting, log_call) for an Activity log entry, or None."""
    if entry is None:
        return None
    try:
        if getattr(entry, "content_type", None) is None:
            return None
        model = entry.content_type.model_class()
        if model is None or model.__name__ != "Activity":
            return None
    except Exception:
        return None
    # Prefer serialized_data from auditlog (set on create)
    serialized = getattr(entry, "serialized_data", None)
    if isinstance(serialized, dict):
        fields = serialized.get("fields") or {}
        at = fields.get("activity_type")
        if at in ACTIVITY_TYPE_ADDED_LABELS:
            return at
    # Fallback: load the Activity by object_pk
    try:
        object_pk = getattr(entry, "object_pk", None) or getattr(
            entry, "object_id", None
        )
        if object_pk is not None:
            obj = (
                model.objects.filter(pk=object_pk)
                .values_list("activity_type", flat=True)
                .first()
            )
            if obj and obj in ACTIVITY_TYPE_ADDED_LABELS:
                return obj
    except Exception:
        pass
    return None


def _get_activity_from_entry(entry):
    """Return the Activity instance for an Activity log entry, or None."""
    if entry is None:
        return None
    try:
        if getattr(entry, "content_type", None) is None:
            return None
        model = entry.content_type.model_class()
        if model is None or model.__name__ != "Activity":
            return None
        object_pk = getattr(entry, "object_pk", None) or getattr(
            entry, "object_id", None
        )
        if object_pk is None:
            return None
        return model.objects.filter(pk=object_pk).first()
    except Exception:
        return None


def _get_mail_create_label(entry):
    """Return a label for a CREATE entry whose model has mail_status (e.g. Email sent, Draft saved). Generic; no model name."""
    if entry is None:
        return ""
    try:
        if getattr(entry, "action", None) != LogEntry.Action.CREATE:
            return ""
    except Exception:
        return ""
    try:
        ct = getattr(entry, "content_type", None)
        if ct is None:
            return ""
        model = ct.model_class()
        if model is None:
            return ""
        if not hasattr(model, "_meta") or "mail_status" not in [
            f.name for f in model._meta.get_fields()
        ]:
            return ""
        object_pk = getattr(entry, "object_pk", None) or getattr(
            entry, "object_id", None
        )
        if object_pk is None:
            return ""
        obj = (
            model.objects.filter(pk=object_pk)
            .values_list("mail_status", flat=True)
            .first()
        )
        if obj and obj in MAIL_STATUS_CREATE_LABELS:
            return str(MAIL_STATUS_CREATE_LABELS.get(obj, ""))
    except Exception:
        pass
    return ""


@register.filter
def mail_create_display(entry):
    """
    For a CREATE log entry whose model has mail_status, return "Email sent", "Draft saved",
    "Scheduled mail", or "Mail failed" so history distinguishes sent/draft/scheduled. Generic.
    """
    return _get_mail_create_label(entry)


@register.filter
def is_error_entry(entry):
    """Return True if this history entry represents an error/failure (delete action or failed mail)."""
    if entry is None:
        return False
    action = getattr(entry, "action", None)
    if action == LogEntry.Action.DELETE:
        return True
    if action == LogEntry.Action.CREATE:
        failed_label = str(MAIL_STATUS_CREATE_LABELS.get("failed", ""))
        if failed_label and _get_mail_create_label(entry) == failed_label:
            return True
    return False


@register.filter
def activity_create_display(entry):
    """
    For an Activity CREATE log entry, return a phrase like "Task added", "Event added",
    "Meeting added", "Call added". Returns empty string for non-Activity or non-create entries.
    """
    if entry is None:
        return ""
    try:
        if getattr(entry, "action", None) != LogEntry.Action.CREATE:
            return ""
    except Exception:
        return ""
    activity_type = _get_activity_type_from_entry(entry)
    if activity_type is None:
        return ""
    return str(ACTIVITY_TYPE_ADDED_LABELS.get(activity_type, ""))


@register.filter
def activity_create_details(entry):
    """
    For an Activity CREATE log entry, return a dict with type_label and status for history display.
    Returns None for non-activity create.
    """
    if entry is None:
        return None
    try:
        if getattr(entry, "action", None) != LogEntry.Action.CREATE:
            return None
    except Exception:
        return None
    activity = _get_activity_from_entry(entry)
    if activity is None:
        return None
    activity_type = getattr(activity, "activity_type", None)
    if activity_type not in ACTIVITY_TYPE_ADDED_LABELS:
        return None
    type_label = str(ACTIVITY_TYPE_ADDED_LABELS.get(activity_type, ""))
    status_raw = getattr(activity, "status", None)
    status_display = (
        dict(activity.STATUS_CHOICES).get(status_raw, status_raw or "--")
        if hasattr(activity, "STATUS_CHOICES")
        else (status_raw or "--")
    )
    if hasattr(status_display, "_proxy____args"):
        status_display = str(status_display)
    return {
        "type_label": type_label,
        "status": status_display,
    }
