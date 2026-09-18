"""
Add the Cadence tab to Horilla generic detail views through ViewExtension
(_inherit_view), targeting the shared ``HorillaDetailTabView`` base class.

``HorillaDetailTabView`` is a shared base class every concrete detail-tab
view across every app inherits — there is no single concrete class to name.
``resolve_view_class()`` (the same resolver every ``_inherit_view``
registration goes through at ``as_view()`` time) checks an exact match for
the concrete class first, then falls back to checking each base class in
the concrete class's MRO, so a registration on ``HorillaDetailTabView``
here is picked up by every concrete detail-tab view automatically —
present and future, across every app. See
``horilla/extension/view/resolve.py``'s ``_resolve_via_base_class`` and
``docs/horilla/extension/inherit.md``'s "Targeting a shared base class".

CRM apps don't need to reference the "cadences" URL namespace in their own
``urls`` dicts either — they only need to call ``register_cadence_tab(...)``
from their own ``registration.py``; this extension finds the right URL for
a model at render time via ``get_cadence_tab_url_name``.
"""

from horilla.extension.view import ViewExtension
from horilla.urls import reverse_lazy
from horilla.utils.translation import gettext_lazy as _


def _has_active_cadences_for_model(model):
    """Return True if any active cadences exist for the given model class."""
    try:
        from horilla.contrib.cadences.models import Cadence
        from horilla.contrib.core.models import HorillaContentType

        content_type = HorillaContentType.objects.get_for_model(model)
        return Cadence.objects.filter(module=content_type, is_active=True).exists()
    except Exception:
        return False


def _get_cadence_tab_url(model):
    """Return the reversed cadence tab URL name for ``model``, or None.

    Only returns a URL name when the model has been registered via
    ``register_cadence_tab`` AND has at least one active cadence — this
    keeps the tab hidden on unrelated/inactive models.
    """
    from .registration import get_cadence_tab_url_name

    app_label = model._meta.app_label
    model_name = model._meta.model_name
    url_name = get_cadence_tab_url_name(app_label, model_name)
    if not url_name:
        return None
    if not _has_active_cadences_for_model(model):
        return None
    return url_name


class CadenceTabExtension(ViewExtension):
    """Add the Cadence tab to every detail view's tab list, when applicable."""

    _inherit_view = "horilla.contrib.generics.views.detail_tabs.HorillaDetailTabView"

    def _prepare_detail_tabs(self):
        # Call the real chain first; this sets self.object_id and builds
        # self.tabs with all standard tabs.
        super()._prepare_detail_tabs()

        if not getattr(self, "object_id", None):
            return

        model = getattr(self, "model", None)
        if model is None:
            return

        try:
            url_name = _get_cadence_tab_url(model)
            if not url_name:
                return

            if not hasattr(self, "tabs"):
                self.tabs = []

            if any(tab.get("id") == "cadence" for tab in self.tabs):
                return

            tab_data = {
                "title": _("Cadence"),
                "url": reverse_lazy(url_name, kwargs={"pk": self.object_id}),
                "target": "tab-cadence-content",
                "id": "cadence",
            }

            # Keep the tab next to Activity when present, to preserve the
            # familiar tab order; otherwise just append it.
            activity_index = next(
                (i for i, t in enumerate(self.tabs) if t.get("id") == "activity"),
                None,
            )
            if activity_index is not None:
                self.tabs.insert(activity_index + 1, tab_data)
            else:
                self.tabs.append(tab_data)
        except Exception as e:
            import logging

            logging.getLogger(__name__).debug(
                "Could not add Cadence tab: %s", e, exc_info=True
            )
