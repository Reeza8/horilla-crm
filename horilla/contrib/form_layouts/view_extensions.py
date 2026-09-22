"""
Offer saved create form layouts as an extra ``form_mode`` entry on Horilla's
generic form views, through ``ViewExtension``/``_inherit_view`` (the same
mechanism ``custom_fields.view_extensions.CustomFieldMultiStepFormKwargsExtension``
uses), instead of monkey-patching.

Neither the wizard nor the plain single-page form is ever intercepted or
redirected: a create or edit request behaves exactly as it did before this
app was installed unless the visitor explicitly follows the "Custom Layout"
mode link this app adds to the view's ``form_mode`` list (see
``FormViewCommonMixin.form_mode``/``resolve_form_mode`` in
``horilla/contrib/generics/views/toolkit/form_mixin.py``) — alongside whatever
modes the view already declares (e.g. an app's own Single-Step/Multi-Step
entries), or the generic "Default Form" entry that base class falls back to
when a view declares none, so the mode switcher always has something to
switch away from (this app never needs to know or guess that fallback's
shape). That link points at the model's single-page create/edit view with
``?form_layout=1`` appended, and only ``get_form`` reads that marker to leave
hidden fields out and reorder the rest — everything else about the
single-page view is untouched, and the wizard never renders the trimmed form
at all.

Removing a field from the form never touches its stored value: Django's
``ModelForm.save()``/``construct_instance`` only writes fields present in
``form.fields``, so a hidden optional field on an edit request keeps
whatever the record already has, the same way a field that never appears in
POST data is left alone. Required fields are never removed at all (see
``apply_form_layout`` in ``utils.py``).

Each extension below targets the shared base class instead of one concrete
view: ``resolve_view_class`` checks an exact match first, then falls back to
a base class in the MRO (see ``horilla/extension/view/resolve.py``'s
``_resolve_via_base_class``), so one registration here applies to every
concrete single-page/wizard view, present and future, without naming any of
them.

Duplicate requests never show or use the custom layout: they intentionally
render every field so the copied values are all visible for review before
saving.
"""

# Standard library imports
import logging

# First party imports (Horilla)
from horilla.extension.view import ViewExtension
from horilla.utils.translation import gettext_lazy as _

# Local imports
from .registry import is_layout_configurable
from .utils import apply_form_layout, get_form_layout, is_empty_value

logger = logging.getLogger(__name__)

LAYOUT_MODE_PARAM = "form_layout"
LAYOUT_MODE_TITLE = _("Custom Layout")


def is_layoutable_request(view):
    """
    Return True when ``view``'s current request is eligible for a custom
    layout: any create or edit request except a duplicate. Duplicate mode
    intentionally shows every field so the copied values are all visible for
    review before saving, so the layout never applies there.
    """
    return not getattr(view, "duplicate_mode", False)


def get_active_layout(view):
    """Return the layout ``view``'s current request should render, or None.

    Only true once the visitor has actually followed the "Custom Layout"
    mode link (``?form_layout=1``) for a model with a saved layout — never
    inferred just because a layout exists, so the default form stays default
    until asked otherwise.
    """
    if view.request.GET.get(LAYOUT_MODE_PARAM) not in ("1", "true", "True"):
        return None
    model = getattr(view, "model", None)
    if model is None or not is_layout_configurable(model):
        return None
    if not is_layoutable_request(view):
        return None
    return get_form_layout(model)


def get_prefilled_field_names(view):
    """Return fields the view pre-fills (e.g. the account on a related create)."""
    try:
        initial = view.get_initial() or {}
    except Exception:
        logger.exception("form_layouts: could not read initial data")
        return set()
    return {name for name, value in initial.items() if not is_empty_value(value)}


def _has_saved_layout(view):
    """Return True when ``view``'s model has a saved layout for this request."""
    model = getattr(view, "model", None)
    if model is None or not is_layout_configurable(model):
        return False
    if not is_layoutable_request(view):
        return False
    return get_form_layout(model) is not None


def _layout_mode_entry(url, active):
    """Build the ``form_mode`` dict for the custom-layout link at ``url``."""
    if not url:
        return None
    separator = "&" if "?" in url else "?"
    return {
        "title": LAYOUT_MODE_TITLE,
        "hx_get": f"{url}{separator}{LAYOUT_MODE_PARAM}=1",
        "hx_target": "#modalBox",
        "hx_swap": "innerHTML",
        "active": active,
    }


def _deactivate(modes):
    """Return ``modes`` with every entry's ``active`` flag cleared.

    Used once the custom layout itself is the active mode, so a view's own
    declared ``form_mode`` (e.g. Single-Step marked ``active: True`` by
    default) does not keep lighting up alongside "Custom Layout".
    """
    return [{**mode, "active": False} for mode in modes]


class FormLayoutSingleFormViewExtension(ViewExtension):
    """Apply the saved layout only when the custom-layout mode is active."""

    _inherit_view = "horilla.contrib.generics.views.single_form.HorillaSingleFormView"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        try:
            layout = get_active_layout(self)
            if layout is not None and form is not None:
                protected = set(getattr(self, "hidden_fields", None) or [])
                protected |= set(getattr(self, "condition_fields", None) or [])
                protected |= get_prefilled_field_names(self)
                apply_form_layout(form, layout, protected)
        except Exception:
            logger.exception("form_layouts: could not apply the form layout")
        return form

    def resolve_form_mode(self):
        modes = super().resolve_form_mode()
        try:
            if not _has_saved_layout(self):
                return modes
            layout_active = bool(get_active_layout(self))
            if layout_active:
                modes = _deactivate(modes)
            entry = _layout_mode_entry(self.request.path, active=layout_active)
            if entry is not None:
                modes = [*modes, entry]
        except Exception:
            logger.exception("form_layouts: could not add the custom-layout mode")
        return modes


class FormLayoutMultiStepFormViewExtension(ViewExtension):
    """Offer a link to the custom layout from the wizard, without redirecting."""

    _inherit_view = "horilla.contrib.generics.views.multi_form.HorillaMultiStepFormView"

    def resolve_form_mode(self):
        modes = super().resolve_form_mode()
        try:
            if not _has_saved_layout(self):
                return modes
            # The wizard marks its own form_mode entry active: True; the
            # other entry is its counterpart form, and the custom layout is
            # never the active mode here, since the wizard never renders the
            # trimmed form itself.
            counterpart_url = next(
                (mode["hx_get"] for mode in modes if not mode.get("active")),
                None,
            )
            entry = _layout_mode_entry(counterpart_url, active=False)
            if entry is not None:
                modes = [*modes, entry]
        except Exception:
            logger.exception("form_layouts: could not add the custom-layout mode")
        return modes
