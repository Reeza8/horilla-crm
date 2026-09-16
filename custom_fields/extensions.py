"""
Inject custom fields into forms through FormExtension (_inherit_form).

Horilla composes ``FormExtension`` subclasses onto concrete forms after every
app has loaded. This module discovers ``HorillaMultiStepForm``/
``HorillaModelForm`` subclasses whose ``Meta.model`` opted in to custom
fields (via ``register_model_for_feature(..., features=["custom_fields_models"])``
in the model's own app ``registration.py``) and registers one extension per
form. No model, form, or view class is ever imported by name here.

This mirrors ``horilla.contrib.field_requirements.extensions`` exactly:
discovery hooks into ``apply_form_extensions`` (the same compose step views
already call) rather than running once during ``ready()``, since CRM apps
opt in during their own ``ready()`` which may run after this app's.
"""

# Standard library imports
import inspect
import logging
import pkgutil
from importlib import import_module

# Third-party imports (Django)
from django.apps import apps as django_apps

from custom_fields.integration import (
    apply_multi_step_custom_fields,
    apply_single_form_custom_fields,
    clean_multi_step_custom_fields,
    save_with_custom_fields,
)

# First party imports (Horilla)
from horilla.contrib.generics.forms.multi_step import HorillaMultiStepForm
from horilla.contrib.generics.forms.single_step import HorillaModelForm
from horilla.extension.forms import FormExtension
from horilla.extension.forms.registry import FORM_EXTENSION_REGISTRY
from horilla.registry.feature import FEATURE_REGISTRY

logger = logging.getLogger(__name__)

_DISCOVERY_HOOK_INSTALLED = False


def _configurable_models():
    return set(FEATURE_REGISTRY.get("custom_fields_models", []))


def register_discovered_form_extensions():
    """Register a FormExtension for each opted-in model's discovered forms.

    Idempotent. Safe to call before CRM apps have opted in (no-op) and again
    after the feature registry is populated. Returns the number of forms
    newly registered.
    """
    registered = 0
    for form_class in iter_configurable_model_forms():
        if _register_form_extension(form_class):
            registered += 1
    return registered


def iter_configurable_model_forms():
    """Yield HorillaMultiStepForm/HorillaModelForm subclasses whose Meta.model opted in."""
    configurable = _configurable_models()
    if not configurable:
        return

    app_labels = {model._meta.app_label for model in configurable}
    for app_label in sorted(app_labels):
        try:
            app_config = django_apps.get_app_config(app_label)
        except LookupError:
            continue
        for form_class in _iter_app_model_forms(app_config):
            if _form_model(form_class) in configurable:
                yield form_class


def _form_model(form_class):
    """Return ``Meta.model`` when it is a real Django model, else ``None``."""
    model = getattr(getattr(form_class, "Meta", None), "model", None)
    if model is None or getattr(model, "_meta", None) is None:
        return None
    return model


def _iter_app_model_forms(app_config):
    """Yield HorillaMultiStepForm/HorillaModelForm subclasses defined in ``{app}.forms`` modules."""
    for module in _iter_forms_modules(app_config):
        for form_class in _iter_module_model_forms(module):
            yield form_class


def _iter_forms_modules(app_config):
    """Import ``{app}.forms`` and, when it is a package, its submodules."""
    module_name = f"{app_config.name}.forms"
    try:
        module = import_module(module_name)
    except ModuleNotFoundError:
        return
    except Exception:
        logger.exception("Could not import %s while discovering forms", module_name)
        return

    yield module
    paths = getattr(module, "__path__", None)
    if not paths:
        return

    for module_info in pkgutil.walk_packages(paths, prefix=module_name + "."):
        name = module_info.name
        if name.rsplit(".", 1)[-1] in {"tests", "test_forms"}:
            continue
        try:
            yield import_module(name)
        except Exception:
            logger.exception("Could not import %s while discovering forms", name)


def _iter_module_model_forms(module):
    """Yield HorillaMultiStepForm/HorillaModelForm subclasses defined in ``module``."""
    for _name, obj in inspect.getmembers(module, inspect.isclass):
        if obj.__module__ != module.__name__:
            continue
        if "." in getattr(obj, "__qualname__", ""):
            continue
        if getattr(obj, "__horilla_composed__", False):
            continue
        if not issubclass(obj, (HorillaMultiStepForm, HorillaModelForm)):
            continue
        if obj in (HorillaMultiStepForm, HorillaModelForm):
            continue
        yield obj


def _form_path(form_class):
    """Return the path ``resolve_form_class`` uses for ``form_class``."""
    return f"{form_class.__module__}.{form_class.__name__}"


