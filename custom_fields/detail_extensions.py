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
pattern: it registers pre-compose hooks (``horilla.extension._pre_compose_hooks``)
for both ``apply_detail_extensions``/``apply_detail_section_extensions`` so
newly opted-in models (registered by a CRM app's own ``registration.py``,
possibly after this app's ``ready()``) are picked up without relying on
import order — no Horilla module attribute is reassigned.
"""

# Standard library imports
import logging

from custom_fields.detail_hooks import restore_custom_fields_in_order
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


class _DetailMethods(DetailExtension):
    """
    Template for the methods a ``DetailExtension`` needs on ``HorillaDetailView``.

    Never itself registered (no ``_inherit_detail`` here) and never used as a
    base class — ``register_detail_extension_class`` only captures methods
    present directly in a ``DetailExtension`` subclass's own ``__dict__``
    (not inherited ones), so ``_register_detail_extension`` copies these
    function objects, by reference, into each concrete view's dynamically
    created subclass namespace instead of subclassing this template.

    Real ``super()`` here is safe despite that: ``compose_detail_view_class``
    (``horilla/extension/detail/compose.py``) rebinds each captured method's
    ``__class__`` closure cell to the actual mixin it ends up composed into
    (see ``horilla.extension._super_rebind``), so ``super().get_context_data()``
    correctly resolves to the next extension or the target view regardless
    of which subclass this function object is attached to.
    """

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = (
            context.get("obj") or context.get("object") or getattr(self, "object", None)
        )
        apply_custom_fields_to_detail_context(
            context, obj, request=getattr(self, "request", None), view=self
        )
        return context

    def _normalize_field_list(self, field_list, exclude_set):
        """
        ``HorillaDetailView._normalize_field_list`` drops any name that is
        not a real Django model field (``instance._meta.get_field(field_name)``
        raises ``FieldDoesNotExist`` for ``cf_*`` names) — used by both
        ``get_header_fields()`` (feeds ``context["header_fields"]``, read by
        the "Change Detail View Fields" picker's currently-selected list)
        and ``get_body()`` when a saved
        ``DetailFieldVisibility.header_fields`` exists. ``get_context_data``'s
        custom-field merge only rebuilds ``context["body"]``, so a saved
        custom field would otherwise silently disappear from the header's
        own field-list normalization. Re-inserting it here keeps that in
        sync without touching Horilla's own ``details.py``.
        """
        kept = super()._normalize_field_list(field_list, exclude_set)
        model = getattr(self, "model", None)
        if model is None:
            return kept
        return restore_custom_fields_in_order(model, field_list, kept, exclude_set)


class _DetailSectionMethods(DetailSectionExtension):
    """Template for the methods a ``DetailSectionExtension`` needs (see ``_DetailMethods``)."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = (
            context.get("obj") or context.get("object") or getattr(self, "object", None)
        )
        apply_custom_fields_to_detail_context(
            context, obj, request=getattr(self, "request", None), view=self
        )
        return context


def _copy_template_namespace(template):
    return {
        key: value
        for key, value in template.__dict__.items()
        if not key.startswith("__")
    }


def _register_detail_extension(view_class):
    """Create and register a DetailExtension subclass for ``view_class``."""
    view_path = _view_path(view_class)
    if _already_registered(DETAIL_EXTENSION_REGISTRY, view_path):
        return False

    namespace = _copy_template_namespace(_DetailMethods)
    namespace["_inherit_detail"] = view_path
    namespace["__module__"] = __name__
    namespace["__doc__"] = f"Injects custom fields into {view_path}."
    type(f"CustomFields{view_class.__name__}Extension", (DetailExtension,), namespace)
    return True


def _register_detail_section_extension(view_class):
    """Create and register a DetailSectionExtension subclass for ``view_class``."""
    view_path = _section_view_path(view_class)
    if _already_registered(DETAIL_SECTION_EXTENSION_REGISTRY, view_path):
        return False

    namespace = _copy_template_namespace(_DetailSectionMethods)
    namespace["_inherit_detail_section"] = view_path
    namespace["__module__"] = __name__
    namespace["__doc__"] = f"Injects custom fields into {view_path}."
    type(
        f"CustomFields{view_class.__name__}Extension",
        (DetailSectionExtension,),
        namespace,
    )
    return True


def _install_discovery_hook():
    """Register discovery to run at the start of Horilla's detail/detail-section compose steps."""
    global _DISCOVERY_HOOK_INSTALLED
    if _DISCOVERY_HOOK_INSTALLED:
        return

    from horilla.extension._pre_compose_hooks import register_pre_compose_hook

    register_pre_compose_hook("detail", register_discovered_detail_extensions)
    register_pre_compose_hook(
        "detail_section", register_discovered_detail_section_extensions
    )
    _DISCOVERY_HOOK_INSTALLED = True


_install_discovery_hook()
register_discovered_detail_extensions()
register_discovered_detail_section_extensions()
