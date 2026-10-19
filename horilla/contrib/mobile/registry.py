"""
Which models the phone shows, and how.

An app opts a model in with two things, neither of which imports this package:

- ``features=["mobile"]`` in its ``registration.py`` (the feature registry), and
- a ``mobile.py`` module next to it holding plain data::

      MOBILE_MODELS = {
          "Lead": {
              "title_field": "title",
              "phone_fields": ["contact_number"],
              "email_field": "email",
              "status_field": "lead_status",
              "row_fields": ["lead_company", "lead_owner"],
              "search_fields": ["first_name", "last_name", "lead_company"],
          },
      }

``MobileConfig.ready()`` imports every installed app's ``mobile`` module (when
it exists) and keeps the settings here. A model is shown only when it has both
the feature and a ``MOBILE_MODELS`` entry.
"""

# Standard library imports
import importlib
import importlib.util
import logging
from dataclasses import dataclass

# Third-party imports (Django)
from django.core.exceptions import FieldDoesNotExist, ImproperlyConfigured

# First party imports (Horilla)
from horilla.apps import apps
from horilla.registry.feature import FEATURE_REGISTRY

logger = logging.getLogger(__name__)

FEATURE_NAME = "mobile"
REGISTRY_KEY = "mobile_models"

# Name of the dict a ``mobile.py`` module exposes.
MODULE_SETTING = "MOBILE_MODELS"

# A list row shows the title, the status and at most this many extra fields.
MAX_ROW_FIELDS = 2

_LIST_OPTIONS = (
    "phone_fields",
    "header_fields",
    "row_fields",
    "search_fields",
    "filter_fields",
)
_FIELD_OPTIONS = ("title_field", "email_field", "status_field")


@dataclass(frozen=True)
class MobileModelConfig:
    """Display settings of one opted-in model (see the module docstring)."""

    model: type
    title_field: str = ""
    phone_fields: tuple = ()
    email_field: str = ""
    status_field: str = ""
    # Record page key fields for a model without a desktop detail view.
    header_fields: tuple = ()
    row_fields: tuple = ()
    search_fields: tuple = ()
    filter_fields: tuple = ()

    @property
    def key(self):
        """Identifier used in mobile URLs and forms: ``app_label.model_name``."""
        return f"{self.model._meta.app_label}.{self.model._meta.model_name}"

    @property
    def verbose_name_plural(self):
        """Plural model name, e.g. "Leads"."""
        return self.model._meta.verbose_name_plural

    @property
    def verbose_name(self):
        """Singular model name, e.g. "Lead"."""
        return self.model._meta.verbose_name


# ``model class -> MobileModelConfig`` for every ``MOBILE_MODELS`` entry found.
_CONFIGS = {}

# Opted-in models already reported as missing a ``MOBILE_MODELS`` entry.
_WARNED_MISSING = set()


def _check_fields(model, names, option, errors):
    """Append an error for each name in ``names`` that isn't a field of ``model``."""
    for name in names:
        try:
            model._meta.get_field(name)
        except FieldDoesNotExist:
            errors.append(f"{option}: '{name}' is not a field of {model.__name__}")


def _is_choice_field(model, name):
    """True when field ``name`` has a fixed set of values to pick from."""
    try:
        field = model._meta.get_field(name)
    except FieldDoesNotExist:
        return True  # reported separately
    return bool(
        getattr(field, "choices", None)
        or (field.many_to_one and field.related_model is not None)
        or field.get_internal_type() == "BooleanField"
    )


