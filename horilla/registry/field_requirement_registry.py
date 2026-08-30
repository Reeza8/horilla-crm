"""
Registry for models whose field requiredness may be reconfigured by admins.

Requiredness is normally fixed in the model definition (``blank=False``), which
means an installation cannot adapt a form to its own process without editing
source. Models registered here expose their fields to the Field Requirements
settings page, where an admin may mark a field required or optional per company.

Opting in is explicit: a model must be decorated with
:func:`configurable_field_requirements`. That keeps the settings page limited to
models whose forms are known to tolerate the change, rather than every model in
the project.
"""

# Standard library imports
from itertools import chain

CONFIGURABLE_REQUIREMENT_MODELS = set()

# Never configurable: bookkeeping columns the user does not fill in, and the
# primary key. Model-specific additions come from ``field_permissions_exclude``.
ALWAYS_EXCLUDED_FIELDS = {"id", "pk"}


def configurable_field_requirements(cls):
    """Register a model so its field requiredness can be configured.

    Usage::

        @configurable_field_requirements
        class Lead(HorillaCoreModel):
            ...
    """
    CONFIGURABLE_REQUIREMENT_MODELS.add(cls._meta.label_lower)
    return cls


def is_requirement_configurable(model):
    """Return True when `model` opted in to configurable requiredness."""
    meta = getattr(model, "_meta", None)
    if meta is None:
        return False
    return meta.label_lower in CONFIGURABLE_REQUIREMENT_MODELS


def get_configurable_models():
    """Return the registered model classes, sorted by verbose name.

    Resolved lazily through the app registry so importing this module never
    depends on model import order.
    """
    from horilla.apps import apps

    models = []
    for label in CONFIGURABLE_REQUIREMENT_MODELS:
        try:
            models.append(apps.get_model(label))
        except LookupError:
            # A registered model may be absent when its app is uninstalled.
            continue
    return sorted(models, key=lambda model: str(model._meta.verbose_name).lower())


def get_excluded_fields(model):
    """Return field names that must never be configurable on `model`."""
    return set(
        chain(
            ALWAYS_EXCLUDED_FIELDS,
            getattr(model, "field_permissions_exclude", []) or [],
            getattr(model, "requirement_config_exclude", []) or [],
        )
    )


def get_configurable_fields(model):
    """Return the model fields whose requiredness may be configured.

    Limited to concrete, editable, user-facing columns. Many-to-many fields are
    left out because their emptiness is not expressed by ``blank`` in a way the
    form layer can relax safely.
    """
    if not is_requirement_configurable(model):
        return []

    excluded = get_excluded_fields(model)
    fields = []
    for field in model._meta.get_fields():
        if not getattr(field, "concrete", False):
            continue
        if field.primary_key or field.many_to_many:
            continue
        if not getattr(field, "editable", False):
            continue
        if field.name in excluded:
            continue
        fields.append(field)
    return sorted(fields, key=lambda field: str(field.verbose_name).lower())


def can_relax_requirement(model_field):
    """Return whether `model_field` can be made optional without breaking saves.

    A form may only stop requiring a value if the column has somewhere to put
    the absence of one:

    * ``null=True`` stores NULL;
    * text-like columns store the empty string (Django reports this as
      ``empty_strings_allowed``, which is False for numeric, date, boolean and
      foreign key columns);
    * a column with a default falls back to that default.

    Without one of those, clearing the field would raise IntegrityError at
    save time, so the settings page refuses the change instead.
    """
    if model_field is None:
        return False
    if getattr(model_field, "null", False):
        return True
    if getattr(model_field, "empty_strings_allowed", False):
        return True
    has_default = getattr(model_field, "has_default", None)
    return bool(has_default and has_default())


def get_relax_blocked_reason(model_field):
    """Return a human-readable reason a field cannot be made optional.

    Returns None when the field can be relaxed.
    """
    if can_relax_requirement(model_field):
        return None

    from horilla.utils.translation import gettext_lazy as _

    return _(
        "%(field)s cannot be made optional because the database has no way to "
        "store an empty value for it. Allow null values on the field first."
    ) % {"field": model_field.verbose_name}
