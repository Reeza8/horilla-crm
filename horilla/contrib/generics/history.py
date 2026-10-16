"""
Generic helpers for showing one record's related rows (activities, notes,
attachments, emails) on another record, and for locking records.

Nothing here knows about any app's models. A model opts in by defining:

* ``get_history_sources()`` returning the records whose related rows should
  also be listed on this record, and/or
* ``is_record_locked`` (property or attribute) that is truthy while the record
  must be read-only.
"""

# Standard library imports
from urllib.parse import urlencode

# Third-party imports (Django)
from django.template.loader import render_to_string

# First party imports (Horilla)
from horilla.contrib.core.models import HorillaContentType
from horilla.contrib.utils.middlewares import get_current_request
from horilla.db.models import Q
from horilla.utils.translation import gettext_lazy as _


def is_record_locked(obj):
    """Return True when ``obj`` declares itself read-only."""
    return bool(obj is not None and getattr(obj, "is_record_locked", False))


def history_sources(obj, user):
    """Records whose history also shows on ``obj`` and that ``user`` may view."""
    getter = getattr(obj, "get_history_sources", None)
    if not getter:
        return []

    from horilla.contrib.generics.views.details import check_record_access

    return [src for src in getter() if check_record_access(user, src)]


def history_q(obj, user):
    """Q matching rows attached to ``obj`` or to any of its history sources."""
    get_ct = HorillaContentType.objects.get_for_model
    query = Q(content_type=get_ct(obj), object_id=obj.pk)
    for src in history_sources(obj, user):
        query |= Q(content_type=get_ct(src), object_id=src.pk)
    return query


def remember_history_parent(request, obj):
    """Store the record a list is rendered for, so rows can label their source."""
    request._history_parent = (HorillaContentType.objects.get_for_model(obj).pk, obj.pk)


def history_parent(request=None):
    """Return ``(content_type_id, object_id)`` stored by ``remember_history_parent``."""
    request = request or get_current_request()
    return getattr(request, "_history_parent", None)


def is_foreign_row(row, parent=None):
    """True when ``row`` belongs to a history source, not to the listed record."""
    parent = parent or history_parent()
    if not parent:
        return False
    return (row.content_type_id, row.object_id) != tuple(parent)


def parent_key(obj):
    """``(content_type_id, object_id)`` identifying ``obj`` for row comparisons."""
    return (HorillaContentType.objects.get_for_model(obj).pk, obj.pk)


def guard_foreign_row_action(action, parent_obj=None):
    """
    Disable (not hide) a list action on rows that come from a history source,
    and on every row when the listed record is itself locked.
    """
    inner = action.get("disabled_if")
    parent = parent_key(parent_obj) if parent_obj is not None else None
    locked = is_record_locked(parent_obj)

    def disabled(row):
        return locked or is_foreign_row(row, parent) or bool(inner and inner(row))

    return {
        **action,
        "disabled_if": disabled,
        "disabled_title": action.get("disabled_title", _("Read-only")),
    }


def history_source_pill(row):
    """
    "Related To" cell: "Self" for the listed record's own rows, otherwise a pill
    naming the record the row comes from, linked to it (with the listed record as
    the breadcrumb referrer) when the viewer may open it.
    """
    related = getattr(row, "related_object", None) or getattr(row, "related_to", None)
    if related is None:
        return ""
    verbose = related._meta.verbose_name
    if not is_foreign_row(row):
        return render_to_string(
            "history_source_pill.html", {"is_self": True, "text": _("Self")}
        )
    context = {
        "text": "%s: %s" % (verbose, related),
        "title": "%s %s: %s" % (_("From"), verbose, related),
        "initial": str(verbose)[:1].upper(),
        "url": _viewable_detail_url(related),
    }
    return render_to_string("history_source_pill.html", context)


def _history_parent_model_and_obj():
    parent = history_parent()
    if not parent:
        return None, None
    model = HorillaContentType.objects.get(pk=parent[0]).model_class()
    return model, model.objects.filter(pk=parent[1]).first()


def _viewable_detail_url(related):
    """
    Detail URL of ``related`` (opened in its own side-menu section) if the viewer
    may open it, carrying the listed record as the breadcrumb referrer.
    """
    request = get_current_request()
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return ""
    if not callable(getattr(related, "get_detail_url", None)):
        return ""

    from horilla.contrib.generics.views.details import check_record_access
    from horilla.contrib.utils.methods import get_section_info_for_model
    from horilla.urls import resolve

    if not check_record_access(user, related):
        return ""
    params = {}
    section = get_section_info_for_model(related.__class__).get("section")
    if section:
        params["section"] = section
    _, parent_obj = _history_parent_model_and_obj()
    if parent_obj is not None:
        params.update(
            referrer_app=parent_obj._meta.app_label,
            referrer_model=parent_obj._meta.model_name,
            referrer_id=parent_obj.pk,
        )
        if callable(getattr(parent_obj, "get_detail_url", None)):
            try:
                params["referrer_url"] = resolve(
                    str(parent_obj.get_detail_url())
                ).url_name
            except Exception:
                pass
    url = str(related.get_detail_url())
    return url + ("&" if "?" in url else "?") + urlencode(params)
