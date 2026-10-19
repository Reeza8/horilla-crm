"""
Who may see which records on the phone.

The rules are the desktop ones: a list shows what ``HorillaListView`` shows,
and a record opens when ``check_record_access`` allows it.
"""

# Standard library imports
from functools import reduce
from operator import or_

# First party imports (Horilla)
from horilla.contrib.core.utils import get_allowed_user_ids
from horilla.contrib.generics.views.details import check_record_access
from horilla.contrib.generics.views.helpers.queryset_utils import (
    get_granted_access_filter,
)
from horilla.db.models import Q


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