def _already_registered(form_path):
    """Return True when this app already registered an extension for ``form_path``."""
    for spec in FORM_EXTENSION_REGISTRY.get(form_path, []):
        if spec.extension_app_label == "custom_fields":
            return True
        if spec.module == __name__:
            return True
    return False


def _multi_step_setup(self):
    """FormExtension hook: build cf_* fields into the last step after __init__."""
    apply_multi_step_custom_fields(self, self._meta.model)


def _make_multi_step_clean(target_form_class):
    """
    Build a ``clean`` override bound to ``target_form_class``.

    The composed class MRO is ``Composed -> ExtMixin -> target_form_class``,
    but the mixin object the framework builds around this function is created
    later, inside ``compose.py`` — it does not exist yet when this module
    registers the extension, so a zero-arg/``type(self)`` ``super()`` cannot
    resolve reliably here (``type(self)`` is always the leaf composed class,
    which recurses back into this same function). Calling
    ``target_form_class.clean(self)`` directly is safe: it is the one
    concrete class this extension targets, and custom_fields is the only
    extension registered for these forms, so no other mixin sits between
    this one and the target in the MRO.
    """

    def clean(self):
        return clean_multi_step_custom_fields(
            self, lambda: target_form_class.clean(self)
        )

    return clean


def _make_multi_step_save(target_form_class):
    """Build a ``save`` override bound to ``target_form_class`` (see _make_multi_step_clean)."""

    def save(self, commit=True):
        return save_with_custom_fields(
            self,
            lambda commit: target_form_class.save(self, commit=commit),
            commit=commit,
        )

    return save


def _single_form_setup(self):
    """FormExtension hook: build cf_* fields after the target form's __init__."""
    apply_single_form_custom_fields(self, self._meta.model)


def _make_single_form_save(target_form_class):
    """Build a ``save`` override bound to ``target_form_class`` (see _make_multi_step_clean)."""

    def save(self, commit=True):
        return save_with_custom_fields(
            self,
            lambda commit: target_form_class.save(self, commit=commit),
            commit=commit,
        )

    return save


def _register_form_extension(form_class):
    """
    Create and register a FormExtension subclass for ``form_class``.

    Deliberately never queries ``CustomFieldDefinition`` here: registration
    runs from ``apply_form_extensions()``, which can fire while Django's app
    registry is still loading (e.g. during ``manage.py test``'s database
    setup, before migrations/permissions exist, or against the wrong
    database entirely before the test DB swap) — a query at that point can
    succeed against the wrong database or crash startup outright. Which
    ``cf_*`` fields exist is fundamentally per-request/per-company dynamic
    (admins add/edit/remove them without a restart), so it is built entirely
    at request time in ``setup_form_extension_fields``/``clean``/``save``
    below — the same functions the pre-extension ``inject.py`` wrapper used.
    """
    form_path = _form_path(form_class)
    if _already_registered(form_path):
        return False

    if issubclass(form_class, HorillaMultiStepForm):
        type(
            f"CustomFields{form_class.__name__}Extension",
            (FormExtension,),
            {
                "_inherit_form": form_path,
                "setup_form_extension_fields": _multi_step_setup,
                "clean": _make_multi_step_clean(form_class),
                "save": _make_multi_step_save(form_class),
                "__module__": __name__,
                "__doc__": f"Injects custom fields into {form_path}.",
            },
        )
    else:
        type(
            f"CustomFields{form_class.__name__}Extension",
            (FormExtension,),
            {
                "_inherit_form": form_path,
                "setup_form_extension_fields": _single_form_setup,
                "save": _make_single_form_save(form_class),
                "__module__": __name__,
                "__doc__": f"Injects custom fields into {form_path}.",
            },
        )
    return True


def _install_discovery_hook():
    """Run discovery at the start of Horilla's form-extension compose step."""
    global _DISCOVERY_HOOK_INSTALLED
    if _DISCOVERY_HOOK_INSTALLED:
        return

    from horilla.extension import forms as forms_pkg
    from horilla.extension.forms import bootstrap as forms_bootstrap

    original = forms_bootstrap.apply_form_extensions
    if getattr(original, "_custom_fields_hooked", False):
        _DISCOVERY_HOOK_INSTALLED = True
        return

    def apply_form_extensions(force=False):
        """Discover custom-field form extensions, then compose as usual."""
        register_discovered_form_extensions()
        return original(force=force)

    apply_form_extensions._custom_fields_hooked = True
    apply_form_extensions.__wrapped__ = original
    forms_bootstrap.apply_form_extensions = apply_form_extensions
    forms_pkg.apply_form_extensions = apply_form_extensions
    _DISCOVERY_HOOK_INSTALLED = True


_install_discovery_hook()
register_discovered_form_extensions()
