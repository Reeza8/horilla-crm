"""
Read a record's field layout and status choices from its desktop views.

The phone shows what the desktop detail page shows: the user's own
``DetailFieldVisibility`` choice (or the desktop view's defaults), with field
permissions and custom fields applied by the same code. The desktop views key
that choice by their own URL, so they are run against a copy of the request
that carries the desktop detail path instead of the phone's.
"""

# Standard library imports
import copy
import logging

# First party imports (Horilla)
from horilla.extension.detail.resolve import resolve_detail_view_class
from horilla.extension.detail_section.resolve import resolve_detail_section_view_class
from horilla.urls import Resolver404, resolve
from horilla.web import QueryDict
from horilla.contrib.core.utils import get_field_permissions_for_model
from horilla.contrib.generics.views.detail_tabs import HorillaDetailSectionView
from horilla.contrib.generics.views.details import HorillaDetailView

logger = logging.getLogger(__name__)


def get_desktop_detail_path(obj):
    """Return the desktop detail page path of ``obj``, or "" when it has none."""
    getter = getattr(obj, "get_detail_url", None)
    if not callable(getter):
        return ""
    try:
        return str(getter() or "")
    except Exception:  # pylint: disable=broad-except
        logger.exception("get_detail_url() failed for %r", obj)
        return ""


def _desktop_request(request, path, params=None):
    """Shallow copy of ``request`` as a GET for ``path`` with ``params``."""
    clone = copy.copy(request)
    clone.method = "GET"
    clone.path = clone.path_info = path
    query = QueryDict(mutable=True)
    for key, value in (params or {}).items():
        if value:
            query[key] = value
    clone.GET = query
    return clone


def _hidden_field_names(user, model):
    """Names of the fields ``user`` may not see on ``model``."""
    permissions = get_field_permissions_for_model(user, model)
    return {name for name, permission in permissions.items() if permission == "hidden"}


class DesktopLayout:
    """
    Field layout and status choices of one record, as its desktop pages show them.

    ``key_fields`` and ``all_fields`` are ``(label, field_name)`` lists;
    ``field_name`` may be a custom field (``cf_<id>``).
    """

    def __init__(self, request, obj, config):
        self.request = request
        self.obj = obj
        self.config = config
        self.model = obj.__class__
        self.detail_path = get_desktop_detail_path(obj)
        self.detail_view = self._build_detail_view()
        self.visibility_url_name = self._visibility_url_name()
        self._hidden = _hidden_field_names(request.user, self.model)

    # ----- desktop views -------------------------------------------------

    def _build_detail_view(self):
        """The model's (extension-composed) desktop detail view, set up for ``obj``."""
        view_class = HorillaDetailView._view_registry.get(self.model)
        if view_class is None or not self.detail_path:
            return None
        view = resolve_detail_view_class(view_class)()
        view.setup(_desktop_request(self.request, self.detail_path), pk=self.obj.pk)
        view.model = self.model
        view.object = self.obj
        return view

    def _visibility_url_name(self):
        """``DetailFieldVisibility.url_name`` the desktop page saves the user's choice under."""
        if not self.detail_path:
            return ""
        try:
            url_name = resolve(self.detail_path).url_name or ""
        except Resolver404:
            return ""
        if self.detail_view is not None:
            scope = self.detail_view.get_detail_field_visibility_scope(self.obj)
            if scope:
                url_name = f"{url_name}:{scope}"
        return url_name

    def _build_section_view(self):
        """The model's desktop Details tab view, set up for ``obj``."""
        view_class = HorillaDetailSectionView._view_registry.get(
            self.model, HorillaDetailSectionView
        )
        view = resolve_detail_section_view_class(view_class)()
        params = {"detail_url_name": self.visibility_url_name}
        if self.detail_view is not None:
            params["pipeline_field"] = self.detail_view.pipeline_field or ""
        view.setup(
            _desktop_request(
                self.request, self.detail_path or self.request.path, params
            ),
            pk=self.obj.pk,
        )
        view.model = self.model
        view.object = self.obj
        return view

    # ----- fields --------------------------------------------------------

    def _visible(self, fields, skip=()):
        """Drop hidden fields, ``skip`` names and duplicates from ``fields``."""
        result = []
        seen = set(skip)
        for label, name in fields:
            if name in self._hidden or name in seen:
                continue
            seen.add(name)
            result.append((label, name))
        return result

    def _normalize(self, names):
        """``(label, name)`` pairs for model field ``names``."""
        pairs = []
        for name in names:
            try:
                pairs.append((self.model._meta.get_field(name).verbose_name, name))
            except Exception:  # pylint: disable=broad-except
                continue
        return pairs

    def get_key_fields(self):
        """
        Fields of the record header: the desktop header grid (``get_body()``
        minus its first entry, which is the title), or ``header_fields`` from
        ``mobile.py`` for a model without a desktop detail view.
        """
        skip = {self.config.title_field, self.config.status_field}
        if self.detail_view is not None:
            body = self.detail_view.get_body()
            return self._visible(body[1:], skip=skip)
        return self._visible(self._normalize(self.config.header_fields), skip=skip)

    def get_all_fields(self):
        """Fields of the desktop Details tab (the user's choice or its defaults)."""
        view = self._build_section_view()
        context = view.get_context_data(object=self.obj)
        return self._visible(context.get("body") or [])

    def get_stage_field(self):
        """
        ``(label, name)`` of the field the desktop page shows as its stage bar
        rather than in its field lists, or None. For pages without a status
        control on the phone, so the value still shows.
        """
        view = self.detail_view
        name = getattr(view, "pipeline_field", "") if view is not None else ""
        if not name or name in self._hidden:
            return None
        return (self.model._meta.get_field(name).verbose_name, name)

    # ----- status ---------------------------------------------------------

    def get_status(self):
        """
        Status choices when the desktop detail page shows ``status_field`` as
        its stage bar, else None. Returns::

            {"field": name, "label": verbose name, "can_update": bool,
             "choices": [{"label", "value", "is_current", "blocked"}, ...]}

        ``blocked`` marks a stage the desktop handles with its own action
        (e.g. converting a lead); the phone leaves that to the full version.
        """
        view = self.detail_view
        field = self.config.status_field
        if view is None or not field or view.pipeline_field != field:
            return None
        if field in self._hidden:
            return None
        final_action = getattr(view, "final_stage_action", None)
        if callable(final_action):
            final_action = final_action()
        choices = []
        for choice in view.get_pipeline_choices() or []:
            choices.append(
                {
                    "label": choice["label"],
                    "value": choice["value"],
                    "is_current": choice["is_current"],
                    "blocked": bool(choice.get("is_final") and final_action),
                }
            )
        return {
            "field": field,
            "label": self.model._meta.get_field(field).verbose_name,
            "can_update": view.check_update_permission(),
            "choices": choices,
        }
