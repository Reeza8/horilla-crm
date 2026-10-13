"""Shared field-resolution and filter-value helpers for the reports engine.

Centralizes the "dotted related-field" lookup (e.g. "stage__stage_type") so
filters, row/column groups, and verbose-name lookups can all traverse exactly
one level of a forward ForeignKey/OneToOneField relation, in addition to
plain direct fields on the report's own model. Also defines a small,
app-agnostic registry for "virtual fields" — values computed at query time
via annotate() (e.g. "days_open" = now() - created_at) that have no backing
database column. This module has no knowledge of which apps use it; any app
registers its own virtual fields via `register_virtual_field(...)`, the same
way models register for report eligibility via `register_model_for_feature`.
"""

# Standard library imports
import json
from datetime import timedelta

# Third-party imports (Django)
from django.core.exceptions import FieldDoesNotExist
from django.db.models import (
    DecimalField,
    DurationField,
    FloatField,
    ForeignKey,
    IntegerField,
    OneToOneField,
)

from horilla.views.generic import View

# Populated exclusively via register_virtual_field() — this module defines
# no virtual fields of its own, only the mechanism.
_VIRTUAL_FIELD_REGISTRY = {}


class VirtualField:
    """Duck-types the small subset of Django Field attributes the reports
    engine reads (verbose_name/choices/related_model), for a computed value
    that isn't a real column. `annotation` is what gets passed to
    queryset.annotate(field_name=annotation). `show_in_detail` lets the field
    also appear as a column in the report detail table (the rows carry the
    annotated value)."""

    related_model = None
    is_relation = False
    editable = True

    def __init__(
        self, name, verbose_name, annotation, choices=None, show_in_detail=False
    ):
        self.name = name
        self.verbose_name = verbose_name
        self.annotation = annotation
        self.choices = choices
        self.show_in_detail = show_in_detail
        self.output_field = getattr(annotation, "output_field", None)


def register_virtual_field(
    app_label,
    model_name,
    field_name,
    verbose_name,
    annotation,
    choices=None,
    show_in_detail=False,
):
    """Register a computed field for reports on app_label.model_name.

    `annotation` is any Django ORM expression suitable for
    `queryset.annotate(field_name=annotation)`, e.g.
    `ExpressionWrapper(Now() - F("created_at"), output_field=DurationField())`
    for a "days since created" value. Pass `show_in_detail=True` to also show
    it as a column of the report detail table. Call this from the owning
    app's own `registration.py`, not from this module.
    """
    key = f"{app_label}.{model_name.lower()}"
    _VIRTUAL_FIELD_REGISTRY.setdefault(key, {})[field_name] = VirtualField(
        field_name,
        verbose_name,
        annotation,
        choices=choices,
        show_in_detail=show_in_detail,
    )


class ReportFieldProvider(View):
    """
    Extension seam for report fields that depend on who is asking.

    ``register_virtual_field`` is process-wide and static. Fields created at
    runtime, or visible to some users only (e.g. user-defined fields), come
    from an ``_inherit_view`` extension overriding :meth:`get_virtual_fields`,
    resolved through :func:`get_report_field_provider` (the same late-binding
    pattern as ``ExtraFieldsProvider``). Never dispatched via ``as_view()``.
    """

    def get_virtual_fields(self, model_class):
        """Return ``{field_name: VirtualField}`` for ``model_class``."""
        return {}


def get_report_field_provider():
    """Return a ReportFieldProvider with ``_inherit_view`` extensions applied."""
    from horilla.extension.view.resolve import resolve_view_class

    return resolve_view_class(ReportFieldProvider)()


def _virtual_fields_for(model_class):
    """Return the virtual fields registered or provided for model_class."""
    key = f"{model_class._meta.app_label}.{model_class._meta.model_name}"
    fields = dict(_VIRTUAL_FIELD_REGISTRY.get(key, {}))
    fields.update(get_report_field_provider().get_virtual_fields(model_class))
    return fields


def detail_virtual_fields(model_class):
    """Column-picker entries for virtual fields that can be detail table columns.

    Same dict shape as the entries built from model fields for the report
    panel's Columns tab: name / verbose_name / field_type.
    """
    return [
        {
            "name": name,
            "verbose_name": str(virtual_field.verbose_name),
            "field_type": "VirtualField",
        }
        for name, virtual_field in _virtual_fields_for(model_class).items()
        if virtual_field.show_in_detail
    ]


