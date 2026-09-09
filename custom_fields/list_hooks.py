"""
Runtime hooks for Horilla list-column picker and list-cell values.

Horilla's Add Column to List modal only knows about model columns. This
module patches those call sites from the custom_fields app so we do not
edit Horilla sources.
"""

import logging

from django.core.cache import cache
from django.utils.encoding import force_str

from custom_fields.detail_hooks import (
    _partition_selector_lists,
    custom_field_selector_items,
    field_names_from_list,
    relabel_custom_field_pairs,
)
from custom_fields.models import CustomFieldValue
from custom_fields.utils import (
    assign_custom_field_attr,
    custom_field_form_name,
    format_custom_field_display,
    get_custom_field_definitions,
)
from horilla.apps import apps
from horilla.contrib.core.models import HorillaContentType, ListColumnVisibility

logger = logging.getLogger(__name__)

_PATCHED = False


def inject_custom_fields_into_column_selector(context):
    """Add custom fields to the Add Column to List modal lists."""
    app_label = context.get("app_label")
    model_name = context.get("model_name")
    if not app_label or not model_name:
        return context
    try:
        model = apps.get_model(app_label, model_name)
    except LookupError:
        return context

    extras = custom_field_selector_items(model)
    if not extras:
        return context

    visible_fields, available_fields = _partition_selector_lists(
        context.get("visible_fields"),
        context.get("available_fields"),
        extras,
    )
    context["visible_fields"] = visible_fields
    context["available_fields"] = available_fields
    return context


def relabel_saved_list_column_visibility(view):
    """Replace stored ``cf_*`` labels with the definition name after save."""
    request = getattr(view, "request", None)
    if request is None:
        return
    app_label = request.POST.get("app_label")
    model_name = request.POST.get("model_name")
    url_name = request.POST.get("url_name")
    if model_name:
        model_name = model_name.strip('"')
        if "." in model_name:
            model_name = model_name.split(".")[-1]
    if not app_label or not model_name:
        return

    from horilla.contrib.generics.views.helpers.list_column import _get_path_context

    path_context = _get_path_context(request)
    visibility = ListColumnVisibility.all_objects.filter(
        user=request.user,
        app_label=app_label,
        model_name=model_name,
        context=path_context,
        url_name=url_name,
    ).first()
    if visibility is None:
        return

    visibility.visible_fields = relabel_custom_field_pairs(visibility.visible_fields)
    visibility.removed_custom_fields = relabel_custom_field_pairs(
        visibility.removed_custom_fields
    )
    visibility.save(update_fields=["visible_fields", "removed_custom_fields"])

    cache_key = (
        f"visible_columns_{request.user.id}_{app_label}_{model_name}_"
        f"{path_context}_{url_name}"
    )
    cache.delete(cache_key)


def attach_custom_field_values_to_objects(model, objects, extras=None):
    """Set ``cf_<id>`` attributes on each object so list cells can render."""
    if extras is None:
        extras = custom_field_selector_items(model)
    if not extras:
        return

    items = []
    for obj in objects or []:
        if getattr(obj, "pk", None) is not None:
            items.append(obj)
    if not items:
        return

    keys = [item[1] for item in extras]
    for obj in items:
        for key in keys:
            assign_custom_field_attr(obj, key, "")

    ct = HorillaContentType.objects.get_for_model(model)
    pks = [obj.pk for obj in items]
    definitions = list(get_custom_field_definitions(model))
    values = CustomFieldValue.objects.filter(
        content_type=ct,
        object_id__in=pks,
        field_definition__in=definitions,
    ).select_related("field_definition")

    by_pk = {}
    for cfv in values:
        key = custom_field_form_name(cfv.field_definition)
        val = cfv.get_value()
        by_pk.setdefault(cfv.object_id, {})[key] = format_custom_field_display(
            cfv.field_definition, val
        )

    for obj in items:
        for key, val in by_pk.get(obj.pk, {}).items():
            assign_custom_field_attr(obj, key, val)


def _saved_list_column_names(view):
    """Return saved visible column names, or None when the user has no preference."""
    request = getattr(view, "request", None)
    model = getattr(view, "model", None)
    if request is None or model is None:
        return None
    if not getattr(view, "list_column_visibility", False):
        return None
    from horilla.contrib.generics.views.helpers.list_column import _get_path_context
    from horilla.urls import resolve as resolve_url

    try:
        url_name = resolve_url(request.path_info).url_name
    except Exception:
        url_name = ""
    visibility = ListColumnVisibility.all_objects.filter(
        user=request.user,
        model_name=model.__name__,
        app_label=model._meta.app_label,
        context=_get_path_context(request),
        url_name=url_name,
    ).first()
    if visibility is None:
        return None
    return field_names_from_list(visibility.visible_fields)


