"""
Metaclass for HorillaCoreModel _inherit_model extensions.
"""

from django.apps import apps as django_apps
from django.core.exceptions import AppRegistryNotReady
from django.db.models.base import ModelBase
from django.db.models.fields import Field

from horilla.extension.models.registry import INJECTION_MAP

EXTENSION_REGISTRY = {}

_SKIP_KEYS = frozenset(
    {
        "_inherit_model",
        "_field_overrides",
        "__module__",
        "__qualname__",
        "__doc__",
        "Meta",
    }
)


def _resolve_extension_app_label(module_name):
    """Return Django app label for the module defining an extension class."""
    if not module_name:
        return ""
    try:
        config = django_apps.get_containing_app_config(module_name)
        if config:
            return config.label
    except AppRegistryNotReady:
        pass
    return module_name.split(".")[0]


class ExtensionModelBase(ModelBase):
    """
    When _inherit_model is set, inject fields/methods/dict attrs onto the
    target model, optionally patch existing target fields' attributes via
    _field_overrides (e.g. {"ip": {"verbose_name": _("IP")}}), and return a
    placeholder class (no DB table). Otherwise delegate to Django ModelBase.
    """

    def __new__(cls, name, bases, namespace, **kwargs):
        inherit = namespace.get("_inherit_model")

        if not inherit:
            return super().__new__(cls, name, bases, namespace, **kwargs)

        parts = inherit.rsplit(".", 1)
        if len(parts) != 2:
            raise ValueError(
                f"_inherit_model must be 'app_label.ModelName', got: {inherit!r}"
            )
        app_label, model_name = parts
        # Must match Apps.register_model / do_pending_operations key:
        # (app_label, model._meta.model_name) — model_name is always lowercased.
        model_key = (app_label, model_name.lower())

        contributed_fields = {
            key: value for key, value in namespace.items() if isinstance(value, Field)
        }
        contributed_methods = {
            key: value
            for key, value in namespace.items()
            if callable(value) and not key.startswith("__") and key not in _SKIP_KEYS
        }
        contributed_dicts = {
            key: value
            for key, value in namespace.items()
            if isinstance(value, dict) and key not in _SKIP_KEYS
        }
        contributed_field_overrides = namespace.get("_field_overrides") or {}

        EXTENSION_REGISTRY.setdefault(inherit, []).append(
            {
                "class_name": name,
                "module": namespace.get("__module__", ""),
                "fields": contributed_fields,
                "methods": contributed_methods,
                "dicts": contributed_dicts,
                "field_overrides": contributed_field_overrides,
            }
        )

        module_name = namespace.get("__module__", "")
        extension_app_label = _resolve_extension_app_label(module_name)

        def _apply(target_model):
            for field_name, field in contributed_fields.items():
                if not hasattr(target_model, field_name):
                    field.contribute_to_class(target_model, field_name)
                    injection_key = (
                        target_model._meta.app_label,
                        target_model._meta.model_name,
                        field_name,
                    )
                    INJECTION_MAP[injection_key] = extension_app_label

            for method_name, method in contributed_methods.items():
                if method_name == "clean":
                    existing = getattr(target_model, "clean", None)
                    if existing:

                        def _chained_clean(self, _orig=existing, _ext=method):
                            _orig(self)
                            _ext(self)

                        target_model.clean = _chained_clean
                    else:
                        target_model.clean = method
                elif not hasattr(target_model, method_name):
                    setattr(target_model, method_name, method)

            for dict_name, extra in contributed_dicts.items():
                existing = target_model.__dict__.get(dict_name)
                if isinstance(existing, dict):
                    merged = {**existing, **extra}
                else:
                    merged = dict(extra)
                setattr(target_model, dict_name, merged)

            for field_name, overrides in contributed_field_overrides.items():
                try:
                    target_field = target_model._meta.get_field(field_name)
                except Exception:
                    continue
                for attr_name, attr_value in overrides.items():
                    setattr(target_field, attr_name, attr_value)

        django_apps.lazy_model_operation(_apply, model_key)

        return type(
            name,
            (object,),
            {
                "_is_horilla_extension": True,
                "_inherit_model": inherit,
                "_extension_fields": contributed_fields,
                "_extension_dicts": contributed_dicts,
                "_extension_field_overrides": contributed_field_overrides,
                "__module__": module_name,
                "__qualname__": namespace.get("__qualname__", name),
            },
        )
