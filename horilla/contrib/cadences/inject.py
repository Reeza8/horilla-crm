"""Runtime injection that adds the Cadence tab to Horilla generic detail views.

This mirrors the extension pattern used by `horilla.contrib.duplicates`
(`inject_duplicate_tab`): the cadences app wraps
`HorillaDetailTabView._prepare_detail_tabs` and appends its own tab when
applicable, instead of the generics app hardcoding any knowledge of
cadences. CRM apps don't need to reference the "cadences" URL namespace in
their own `urls` dicts either — they only need to call
`register_cadence_tab(...)` from their own `registration.py`.
"""

# Standard library imports
import logging
from functools import wraps

from horilla.contrib.generics.views import HorillaDetailTabView

# First-party (Horilla)
from horilla.urls import reverse_lazy
from horilla.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


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


def create_prepare_tabs_with_cadence_tab(original_prepare_tabs):
    """Create a wrapped ``_prepare_detail_tabs`` that appends the Cadence tab."""

    @wraps(original_prepare_tabs)
    def _prepare_detail_tabs_with_cadence_tab(self):
        # Call original _prepare_detail_tabs first; this sets self.object_id
        # and builds self.tabs with all standard tabs.
        original_prepare_tabs(self)

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
            logger.debug("Could not add Cadence tab: %s", e, exc_info=True)

    return _prepare_detail_tabs_with_cadence_tab


def inject_cadence_tab():
    """Wrap HorillaDetailTabView._prepare_detail_tabs to add the Cadence tab
    when the model has active cadences."""
    try:
        if not hasattr(HorillaDetailTabView, "_original_prepare_detail_tabs_cadence"):
            HorillaDetailTabView._original_prepare_detail_tabs_cadence = (
                HorillaDetailTabView._prepare_detail_tabs
            )
            HorillaDetailTabView._prepare_detail_tabs = (
                create_prepare_tabs_with_cadence_tab(
                    HorillaDetailTabView._original_prepare_detail_tabs_cadence
                )
            )
    except Exception as e:
        logger.warning("Failed to inject cadence tab: %s", e)


inject_cadence_tab()
