"""
Inject custom fields into forms through FormExtension (_inherit_form).

Horilla composes ``FormExtension`` subclasses onto concrete forms after every
app has loaded. This module discovers ``HorillaMultiStepForm``/
``HorillaModelForm`` subclasses whose ``Meta.model`` opted in to custom
fields (via ``register_model_for_feature(..., features=["custom_fields_models"])``
in the model's own app ``registration.py``) and registers one extension per
form. No model, form, or view class is ever imported by name here.

This mirrors ``horilla.contrib.field_requirements.extensions``'s discovery
pattern: it registers a pre-compose hook (``horilla.extension._pre_compose_hooks``)
that runs at the start of every ``apply_form_extensions()`` call (the same
compose step views already trigger) rather than running once during
``ready()``, since CRM apps opt in during their own ``ready()`` which may
run after this app's. The hook is an ordinary registration — no Horilla
module attribute is reassigned.

``clean``/``save`` use plain ``super()`` (per ``docs/horilla/extension/forms/inherit.md``
"Method merge" — "``clean`` / ``save`` — If overridden, must call
``super()``"). This only works because the mixin classes below
(``_CustomFieldsMultiStepFormMixin``, ``_CustomFieldsSingleFormMixin``) are
real, statically-defined classes: a method's zero-arg ``super()`` needs a
``__class__`` closure cell bound to the class it is textually written in,
and that class must actually sit in the composed MRO. Each concrete form
gets its own dynamically-created ``FormExtension`` subclass, but that
subclass only sets ``_inherit_form`` — it inherits the real
``clean``/``save``/``setup_form_extension_fields`` methods from one of these
two static mixins, so ``super()`` resolves correctly regardless of which
form it ends up composed onto.
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


class _MultiStepFormMethods(FormExtension):
    """
    Template for the methods a multi-step ``FormExtension`` needs.

    Never itself registered (no ``_inherit_form`` here) and never used as a
    base class — ``register_extension_class`` only captures methods present
    directly in a ``FormExtension`` subclass's own ``__dict__`` (not
    inherited ones), so ``_register_form_extension`` copies these function
    objects, by reference, straight into each concrete form's dynamically
    created subclass namespace instead of subclassing this template.

    Real ``super()`` here is safe despite that: the framework's own
    ``_spec_to_mixin()`` (``horilla/extension/forms/compose.py``) rebinds
    each captured method's ``__class__`` closure cell to the actual mixin it
    ends up composed into (see ``horilla.extension._super_rebind`), so
    ``super().clean()`` / ``super().save()`` correctly resolve to the next
    extension or the target form regardless of which subclass this function
    object is attached to.
    """

    def setup_form_extension_fields(self):
        apply_multi_step_custom_fields(self, self._meta.model)

    def clean(self):
        return clean_multi_step_custom_fields(self, super().clean)

    def save(self, commit=True):
        return save_with_custom_fields(self, super().save, commit=commit)


class _SingleFormMethods(FormExtension):
    """Template for the methods a single-step ``FormExtension`` needs (see ``_MultiStepFormMethods``)."""

    def setup_form_extension_fields(self):
        apply_single_form_custom_fields(self, self._meta.model)

    def save(self, commit=True):
        return save_with_custom_fields(self, super().save, commit=commit)


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
    above — the same functions the pre-extension ``inject.py`` wrapper used.
    """
    form_path = _form_path(form_class)
    if _already_registered(form_path):
        return False

    template = (
        _MultiStepFormMethods
        if issubclass(form_class, HorillaMultiStepForm)
        else _SingleFormMethods
    )
    namespace = {
        key: value
        for key, value in template.__dict__.items()
        if not key.startswith("__")
    }
    namespace["_inherit_form"] = form_path
    namespace["__module__"] = __name__
    namespace["__doc__"] = f"Injects custom fields into {form_path}."
    type(
        f"CustomFields{form_class.__name__}Extension",
        (FormExtension,),
        namespace,
    )
    return True


def _install_discovery_hook():
    """Register discovery to run at the start of Horilla's form-extension compose step."""
    global _DISCOVERY_HOOK_INSTALLED
    if _DISCOVERY_HOOK_INSTALLED:
        return

    from horilla.extension._pre_compose_hooks import register_pre_compose_hook

    register_pre_compose_hook("forms", register_discovered_form_extensions)
    _DISCOVERY_HOOK_INSTALLED = True


_install_discovery_hook()
register_discovered_form_extensions()
