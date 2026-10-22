"""
Who may see which records on the phone.

The rules are the desktop ones: a list shows what ``HorillaListView`` shows,
and a record opens when ``check_record_access`` allows it.
"""

# Standard library imports
from functools import reduce
from operator import or_

# First party imports (Horilla)
from horilla.db.models import Q
from horilla.contrib.core.utils import get_allowed_user_ids
from horilla.contrib.generics.views.details import (
    check_record_access,
    check_record_change_access,
)
from horilla.contrib.generics.views.helpers.queryset_utils import (
    get_granted_access_filter,
)


def can_list_model(user, model):
    """True when ``user`` may see at least their own records of ``model``."""
    app_label = model._meta.app_label
    model_name = model._meta.model_name
    return user.has_perm(f"{app_label}.view_{model_name}") or user.has_perm(
        f"{app_label}.view_own_{model_name}"
    )


def scope_queryset(user, queryset):
    """
    Limit ``queryset`` to the rows ``user`` may view.

    Same rule as ``HorillaListView.get_queryset`` (owner filtration): the view
    permission shows everything; ``view_own`` shows rows whose ``OWNER_FIELDS``
    point at the user or a subordinate, plus rows the model grants through
    ``granted_access_filter``; anything else shows nothing.
    """
    model = queryset.model
    app_label = model._meta.app_label
    model_name = model._meta.model_name
    if user.has_perm(f"{app_label}.view_{model_name}"):
        return queryset
    if not user.has_perm(f"{app_label}.view_own_{model_name}"):
        return queryset.none()

    query = None
    owner_fields = getattr(model, "OWNER_FIELDS", None)
    if owner_fields:
        allowed_user_ids = list(get_allowed_user_ids(user))
        query = reduce(
            or_,
            (Q(**{f"{field}__in": allowed_user_ids}) for field in owner_fields),
        )
    granted = get_granted_access_filter(model, user, "view")
    if granted is not None:
        query = granted if query is None else query | granted
    if query is None:
        return queryset.none()
    return queryset.filter(query).distinct()


def can_open(user, obj):
    """True when ``user`` may open ``obj`` (the desktop detail page rule)."""
    return check_record_access(user, obj)


def can_log_activity(user, obj):
    """
    True when ``user`` may add activities and notes to ``obj``. The desktop
    activity tab shows its add buttons on the same condition: change access
    to the record, which also rules out locked records.
    """
    return check_record_change_access(user, obj)


def can_edit_activity(user, activity):
    """
    True when ``user`` may edit ``activity``: change access to the activity
    itself (``change_activity``, or ``change_own_activity`` on their own),
    not on a locked one.
    """
    return check_record_change_access(user, activity)


def can_edit_note(user, note, record):
    """
    True when ``user`` may edit ``note`` on ``record``, the rule of the
    desktop note details: change access to the record, and without the
    model's full change permission only notes added by the user or a
    subordinate.
    """
    if not check_record_change_access(user, record):
        return False
    app_label = record._meta.app_label
    model_name = record._meta.model_name
    if user.is_superuser or user.has_perm(f"{app_label}.change_{model_name}"):
        return True
    return note.created_by_id is None or note.created_by_id in get_allowed_user_ids(
        user
    )


def can_add_activity(user):
    """
    True when ``user`` may add activities that belong to no record (from the
    Agenda): the desktop activity forms' rule, ``add_activity`` or
    ``add_own_activity``.
    """
    return (
        user.is_superuser
        or user.has_perm("activity.add_activity")
        or user.has_perm("activity.add_own_activity")
    )