def ensure_saved_custom_field_columns(view, context):
    """Put selected ``cf_*`` columns back if Horilla omitted them from the table."""
    model = getattr(view, "model", None)
    extras = custom_field_selector_items(model) if model is not None else []
    if not extras:
        return context
    extra_by_name = {name: label for label, name in extras}
    saved_names = _saved_list_column_names(view)
    if saved_names is None:
        return context
    columns = list(context.get("columns") or [])
    col_names = [
        str(col[1])
        for col in columns
        if isinstance(col, (list, tuple)) and len(col) >= 2
    ]
    for name in saved_names:
        if name in extra_by_name and name not in col_names:
            columns.append([extra_by_name[name], name])
            col_names.append(name)
    relabeled = []
    for col in columns:
        if isinstance(col, (list, tuple)) and len(col) >= 2 and col[1] in extra_by_name:
            relabeled.append([extra_by_name[col[1]], col[1]])
        else:
            relabeled.append(col)
    context["columns"] = relabeled
    return context


def attach_custom_fields_to_list_context(view, context):
    """Attach values on the current page and skip sorting on ``cf_*`` columns."""
    model = getattr(view, "model", None)
    if model is None:
        return context
    extras = custom_field_selector_items(model)
    objects = context.get("queryset")
    if objects is None:
        objects = context.get("object_list")
    attach_custom_field_values_to_objects(model, objects, extras=extras)
    ensure_saved_custom_field_columns(view, context)
    if extras:
        exclude = list(context.get("exclude_columns_from_sorting") or [])
        for _, name in extras:
            if name not in exclude:
                exclude.append(name)
        context["exclude_columns_from_sorting"] = exclude
    return context


def _patch_column_selection_form():
    """Include ``cf_*`` in column-form choices so save does not drop them."""
    from horilla.contrib.generics.forms.generics import ColumnSelectionForm

    if getattr(ColumnSelectionForm.__init__, "_custom_fields_patched", False):
        return

    original_init = ColumnSelectionForm.__init__

    def patched_init(self, *args, **kwargs):
        model = kwargs.get("model")
        original_data = kwargs.get("data")
        if original_data is None and args:
            original_data = args[0]
        original_init(self, *args, **kwargs)
        if model is None:
            return
        extras = custom_field_selector_items(model)
        if not extras:
            return
        extra_by_name = {name: force_str(label) for label, name in extras}
        field = self.fields.get("visible_fields")
        if field is not None:
            existing = {choice[0] for choice in field.choices}
            new_choices = list(field.choices)
            for name, label in extra_by_name.items():
                if name not in existing:
                    new_choices.append((name, label))
            field.choices = new_choices
        if original_data is None or not hasattr(original_data, "getlist"):
            return
        if field is None or getattr(self, "data", None) is None:
            return
        allowed = {choice[0] for choice in field.choices}
        posted = original_data.getlist("visible_fields")
        kept = [name for name in posted if name in allowed]
        current = (
            list(self.data.getlist("visible_fields"))
            if hasattr(self.data, "getlist")
            else []
        )
        if kept == current:
            return
        data = self.data.copy()
        if hasattr(data, "setlist"):
            data.setlist("visible_fields", kept)
        else:
            data["visible_fields"] = kept
        self.data = data

    patched_init._custom_fields_patched = True
    ColumnSelectionForm.__init__ = patched_init


def install_list_column_patches():
    """Monkey-patch Horilla list-column helpers without editing their files."""
    global _PATCHED
    if _PATCHED:
        return

    from horilla.contrib.generics.views.helpers.list_column import (
        ListColumnSelectFormView,
    )
    from horilla.contrib.generics.views.list import HorillaListView

    _patch_column_selection_form()

    original_get_context_data = ListColumnSelectFormView.get_context_data
    original_form_valid = ListColumnSelectFormView.form_valid
    original_list_get_context_data = HorillaListView.get_context_data

    def patched_get_context_data(self, **kwargs):
        context = original_get_context_data(self, **kwargs)
        try:
            inject_custom_fields_into_column_selector(context)
        except Exception:
            logger.exception("custom_fields: could not inject list columns")
        return context

    def patched_form_valid(self, form):
        response = original_form_valid(self, form)
        try:
            relabel_saved_list_column_visibility(self)
        except Exception:
            logger.exception("custom_fields: could not relabel saved list columns")
        return response

    def patched_list_get_context_data(self, **kwargs):
        context = original_list_get_context_data(self, **kwargs)
        try:
            attach_custom_fields_to_list_context(self, context)
        except Exception:
            logger.exception("custom_fields: could not attach list custom fields")
        return context

    ListColumnSelectFormView.get_context_data = patched_get_context_data
    ListColumnSelectFormView.form_valid = patched_form_valid
    HorillaListView.get_context_data = patched_list_get_context_data
    _PATCHED = True
