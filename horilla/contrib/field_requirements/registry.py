"""
Helpers for models whose field requiredness may be reconfigured by admins.

Requiredness is normally fixed in the model definition (``blank=False``), so an
installation cannot adapt a form to its own process without editing source.
Models opted in through the feature registry expose their fields so an
administrator can mark a field required or optional per company.

Opt-in is explicit: an app must call
``register_model_for_feature(..., features=["field_requirements"])``. That keeps
the settings page limited to models whose forms are known to tolerate the
change, rather than every model in the project.
"""

# Standard library imports
from itertools import chain

# First party imports (Horilla)
from horilla.db.models import Q
from horilla.registry.feature import FEATURE_REGISTRY
from horilla.utils.translation import gettext_lazy as _

REGISTRY_KEY = "field_requirement_models"

# Never configurable: bookkeeping columns the user does not fill in, and the
# primary key. Model-specific additions come from ``field_permissions_exclude``.
ALWAYS_EXCLUDED_FIELDS = {"id", "pk"}


def is_requirement_configurable(model):
    """Return True when `model` opted in to configurable requiredness."""
    if getattr(model, "_meta", None) is None:
        return False
    return model in FEATURE_REGISTRY.get(REGISTRY_KEY, [])


def get_configurable_models():
    """Return the registered model classes, sorted by verbose name."""
    models = list(FEATURE_REGISTRY.get(REGISTRY_KEY, []))
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

    return _(
        "%(field)s cannot be made optional because the database has no way to "
        "store an empty value for it. Allow null values on the field first."
    ) % {"field": model_field.verbose_name}


def limit_content_types():
    """Limit ContentType choices to models opted in for field requirements."""
    configured = FEATURE_REGISTRY.get(REGISTRY_KEY, [])
    if not configured:
        return Q(pk__in=[])

    filters = Q()
    for model in configured:
        filters |= Q(app_label=model._meta.app_label, model=model._meta.model_name)
    return filters
