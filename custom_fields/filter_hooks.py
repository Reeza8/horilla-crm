"""
Runtime hooks so custom fields appear in Horilla's Filter Records panel
and actually filter the queryset.

Horilla's filter UI only knows about model columns. This module patches
those call sites from the custom_fields app so we do not edit Horilla sources.
"""

import logging
from decimal import Decimal, InvalidOperation

from horilla.contrib.core.models import HorillaContentType
from horilla.db.models import Q

from custom_fields.models import CustomFieldValue, parse_choice_values
from custom_fields.utils import (
    custom_field_form_name,
    get_custom_field_definitions,
    get_definition_by_form_name,
    is_custom_field_name,
    safe_custom_field_label,
)

logger = logging.getLogger(__name__)

_PATCHED = False

FILTER_TYPE_MAP = {
    "small_text": "text",
    "large_text": "text",
    "number": "decimal",
    "choice": "choice",
}


def custom_field_filter_dicts(model, filterset_class=None):
    """Return Horilla filter-field dicts for the model's custom fields."""
    from horilla.contrib.generics.filters import HorillaFilterSet

    getter = HorillaFilterSet.get_operators_for_field
    if filterset_class is not None:
        getter = getattr(
            filterset_class, "get_operators_for_field", getter
        )

    field_dicts = []
    for defn in get_custom_field_definitions(model):
        mapped = FILTER_TYPE_MAP.get(defn.field_type, "text")
        choices = []
        if defn.field_type == "choice":
            choices = [{"value": c, "label": c} for c in defn.get_choices_list()]
        field_dicts.append(
            {
                "name": custom_field_form_name(defn),
                "type": mapped,
                "verbose_name": safe_custom_field_label(defn),
                "choices": choices,
                "operators": getter(mapped),
                "model": None,
                "app_label": None,
            }
        )
    return field_dicts


def inject_custom_fields_into_field_dicts(fields, model, filterset_class=None):
    """Append custom-field dicts onto a Horilla ``_get_model_fields`` list."""
    existing = {item.get("name") for item in fields}
    for extra in custom_field_filter_dicts(model, filterset_class):
        if extra["name"] not in existing:
            fields.append(extra)
            existing.add(extra["name"])
    return fields


def _to_decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _filled_values_qs(base, numeric, choice=False):
    if numeric:
        return base.filter(value_number__isnull=False)
    qs = base.exclude(value_text="").exclude(value_text__isnull=True)
    if choice:
        qs = qs.exclude(value_text="[]")
    return qs


def custom_field_row_q(model, field_name, operator, i, values, start_values, end_values):
    """Build a ``Q(pk__in=...)`` (or its inverse) for one custom-field filter row."""
    defn = get_definition_by_form_name(model, field_name)
    if defn is None:
        return None

    value = values[i] if i < len(values) else None
    start_value = start_values[i] if i < len(start_values) else None
    end_value = end_values[i] if i < len(end_values) else None

    match = matching_object_ids(model, defn, operator, value, start_value, end_value)
    if match is None:
        return None
    include, ids = match
    id_list = list(ids)
    if include:
        return Q(pk__in=id_list)
    return ~Q(pk__in=id_list)


