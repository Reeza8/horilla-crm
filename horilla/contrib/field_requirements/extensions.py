"""
Apply per-company field-requirement overrides through FormExtension.

Horilla composes ``FormExtension`` subclasses onto concrete forms after every
app has loaded. This module discovers ``ModelForm`` subclasses whose
``Meta.model`` opted in to field requirements and registers one extension per
form. Views keep using ``resolve_form_class``; ``horilla.contrib.generics``
and CRM model files are not imported from here as a dependency of theirs.

This app is listed before the CRM apps, so its ``ready()`` runs before Lead
and Opportunity opt in. Discovery therefore hooks into
``apply_form_extensions`` — the same compose step views already call — rather
than scanning an empty feature registry during ``ready()``.
"""

# Standard library imports
import inspect
import logging
import pkgutil
from importlib import import_module

# Third-party imports (Django)
from django import forms
from django.apps import apps as django_apps
from django.forms.widgets import CheckboxInput, HiddenInput

# First party imports (Horilla)
from horilla.extension.forms import FormExtension
from horilla.extension.forms.registry import FORM_EXTENSION_REGISTRY

# Local imports
from .registry import get_configurable_models, is_requirement_configurable
from .utils import get_field_requirements_for_model

logger = logging.getLogger(__name__)

_DISCOVERY_HOOK_INSTALLED = False


def apply_field_requirement_overrides(form):
    """Set ``field.required`` from the active company's stored overrides.

    Optional overrides always win, including on later wizard steps (those
    fields are already hidden and non-required). Required overrides are not
    applied to hidden wizard steps or to checkboxes, which Horilla treats as
    optional so an unchecked box can submit.
    """
    model = getattr(getattr(form, "_meta", None), "model", None)
    if model is None or not is_requirement_configurable(model):
        return

    try:
        overrides = get_field_requirements_for_model(model)
    except Exception:
        logger.exception(
            "Could not load field-requirement overrides for %s",
            getattr(model._meta, "label", model),
        )
        return

    if not overrides:
        return

    hidden = getattr(form, "_step_hidden_fields", set()) or set()
    for field_name, is_required in overrides.items():
        field = form.fields.get(field_name)
        if field is None:
            continue
        if not is_required:
            _mark_optional(field)
            continue
        if field_name in hidden:
            continue
        if isinstance(field.widget, (CheckboxInput, HiddenInput)):
            continue
        _mark_required(field)


def _mark_optional(field):
    """Stop requiring ``field`` on the form and in the rendered widget."""
    field.required = False
    if hasattr(field, "_original_required"):
        field._original_required = False
    field.widget.attrs.pop("required", None)


def _mark_required(field):
    """Require ``field`` on the form so the asterisk and validation follow."""
    field.required = True
    if hasattr(field, "_original_required"):
        field._original_required = True


def setup_form_extension_fields(self):
    """FormExtension hook: apply overrides after the target form finishes ``__init__``."""
    apply_field_requirement_overrides(self)


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
    """Yield ``ModelForm`` subclasses whose ``Meta.model`` has opted in."""
    configurable = set(get_configurable_models())
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
    """Yield ``ModelForm`` subclasses defined in ``{app}.forms`` modules."""
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
    """Yield ModelForm subclasses that are defined in ``module``."""
    for _name, obj in inspect.getmembers(module, inspect.isclass):
        if obj.__module__ != module.__name__:
            continue
        if "." in getattr(obj, "__qualname__", ""):
            continue
        if getattr(obj, "__horilla_composed__", False):
            continue
        if not issubclass(obj, forms.BaseModelForm):
            continue
        if obj in (forms.BaseModelForm, forms.ModelForm):
            continue
        yield obj


def _form_path(form_class):
    """Return the path ``resolve_form_class`` uses for ``form_class``."""
    return f"{form_class.__module__}.{form_class.__name__}"


def _already_registered(form_path):
    """Return True when this app already registered an extension for ``form_path``."""
    for spec in FORM_EXTENSION_REGISTRY.get(form_path, []):
        if spec.extension_app_label == "field_requirements":
            return True
        if spec.module == __name__:
            return True
    return False


def _register_form_extension(form_class):
    """Create and register a FormExtension subclass for ``form_class``."""
    form_path = _form_path(form_class)
    if _already_registered(form_path):
        return False

    type(
        f"FieldRequirement{form_class.__name__}Extension",
        (FormExtension,),
        {
            "_inherit_form": form_path,
            "setup_form_extension_fields": setup_form_extension_fields,
            "__module__": __name__,
            "__doc__": (
                "Applies per-company field-requirement overrides on " f"{form_path}."
            ),
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
    if getattr(original, "_field_requirements_hooked", False):
        _DISCOVERY_HOOK_INSTALLED = True
        return

    def apply_form_extensions(force=False):
        """Discover field-requirement form extensions, then compose as usual."""
        register_discovered_form_extensions()
        return original(force=force)

    apply_form_extensions._field_requirements_hooked = True
    apply_form_extensions.__wrapped__ = original
    forms_bootstrap.apply_form_extensions = apply_form_extensions
    forms_pkg.apply_form_extensions = apply_form_extensions
    _DISCOVERY_HOOK_INSTALLED = True


_install_discovery_hook()
register_discovered_form_extensions()
