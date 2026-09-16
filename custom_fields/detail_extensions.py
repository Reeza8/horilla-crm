"""
Inject custom fields into detail views through DetailExtension (_inherit_detail)
and DetailSectionExtension (_inherit_detail_section).

Discovers ``HorillaDetailView``/``HorillaDetailSectionView`` subclasses whose
``model`` opted in to custom fields (via
``register_model_for_feature(..., features=["custom_fields_models"])`` in the
model's own app ``registration.py``), using the same ``_view_registry`` every
other model-keyed detail lookup in Horilla uses, and registers one extension
per view. No model or view class is ever imported by name here.

Mirrors ``horilla.contrib.field_requirements.extensions``'s discovery
pattern: it hooks into ``apply_detail_extensions``/
``apply_detail_section_extensions`` so newly opted-in models (registered by
a CRM app's own ``registration.py``, possibly after this app's ``ready()``)
are picked up without relying on import order.
"""

# Standard library imports
import logging

from custom_fields.integration import apply_custom_fields_to_detail_context
from horilla.contrib.generics.views.detail_tabs import HorillaDetailSectionView

# First party imports (Horilla)
from horilla.contrib.generics.views.details import HorillaDetailView
from horilla.extension.detail import DetailExtension
from horilla.extension.detail.registry import DETAIL_EXTENSION_REGISTRY
from horilla.extension.detail_section import DetailSectionExtension
from horilla.extension.detail_section.registry import DETAIL_SECTION_EXTENSION_REGISTRY
from horilla.registry.feature import FEATURE_REGISTRY

logger = logging.getLogger(__name__)

_DISCOVERY_HOOK_INSTALLED = False


def _configurable_models():
    return set(FEATURE_REGISTRY.get("custom_fields_models", []))


def register_discovered_detail_extensions():
    """Register a DetailExtension for each opted-in model's detail view.

    Idempotent. Safe to call before CRM apps have opted in (no-op) and again
    after the feature registry is populated. Returns the number of views
    newly registered.
    """
    registered = 0
    for model in _configurable_models():
        view_class = HorillaDetailView._view_registry.get(model)
        if view_class is None:
            continue
        if _register_detail_extension(view_class):
            registered += 1
    return registered


def register_discovered_detail_section_extensions():
    """Register a DetailSectionExtension for each opted-in model's section view.

    Idempotent. Safe to call before CRM apps have opted in (no-op) and again
    after the feature registry is populated. Returns the number of views
    newly registered.
    """
    registered = 0
    for model in _configurable_models():
        view_class = HorillaDetailSectionView._view_registry.get(model)
        if view_class is None:
            continue
        if _register_detail_section_extension(view_class):
            registered += 1
    return registered


def _view_path(view_class):
    """Return the path resolve_detail_view_class uses for ``view_class``."""
    wrapped = getattr(view_class, "__wrapped_detail_view__", view_class)
    return f"{wrapped.__module__}.{wrapped.__name__}"


def _section_view_path(view_class):
    """Return the path resolve_detail_section_view_class uses for ``view_class``."""
    wrapped = getattr(view_class, "__wrapped_detail_section_view__", view_class)
    return f"{wrapped.__module__}.{wrapped.__name__}"


def _already_registered(registry, view_path):
    """Return True when this app already registered an extension for ``view_path``."""
    for spec in registry.get(view_path, []):
        if spec.extension_app_label == "custom_fields":
            return True
        if spec.module == __name__:
            return True
    return False


def _make_get_context_data(target_view_class):
    """
    Build a ``get_context_data`` override bound to ``target_view_class``.

    Calling ``target_view_class.get_context_data(self, **kwargs)`` directly
    (rather than a zero-arg/``type(self)`` ``super()``) is deliberate: the
    mixin object the framework builds around this function is created later,
    inside ``compose.py`` and does not exist yet when this module registers
    the extension, so ``type(self)`` at call time is always the composed
    (leaf) class — a ``super(type(self), self)`` call would recurse back into
    this same function instead of reaching the target. custom_fields is the
    only extension registered for these views, so calling the concrete
    target class directly is safe and correct.
    """

    def get_context_data(self, **kwargs):
        context = target_view_class.get_context_data(self, **kwargs)
        obj = (
            context.get("obj") or context.get("object") or getattr(self, "object", None)
        )
        apply_custom_fields_to_detail_context(
            context, obj, request=getattr(self, "request", None), view=self
        )
        return context

    return get_context_data


def _register_detail_extension(view_class):
    """Create and register a DetailExtension subclass for ``view_class``."""
    view_path = _view_path(view_class)
    if _already_registered(DETAIL_EXTENSION_REGISTRY, view_path):
        return False

    type(
        f"CustomFields{view_class.__name__}Extension",
        (DetailExtension,),
        {
            "_inherit_detail": view_path,
            "get_context_data": _make_get_context_data(view_class),
            "__module__": __name__,
            "__doc__": f"Injects custom fields into {view_path}.",
        },
    )
    return True


def _register_detail_section_extension(view_class):
    """Create and register a DetailSectionExtension subclass for ``view_class``."""
    view_path = _section_view_path(view_class)
    if _already_registered(DETAIL_SECTION_EXTENSION_REGISTRY, view_path):
        return False

    type(
        f"CustomFields{view_class.__name__}Extension",
        (DetailSectionExtension,),
        {
            "_inherit_detail_section": view_path,
            "get_context_data": _make_get_context_data(view_class),
            "__module__": __name__,
            "__doc__": f"Injects custom fields into {view_path}.",
        },
    )
    return True


def _install_discovery_hook():
    """Run discovery at the start of Horilla's detail/detail-section compose steps."""
    global _DISCOVERY_HOOK_INSTALLED
    if _DISCOVERY_HOOK_INSTALLED:
        return

    from horilla.extension import detail as detail_pkg
    from horilla.extension import detail_section as detail_section_pkg
    from horilla.extension.detail import bootstrap as detail_bootstrap
    from horilla.extension.detail_section import bootstrap as detail_section_bootstrap

    original_detail = detail_bootstrap.apply_detail_extensions
    original_detail_section = detail_section_bootstrap.apply_detail_section_extensions

    if not getattr(original_detail, "_custom_fields_hooked", False):

        def apply_detail_extensions(force=False):
            """Discover custom-field detail extensions, then compose as usual."""
            register_discovered_detail_extensions()
            return original_detail(force=force)

        apply_detail_extensions._custom_fields_hooked = True
        apply_detail_extensions.__wrapped__ = original_detail
        detail_bootstrap.apply_detail_extensions = apply_detail_extensions
        detail_pkg.apply_detail_extensions = apply_detail_extensions

    if not getattr(original_detail_section, "_custom_fields_hooked", False):

        def apply_detail_section_extensions(force=False):
            """Discover custom-field detail-section extensions, then compose as usual."""
            register_discovered_detail_section_extensions()
            return original_detail_section(force=force)

        apply_detail_section_extensions._custom_fields_hooked = True
        apply_detail_section_extensions.__wrapped__ = original_detail_section
        detail_section_bootstrap.apply_detail_section_extensions = (
            apply_detail_section_extensions
        )
        detail_section_pkg.apply_detail_section_extensions = (
            apply_detail_section_extensions
        )

    _DISCOVERY_HOOK_INSTALLED = True


_install_discovery_hook()
register_discovered_detail_extensions()
register_discovered_detail_section_extensions()