def virtual_field_choices(model_class, purpose):
    """``(name, verbose_name)`` pairs of virtual fields for a field picker.

    ``purpose`` is "detail" (shown as a table column), "grouping" (has
    choices, so values can be grouped) or "numeric" (computed number, so it can
    be summed or averaged).
    """
    numeric_types = (DecimalField, FloatField, IntegerField)
    choices = []
    for name, virtual_field in _virtual_fields_for(model_class).items():
        if purpose == "detail":
            suitable = virtual_field.show_in_detail
        elif purpose == "grouping":
            suitable = bool(virtual_field.choices)
        else:
            suitable = isinstance(virtual_field.output_field, numeric_types)
        if suitable:
            choices.append((name, str(virtual_field.verbose_name)))
    return choices


def get_virtual_field(model_class, field_name):
    """Return the VirtualField for field_name on model_class, or None."""
    return _virtual_fields_for(model_class).get(field_name)


def is_duration_virtual_field(model_class, field_name):
    """True if field_name is a registered virtual field whose annotation
    produces a DurationField (timedelta) value — e.g. "days_open", as
    opposed to a date/datetime-producing virtual field like "close_month"."""
    virtual_field = get_virtual_field(model_class, field_name)
    return virtual_field is not None and isinstance(
        virtual_field.output_field, DurationField
    )


def annotate_virtual_fields(queryset, model_class, field_names):
    """Annotate queryset with any virtual fields referenced in field_names.

    Safe to call with a mix of real and virtual field names — only the
    virtual ones (present in the registry) get annotated; unknown/real names
    are ignored here and resolved normally by the ORM.
    """
    virtual_fields = _virtual_fields_for(model_class)
    to_annotate = {
        name: virtual_fields[name].annotation
        for name in field_names
        if name in virtual_fields
    }
    if to_annotate:
        queryset = queryset.annotate(**to_annotate)
    return queryset


def resolve_report_field(model_class, field_name):
    """Resolve a field name (optionally one level of "relation__field") on model_class.

    Supports exactly one level of forward FK/OneToOne traversal, e.g.
    "stage__stage_type" resolves to OpportunityStage.stage_type via
    Opportunity.stage. Also resolves registered virtual fields (e.g.
    "days_open"), returning a VirtualField in place of a real Django Field.
    Raises FieldDoesNotExist if the field, or the relation it traverses,
    isn't a real forward relation field and isn't a registered virtual field.
    """
    virtual_field = get_virtual_field(model_class, field_name)
    if virtual_field is not None:
        return virtual_field
    if "__" in field_name:
        relation_name, remote_name = field_name.split("__", 1)
        if "__" in remote_name:
            raise FieldDoesNotExist(
                f"Related field traversal is limited to one level: '{field_name}'"
            )
        relation_field = model_class._meta.get_field(relation_name)
        if not isinstance(relation_field, (ForeignKey, OneToOneField)):
            raise FieldDoesNotExist(
                f"'{relation_name}' is not a forward relation on {model_class.__name__}"
            )
        return relation_field.related_model._meta.get_field(remote_name)
    return model_class._meta.get_field(field_name)


def coerce_virtual_filter_value(model_class, field_name, value):
    """Coerce a raw (always-string) filter value to the type a virtual
    field's annotation actually stores at the DB level.

    Currently only DurationField-backed virtual fields need this: the
    filter UI collects a plain number of days (e.g. "3"), but the ORM
    requires an actual timedelta to compare against a DurationField.
    Non-duration virtual fields, or non-virtual fields, are returned as-is.
    """
    if not is_duration_virtual_field(model_class, field_name):
        return value
    try:
        return timedelta(days=float(value))
    except (TypeError, ValueError):
        return value


def parse_in_operator_value(value):
    """Parse an 'in' filter value from a comma-separated or JSON-list string into a list."""
    if isinstance(value, list):
        return value
    value = (value or "").strip()
    if not value:
        return []
    if value.startswith("[") and value.endswith("]"):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return [v.strip() for v in value.split(",") if v.strip()]
