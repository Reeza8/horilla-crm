"""
Permission registry for Horilla core models.

This module provides a decorator and a set to manage models that should be
excluded from permission checks.
"""

PERMISSION_EXEMPT_MODELS = {
    "Session",
    "Migration",
    "LogEntry",
    "Group",
    "Permission",
    "ContentType",
    "Attachment",
}


def permission_exempt_model(cls):
    """
    Decorator to mark a model to be excluded from permission checks.

    Usage:
        @exclude_no_perm
        class HorillaModel(models.Model):
            ...
    """
    PERMISSION_EXEMPT_MODELS.add(cls.__name__)
    return cls


def is_permission_exempt(model):
    """
    Return True if `model` must be excluded from permission listings/bulk actions.

    Covers the static exemption set as well as HorillaCoreModel extension
    classes (`_inherit`/`_inherit_model`), which exist only to inject
    fields/methods onto another model and must never be treated as
    permission-able models in their own right — even if the extension
    attribute is misused and Django ends up registering them as real models.
    """
    if model.__name__ in PERMISSION_EXEMPT_MODELS:
        return True
    if getattr(model, "_inherit_model", None):
        return True
    return False