def build_config(model, options, source="MOBILE_MODELS"):
    """
    Validate ``options`` for ``model`` and return a ``MobileModelConfig``.

    Raises ``ImproperlyConfigured`` listing every problem, so a typo in a
    ``mobile.py`` stops startup instead of hiding a field on the phone.
    """
    if not isinstance(options, dict):
        raise ImproperlyConfigured(f"{source}['{model.__name__}'] must be a dict.")
    errors = []
    unknown = set(options) - set(_LIST_OPTIONS) - set(_FIELD_OPTIONS)
    if unknown:
        errors.append(f"unknown option(s): {', '.join(sorted(unknown))}")

    values = {}
    for option in _FIELD_OPTIONS:
        value = options.get(option, "")
        if not isinstance(value, str):
            errors.append(f"{option} must be a field name")
            continue
        if value:
            _check_fields(model, [value], option, errors)
        values[option] = value
    for option in _LIST_OPTIONS:
        value = options.get(option, ())
        if isinstance(value, str) or not all(isinstance(v, str) for v in value):
            errors.append(f"{option} must be a list of field names")
            continue
        _check_fields(model, value, option, errors)
        values[option] = tuple(value)

    for name in (values.get("status_field"), *values.get("filter_fields", ())):
        if name and not _is_choice_field(model, name):
            errors.append(
                f"'{name}' must be a choice, foreign key or boolean field "
                "to be offered as a filter"
            )

    if len(values.get("row_fields", ())) > MAX_ROW_FIELDS:
        errors.append(f"row_fields holds at most {MAX_ROW_FIELDS} fields")

    if errors:
        raise ImproperlyConfigured(
            f"{source}['{model.__name__}']: " + "; ".join(errors) + "."
        )
    return MobileModelConfig(model=model, **values)


def register_config(model, options, source="MOBILE_MODELS"):
    """Validate and store the settings of ``model``; returns the config."""
    config = build_config(model, options, source)
    _CONFIGS[model] = config
    return config


def unregister_config(model):
    """Forget the settings of ``model`` (used by tests)."""
    _CONFIGS.pop(model, None)


def discover_mobile_modules():
    """
    Import ``{app}.mobile`` for every installed app that has one and register
    its ``MOBILE_MODELS``. Called once from ``MobileConfig.ready()``.
    """
    for app_config in apps.get_app_configs():
        module_name = f"{app_config.name}.mobile"
        try:
            spec = importlib.util.find_spec(module_name)
        except (ImportError, ValueError):
            spec = None
        if spec is None:
            continue
        module = importlib.import_module(module_name)
        settings = getattr(module, MODULE_SETTING, None)
        if settings is None:
            continue
        if not isinstance(settings, dict):
            raise ImproperlyConfigured(
                f"{module_name}.{MODULE_SETTING} must be a dict."
            )
        for model_name, options in settings.items():
            try:
                model = app_config.get_model(model_name)
            except LookupError as exc:
                raise ImproperlyConfigured(
                    f"{module_name}.{MODULE_SETTING}: no model '{model_name}' "
                    f"in app '{app_config.label}'."
                ) from exc
            register_config(model, options, source=f"{module_name}.{MODULE_SETTING}")


def get_mobile_configs():
    """
    Return the configs of the models shown on the phone, in registration order:
    models that opted into the ``mobile`` feature and have a ``MOBILE_MODELS``
    entry.
    """
    opted_in = FEATURE_REGISTRY.get(REGISTRY_KEY, [])
    configs = []
    for model in opted_in:
        config = _CONFIGS.get(model)
        if config is None:
            if model not in _WARNED_MISSING:
                _WARNED_MISSING.add(model)
                logger.warning(
                    "%s opted into the mobile feature but has no %s entry; skipped.",
                    model._meta.label,
                    MODULE_SETTING,
                )
            continue
        configs.append(config)
    return configs


def get_mobile_config(app_label, model_name):
    """Return the config for ``app_label.model_name`` when it is shown, else None."""
    for config in get_mobile_configs():
        meta = config.model._meta
        if meta.app_label == app_label and meta.model_name == model_name:
            return config
    return None


def get_mobile_config_for_key(key):
    """Return the config for an ``app_label.model_name`` key, else None."""
    if not key or "." not in key:
        return None
    app_label, model_name = key.split(".", 1)
    return get_mobile_config(app_label, model_name)
