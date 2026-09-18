"""
Inject custom-field row filtering into filtersets through FilterExtension
(_inherit_filter).

Discovers ``HorillaFilterSet`` subclasses whose ``Meta.model`` opted in to
custom fields (via ``register_model_for_feature(...,
features=["custom_fields_models"])`` in the model's own app
``registration.py``) and registers one ``FilterExtension`` per filterset,
overriding ``_build_row_q`` so a ``cf_*`` filter row builds a real ``Q()``
instead of Horilla's own ``_build_row_q`` (which only knows model columns).
No model or filterset class is ever imported by name here.

Mirrors ``custom_fields/extensions.py``'s discovery pattern exactly: it
registers a pre-compose hook (``horilla.extension._pre_compose_hooks``) so
newly opted-in models (registered by a CRM app's own ``registration.py``,
possibly after this app's ``ready()``) are picked up without relying on
import order — no Horilla module attribute is reassigned.

This only replaces the row-filtering half of ``custom_fields/filter_hooks.py``.
``HorillaListFilterFieldsMixin._get_model_fields`` (the "Filter Records"
field dropdown) is registered separately, through ``MixinExtension``/
``_inherit_mixin`` — see ``custom_fields/mixin_extensions.py`` — since it is
a bare view mixin never resolved by any per-request extension mechanism.
"""

# Standard library imports
import inspect
import logging
import pkgutil
from importlib import import_module

# Third-party imports (Django)
from django.apps import apps as django_apps

from custom_fields.filter_hooks import custom_field_row_q
from custom_fields.utils import is_custom_field_name

# First party imports (Horilla)
from horilla.contrib.generics.filters import HorillaFilterSet
from horilla.extension.filter import FilterExtension
from horilla.extension.filter.registry import FILTER_EXTENSION_REGISTRY
from horilla.registry.feature import FEATURE_REGISTRY

logger = logging.getLogger(__name__)

_DISCOVERY_HOOK_INSTALLED = False


def _configurable_models():
    return set(FEATURE_REGISTRY.get("custom_fields_models", []))


def register_discovered_filter_extensions():
    """Register a FilterExtension for each opted-in model's discovered filtersets.

    Idempotent. Safe to call before CRM apps have opted in (no-op) and again
    after the feature registry is populated. Returns the number of
    filtersets newly registered.
    """
    registered = 0
    for filterset_class in iter_configurable_model_filtersets():
        if _register_filter_extension(filterset_class):
            registered += 1
    return registered


def iter_configurable_model_filtersets():
    """Yield HorillaFilterSet subclasses whose Meta.model opted in."""
    configurable = _configurable_models()
    if not configurable:
        return

    app_labels = {model._meta.app_label for model in configurable}
    for app_label in sorted(app_labels):
        try:
            app_config = django_apps.get_app_config(app_label)
        except LookupError:
            continue
        for filterset_class in _iter_app_model_filtersets(app_config):
            if _filterset_model(filterset_class) in configurable:
                yield filterset_class


def _filterset_model(filterset_class):
    """Return ``Meta.model`` when it is a real Django model, else ``None``."""
    model = getattr(getattr(filterset_class, "Meta", None), "model", None)
    if model is None or getattr(model, "_meta", None) is None:
        return None
    return model


def _iter_app_model_filtersets(app_config):
    """Yield HorillaFilterSet subclasses defined in ``{app}.filters`` modules."""
    for module in _iter_filters_modules(app_config):
        for filterset_class in _iter_module_model_filtersets(module):
            yield filterset_class


def _iter_filters_modules(app_config):
    """Import ``{app}.filters`` and, when it is a package, its submodules."""
    module_name = f"{app_config.name}.filters"
    try:
        module = import_module(module_name)
    except ModuleNotFoundError:
        return
    except Exception:
        logger.exception(
            "Could not import %s while discovering filtersets", module_name
        )
        return

    yield module
    paths = getattr(module, "__path__", None)
    if not paths:
        return

    for module_info in pkgutil.walk_packages(paths, prefix=module_name + "."):
        name = module_info.name
        if name.rsplit(".", 1)[-1] in {"tests", "test_filters"}:
            continue
        try:
            yield import_module(name)
        except Exception:
            logger.exception("Could not import %s while discovering filtersets", name)


def _iter_module_model_filtersets(module):
    """Yield HorillaFilterSet subclasses defined in ``module``."""
    for _name, obj in inspect.getmembers(module, inspect.isclass):
        if obj.__module__ != module.__name__:
            continue
        if "." in getattr(obj, "__qualname__", ""):
            continue
        if getattr(obj, "__horilla_composed__", False):
            continue
        if not issubclass(obj, HorillaFilterSet):
            continue
        if obj is HorillaFilterSet:
            continue
        yield obj


def _filterset_path(filterset_class):
    """Return the path ``resolve_filterset_class`` uses for ``filterset_class``."""
    return f"{filterset_class.__module__}.{filterset_class.__name__}"


def _already_registered(filterset_path):
    """Return True when this app already registered an extension for ``filterset_path``."""
    for spec in FILTER_EXTENSION_REGISTRY.get(filterset_path, []):
        if spec.extension_app_label == "custom_fields":
            return True
        if spec.module == __name__:
            return True
    return False


class _FilterMethods(FilterExtension):
    """
    Template for the methods a custom-fields ``FilterExtension`` needs.

    Never itself registered (no ``_inherit_filter`` here) and never used as
    a base class — ``register_filter_extension_class`` only captures methods
    present directly in a ``FilterExtension`` subclass's own ``__dict__``
    (not inherited ones), so ``_register_filter_extension`` copies this
    function object, by reference, into each concrete filterset's
    dynamically created subclass namespace instead of subclassing this
    template.

    Real ``super()`` here is safe despite that: ``compose_filterset_class``
    (``horilla/extension/filter/compose.py``) rebinds the captured method's
    ``__class__`` closure cell to the actual mixin it ends up composed into
    (see ``horilla.extension._super_rebind``), so ``super()._build_row_q(...)``
    correctly resolves to the next extension or the target filterset
    regardless of which subclass this function object is attached to.
    """

    def _build_row_q(self, model, field, operator, i, values, start_values, end_values):
        if is_custom_field_name(field):
            try:
                return custom_field_row_q(
                    model, field, operator, i, values, start_values, end_values
                )
            except Exception:
                logger.exception(
                    "custom_fields: could not build filter Q for %s", field
                )
                return None
        return super()._build_row_q(
            model, field, operator, i, values, start_values, end_values
        )


def _register_filter_extension(filterset_class):
    """Create and register a FilterExtension subclass for ``filterset_class``."""
    filterset_path = _filterset_path(filterset_class)
    if _already_registered(filterset_path):
        return False

    namespace = {
        key: value
        for key, value in _FilterMethods.__dict__.items()
        if not key.startswith("__")
    }
    namespace["_inherit_filter"] = filterset_path
    namespace["__module__"] = __name__
    namespace["__doc__"] = f"Injects custom-field row filtering into {filterset_path}."
    type(
        f"CustomFields{filterset_class.__name__}Extension",
        (FilterExtension,),
        namespace,
    )
    return True


def _install_discovery_hook():
    """Register discovery to run at the start of Horilla's filter-extension compose step."""
    global _DISCOVERY_HOOK_INSTALLED
    if _DISCOVERY_HOOK_INSTALLED:
        return

    from horilla.extension._pre_compose_hooks import register_pre_compose_hook

    register_pre_compose_hook("filter", register_discovered_filter_extensions)
    _DISCOVERY_HOOK_INSTALLED = True


_install_discovery_hook()
register_discovered_filter_extensions()