def matching_object_ids(model, defn, operator, value, start_value, end_value):
    """
    Return ``(include, object_ids)`` for a custom-field filter.

    ``include`` True means ``Q(pk__in=ids)``; False means ``~Q(pk__in=ids)``.
    """
    ct = HorillaContentType.objects.get_for_model(model)
    base = CustomFieldValue.objects.filter(content_type=ct, field_definition=defn)
    numeric = defn.field_type == "number"
    choice = defn.field_type == "choice"
    value_key = "value_number" if numeric else "value_text"
    filled = _filled_values_qs(base, numeric, choice=choice)

    if operator == "isnull":
        return (False, filled.values_list("object_id", flat=True))
    if operator == "isnotnull":
        return (True, filled.values_list("object_id", flat=True))

    if choice and operator in ("exact", "ne"):
        if value in (None, ""):
            return None
        wanted = [item for item in str(value).split(",") if item]
        matching_ids = []
        for object_id, stored in base.values_list("object_id", "value_text"):
            selected = parse_choice_values(stored)
            if any(item in selected for item in wanted):
                matching_ids.append(object_id)
        if operator == "exact":
            return (True, matching_ids)
        return (False, matching_ids)

    if operator == "between":
        if not numeric:
            return None
        qs = filled
        start_num = _to_decimal(start_value) if start_value not in (None, "") else None
        end_num = _to_decimal(end_value) if end_value not in (None, "") else None
        if start_num is None and end_num is None:
            return None
        if start_num is not None:
            qs = qs.filter(value_number__gte=start_num)
        if end_num is not None:
            qs = qs.filter(value_number__lte=end_num)
        return (True, qs.values_list("object_id", flat=True))

    if operator == "ne":
        if value in (None, ""):
            return None
        if numeric:
            number = _to_decimal(value)
            if number is None:
                return None
            equal_ids = filled.filter(value_number=number).values_list(
                "object_id", flat=True
            )
        else:
            equal_ids = base.filter(value_text=value).values_list("object_id", flat=True)
        return (False, equal_ids)

    if value in (None, ""):
        return None

    if operator == "exact":
        if numeric:
            number = _to_decimal(value)
            if number is None:
                return None
            qs = filled.filter(value_number=number)
        else:
            value_list = [item for item in str(value).split(",") if item]
            if not value_list:
                return None
            if len(value_list) > 1:
                qs = base.filter(value_text__in=value_list)
            else:
                qs = base.filter(value_text__exact=value_list[0])
        return (True, qs.values_list("object_id", flat=True))

    lookup_suffix = {
        "icontains": "icontains",
        "istartswith": "istartswith",
        "iendswith": "iendswith",
        "gt": "gt",
        "lt": "lt",
        "gte": "gte",
        "lte": "lte",
    }.get(operator)
    if not lookup_suffix:
        return None

    filter_value = _to_decimal(value) if numeric else value
    if numeric and filter_value is None:
        return None
    qs = (filled if numeric else base).filter(
        **{f"{value_key}__{lookup_suffix}": filter_value}
    )
    return (True, qs.values_list("object_id", flat=True))


def install_filter_patches():
    """Monkey-patch Horilla filter helpers without editing their files."""
    global _PATCHED
    if _PATCHED:
        return

    from horilla.contrib.generics.filters import HorillaFilterSet
    from horilla.contrib.generics.mixins import HorillaListFilterFieldsMixin

    original_get_model_fields = HorillaListFilterFieldsMixin._get_model_fields
    original_build_row_q = HorillaFilterSet._build_row_q

    def patched_get_model_fields(self, include_properties=False, for_export=False):
        fields = list(
            original_get_model_fields(
                self, include_properties=include_properties, for_export=for_export
            )
        )
        model = getattr(self, "model", None)
        if model is None:
            return fields
        try:
            filterset_class = None
            if hasattr(self, "get_filterset_class"):
                try:
                    filterset_class = self.get_filterset_class()
                except Exception:
                    filterset_class = getattr(self, "filterset_class", None)
            else:
                filterset_class = getattr(self, "filterset_class", None)
            inject_custom_fields_into_field_dicts(fields, model, filterset_class)
        except Exception:
            logger.exception("custom_fields: could not inject filter fields")
        return fields

    def patched_build_row_q(
        self, model, field, operator, i, values, start_values, end_values
    ):
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
        return original_build_row_q(
            self, model, field, operator, i, values, start_values, end_values
        )

    HorillaListFilterFieldsMixin._get_model_fields = patched_get_model_fields
    HorillaFilterSet._build_row_q = patched_build_row_q
    _PATCHED = True
