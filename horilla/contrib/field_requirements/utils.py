"""Resolution helpers for per-company field-requirement overrides."""

# First party imports (Horilla)
from horilla.contrib.core.models import HorillaContentType
from horilla.contrib.utils.middlewares import get_current_request
from horilla.core.exceptions import FieldDoesNotExist

# Local imports
from .models import FieldRequirement
from .registry import can_relax_requirement, is_requirement_configurable

_REQUEST_CACHE_ATTR = "_field_requirement_overrides"


def get_field_requirements_for_model(model):
    """
    Return configured requiredness overrides for ``model``.

    Returns ``{field_name: bool}``, empty when nothing is configured or the
    model has not opted in. Scoped to the active company through the model's
    default manager. Fields absent from the dictionary keep the requiredness
    derived from the model definition.

    Overrides that could not be honoured are dropped here rather than applied:
    a field is only relaxed when the database can store an empty value for it,
    so a stale or imported row can never turn into an IntegrityError on save.

    Results are cached on the current request so a page with several forms for
    the same model does not re-query.
    """
    if model is None or not is_requirement_configurable(model):
        return {}

    cache_key = model._meta.label_lower
    request = get_current_request()
    if request is not None:
        cache = getattr(request, _REQUEST_CACHE_ATTR, None)
        if cache is None:
            cache = {}
            setattr(request, _REQUEST_CACHE_ATTR, cache)
        if cache_key in cache:
            return cache[cache_key]

    content_type = HorillaContentType.objects.get_for_model(model)
    requirements = {}
    rows = FieldRequirement.objects.filter(
        content_type=content_type, is_active=True
    ).values_list("field_name", "is_required")

    for field_name, is_required in rows:
        if is_required:
            requirements[field_name] = True
            continue
        try:
            model_field = model._meta.get_field(field_name)
        except FieldDoesNotExist:
            continue
        if can_relax_requirement(model_field):
            requirements[field_name] = False

    if request is not None:
        getattr(request, _REQUEST_CACHE_ATTR)[cache_key] = requirements

    return requirements
