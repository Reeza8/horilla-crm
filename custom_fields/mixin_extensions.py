"""
Inject custom fields into bare mixins/functions and a handful of concrete
classes with no other reachable extension point, through MixinExtension
(_inherit_mixin).

Most targets here are never dispatched via ``as_view()`` and never resolved
via a ``get_*_class()`` call — nothing calls either of those on a mixin that
is only ever composed in through ordinary Python inheritance, or on a plain
module-level function — so ``_inherit_view``/``_inherit_list``/
``_inherit_form`` etc. cannot reach them. See
``docs/horilla/extension/mixin/inherit.md`` for the full mechanism.

- ``HorillaListFilterFieldsMixin._get_model_fields`` — the "Filter Records"
  field dropdown. Mixed into every ``HorillaListView`` subclass.
- ``HorillaBulkExportMixin.handle_export`` — the actual export-file writer.
  Mixed into ``ExportView``.
- ``get_export_cell_value`` — a bare module-level function that renders one
  export cell.
- ``detail_field.render``/``._get_detail_field_defaults``/
  ``._ensure_json_serializable`` — bare module-level functions in the detail
  field selector/inline-edit module.
- ``ColumnSelectionForm.__init__`` — a plain ``django.forms.Form`` (not a
  ``HorillaModelForm``/``HorillaMultiStepForm``), routed to as a literal
  ``FormView.form_class`` attribute, never through ``get_form_class()`` /
  ``resolve_form_class()`` — so ``FormExtension`` cannot reach it either. Its
  own ``__init__`` also builds ``self.fields["visible_fields"].choices`` and
  immediately filters posted data against those same choices, in one method
  — there is no "after real `__init__`" hook (``FormExtension``'s
  ``setup_form_extension_fields()``) that runs early enough to add ``cf_*``
  choices before that filtering happens.
"""

import logging

from django.db.models.query import QuerySet
from django.utils.encoding import force_str

from custom_fields.detail_hooks import (
    add_custom_fields_to_selector_context,
    append_custom_fields_to_defaults,
    custom_field_selector_items,
    relabel_custom_field_pairs,
)
from custom_fields.export_hooks import (
    _install_export_properties,
    _uninstall_export_properties,
)
from custom_fields.filter_hooks import add_custom_fields_to_field_dicts
from custom_fields.list_hooks import attach_custom_field_values_to_objects
from horilla.extension.mixin import MixinExtension

logger = logging.getLogger(__name__)


class CustomFieldFilterFieldsExtension(MixinExtension):
    """Append custom-field dicts onto the Filter Records field dropdown."""

    _inherit_mixin = "horilla.contrib.generics.mixins.HorillaListFilterFieldsMixin"

    def _get_model_fields(self, original, include_properties=False, for_export=False):
        fields = list(
            original(include_properties=include_properties, for_export=for_export)
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
            add_custom_fields_to_field_dicts(fields, model, filterset_class)
        except Exception:
            logger.exception("custom_fields: could not inject filter fields")
        return fields


class CustomFieldBulkExportExtension(MixinExtension):
    """
    Attach custom-field values onto exported objects for the duration of
    ``handle_export``, so the writer's own row-building sees ``cf_*``
    attributes on each in-memory object.

    ``original`` (the real ``handle_export`` body) builds its ``queryset``
    from a local variable and reads it with a plain ``for obj in queryset:``
    loop — not a method call, so there is no method to override to reach
    the objects before that loop uses them, and the queryset itself is
    never passed back out to the caller. The only way to attach ``cf_*``
    values onto each object before Horilla's own row-building code sees it
    is to intercept iteration itself for the duration of this one call —
    scoped with a save/restore around the ``original(...)`` call below, and
    guarded to only touch querysets of the target ``model``, on the same
    principle ``_install_export_properties``/``_uninstall_export_properties``
    already use for the model's temporary export properties.
    """

    _inherit_mixin = (
        "horilla.contrib.generics.views.toolkit.bulk_export.HorillaBulkExportMixin"
    )

    def handle_export(self, original, record_ids, columns, export_format):
        model = getattr(self, "model", None)
        extras = custom_field_selector_items(model) if model is not None else []
        if not extras:
            return original(record_ids, columns, export_format)

        installed, old_labels = _install_export_properties(model, extras)
        orig_iter = QuerySet.__iter__

        def attaching_iter(qs):
            iterator = orig_iter(qs)
            if getattr(qs, "model", None) is not model:
                return iterator
            items = list(iterator)
            try:
                attach_custom_field_values_to_objects(model, items, extras=extras)
            except Exception:
                logger.exception("custom_fields: could not attach export values")
            return iter(items)

        QuerySet.__iter__ = attaching_iter
        try:
            return original(record_ids, columns, export_format)
        finally:
            QuerySet.__iter__ = orig_iter
            _uninstall_export_properties(model, installed, old_labels)


class CustomFieldExportCellExtension(MixinExtension):
    """Render ``cf_*`` export cells directly from the object's attached value."""

    _inherit_mixin = "horilla.contrib.core.views.export_data.get_export_cell_value"

    def get_export_cell_value(self, original, obj, field_name, field, user):
        if str(field_name).startswith("cf_"):
            value = obj.__dict__.get(field_name, "")
            return "" if value is None else str(value)
        return original(obj, field_name, field, user)


class CustomFieldDetailRenderExtension(MixinExtension):
    """Inject custom fields into the "Change Detail View Fields" selector modal."""

    _inherit_mixin = "horilla.contrib.generics.views.helpers.detail_field.render"

    def render(self, original, request, template_name, context=None, *args, **kwargs):
        if template_name == "add_field_to_detail.html" and context is not None:
            add_custom_fields_to_selector_context(context, request)
        return original(request, template_name, context, *args, **kwargs)


class CustomFieldDetailDefaultsExtension(MixinExtension):
    """Add custom fields to the default header/detail field lists."""

    _inherit_mixin = (
        "horilla.contrib.generics.views.helpers.detail_field._get_detail_field_defaults"
    )

    def _get_detail_field_defaults(self, original, model, request):
        default_header, default_details = original(model, request)
        try:
            return append_custom_fields_to_defaults(
                model, default_header, default_details
            )
        except Exception:
            logger.exception("custom_fields: could not add defaults for %s", model)
            return default_header, default_details


class CustomFieldDetailEnsureSerializableExtension(MixinExtension):
    """Relabel ``cf_*`` pairs to their live custom-field label."""

    _inherit_mixin = (
        "horilla.contrib.generics.views.helpers.detail_field._ensure_json_serializable"
    )

    def _ensure_json_serializable(self, original, fields_list):
        return relabel_custom_field_pairs(original(fields_list))


class CustomFieldColumnSelectionFormExtension(MixinExtension):
    """
    Include ``cf_*`` in ``ColumnSelectionForm``'s ``visible_fields`` choices
    so posted custom-field columns are not dropped.

    Patches ``__init__`` directly (not through ``FormExtension`` — see the
    module docstring): the real ``__init__`` builds
    ``self.fields["visible_fields"].choices`` from the model's own fields
    and, in the same call, filters any posted ``visible_fields`` down to
    just those choices — so custom-field choices must exist *before* that
    filtering runs, not after it (which is the earliest
    ``FormExtension.setup_form_extension_fields()`` could run).
    """

    _inherit_mixin = "horilla.contrib.generics.forms.generics.ColumnSelectionForm"

    def __init__(self, original, *args, **kwargs):
        model = kwargs.get("model")
        original_data = kwargs.get("data")
        if original_data is None and args:
            original_data = args[0]

        original(*args, **kwargs)

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
