"""
``_inherit_view`` extensions so Horilla inline edit and export work for
``cf_*`` fields.

EditFieldView / UpdateFieldView / CancelEditView resolve columns via
``model._meta.get_fields()``. Custom fields are not model columns, so these
extensions intercept ``cf_*`` before Horilla looks them up.

``ExportView`` is a single, concrete, model-agnostic view (routed directly
in ``urls.py``, never subclassed per app) — exactly the shape ``_inherit_view``
targets cleanly, so its two custom-fields hooks live here too, registered
declaratively instead of monkey-patched in ``custom_fields/export_hooks.py``.
This became possible once ``horilla.views.generic.TemplateView`` started
inheriting ``horilla.views.generic.base.View`` (the resolving base) — see
that class's docstring. ``HorillaBulkExportMixin.handle_export`` and the
module-level ``get_export_cell_value`` are registered declaratively too,
through ``MixinExtension``/``_inherit_mixin`` in
``custom_fields/mixin_extensions.py`` — the former is a bare mixin never
itself resolved via ``as_view()``/``get_*_class()``, and the latter is a
plain function, not a view method, so neither has a per-request resolution
point for ``_inherit_view`` to hook into.

``CustomFieldMultiStepFormKwargsExtension`` targets the shared
``HorillaMultiStepFormView`` **base** class instead of one concrete wizard —
``resolve_view_class()`` (the same resolver every ``_inherit_view``
registration goes through) checks a concrete-class match first, then falls
back to checking base classes in the MRO, so this one registration applies
to every wizard view automatically. See
``horilla/extension/view/resolve.py``'s ``_resolve_via_base_class``.
"""

from custom_fields.detail_hooks import (
    custom_field_selector_items,
    handle_custom_field_cancel_get,
    handle_custom_field_edit_get,
    handle_custom_field_update_post,
)
from custom_fields.list_hooks import attach_custom_field_values_to_objects
from custom_fields.utils import is_custom_field_name
from horilla.contrib.generics.views.helpers.edit_field import (
    CancelEditView,
    EditFieldView,
    UpdateFieldView,
)
from horilla.extension.view import ViewExtension


class CustomFieldEditFieldViewExtension(ViewExtension):
    """Open the inline editor for a custom field."""

    _inherit_view = "horilla.contrib.generics.views.helpers.edit_field.EditFieldView"

    def get(self, request, pk, field_name, app_label, model_name):
        if is_custom_field_name(field_name):
            return handle_custom_field_edit_get(
                request, pk, field_name, app_label, model_name
            )
        return EditFieldView.get(self, request, pk, field_name, app_label, model_name)


class CustomFieldUpdateFieldViewExtension(ViewExtension):
    """Save an inline custom-field value."""

    _inherit_view = "horilla.contrib.generics.views.helpers.edit_field.UpdateFieldView"

    def post(self, request, pk, field_name, app_label, model_name):
        if is_custom_field_name(field_name):
            return handle_custom_field_update_post(
                request, pk, field_name, app_label, model_name
            )
        return UpdateFieldView.post(
            self, request, pk, field_name, app_label, model_name
        )


class CustomFieldCancelEditViewExtension(ViewExtension):
    """Cancel inline edit of a custom field."""

    _inherit_view = "horilla.contrib.generics.views.helpers.edit_field.CancelEditView"

    def get(self, request, pk, field_name, app_label, model_name):
        if is_custom_field_name(field_name):
            return handle_custom_field_cancel_get(
                request, pk, field_name, app_label, model_name
            )
        return CancelEditView.get(self, request, pk, field_name, app_label, model_name)


class CustomFieldExportViewExtension(ViewExtension):
    """
    Add custom fields to the Select Columns to Export modal and write their
    values into exported files.

    Statically targets the one concrete ``ExportView`` (not per-model like
    ``custom_fields/extensions.py``/``detail_extensions.py`` — ``ExportView``
    itself already takes ``model`` as a runtime parameter), so real
    ``super()`` resolves correctly here even without the dynamic-registration
    template-copy trick those modules use.
    """

    _inherit_view = "horilla.contrib.core.views.export_data.ExportView"

    def get_available_models(self):
        from custom_fields.export_hooks import add_custom_fields_to_export_modules

        modules = super().get_available_models()
        try:
            add_custom_fields_to_export_modules(modules)
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "custom_fields: could not inject export columns"
            )
        return modules

    def export_model_data(
        self, model, export_format, queryset=None, selected_fields=None
    ):
        from custom_fields.export_hooks import (
            _append_custom_field_columns,
            _custom_fields_only_export,
            _MaterializedObjectList,
        )

        extras = custom_field_selector_items(model)
        extra_names = {name for _label, name in extras}
        extra_pairs = [
            (label, name)
            for label, name in extras
            if selected_fields is None or name in selected_fields
        ]
        if not extra_pairs:
            return super().export_model_data(
                model, export_format, queryset, selected_fields
            )

        objects = _MaterializedObjectList(
            model.objects.all() if queryset is None else queryset
        )
        attach_custom_field_values_to_objects(model, objects, extras=extras)

        model_selected = None
        if selected_fields is not None:
            model_selected = [
                name for name in selected_fields if name not in extra_names
            ]
            if not model_selected:
                return _custom_fields_only_export(
                    self, model, export_format, objects, extra_pairs
                )

        filename, data = super().export_model_data(
            model, export_format, objects, model_selected
        )
        if extra_pairs and export_format in ("csv", "xlsx"):
            data = _append_custom_field_columns(
                data, export_format, objects, extra_pairs
            )
        return filename, data


class CustomFieldListColumnSelectFormViewExtension(ViewExtension):
    """
    Add custom fields to the Add Column to List modal and relabel any
    ``cf_*`` entries in the saved column visibility after a successful save.

    Statically targets the one concrete ``ListColumnSelectFormView`` (routed
    directly in ``urls.py``, never subclassed per app), so real ``super()``
    resolves correctly here without the dynamic-registration template-copy
    trick ``custom_fields/extensions.py``/``detail_extensions.py`` use for
    per-model targets.
    """

    _inherit_view = (
        "horilla.contrib.generics.views.helpers.list_column.ListColumnSelectFormView"
    )

    def get_context_data(self, **kwargs):
        from custom_fields.list_hooks import add_custom_fields_to_column_selector

        context = super().get_context_data(**kwargs)
        try:
            add_custom_fields_to_column_selector(context)
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "custom_fields: could not inject list columns"
            )
        return context

    def form_valid(self, form):
        from custom_fields.list_hooks import relabel_saved_list_column_visibility

        response = super().form_valid(form)
        try:
            relabel_saved_list_column_visibility(self)
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "custom_fields: could not relabel saved list columns"
            )
        return response


class CustomFieldMultiStepFormKwargsExtension(ViewExtension):
    """
    Keep every selected Multiple Choice custom-field value across multi-step
    wizard steps.

    Targets the shared ``HorillaMultiStepFormView`` base class — every
    concrete wizard view (``LeadCreateWizard``, etc., across every CRM app,
    present and future) inherits ``get_form_kwargs`` from it, so a
    per-concrete-view registration would need to name every wizard in
    advance. ``horilla.extension.view.resolve.resolve_view_class`` — the
    same resolver every ``_inherit_view`` registration goes through at
    ``as_view()`` time — checks an exact match for the concrete class
    first, then falls back to checking each base class in the concrete
    class's MRO, so a registration on ``HorillaMultiStepFormView`` here is
    picked up by every concrete wizard automatically. See
    ``horilla/extension/view/resolve.py``'s ``_resolve_via_base_class``.
    """

    _inherit_view = "horilla.contrib.generics.views.multi_form.HorillaMultiStepFormView"

    def get_form_kwargs(self):
        from custom_fields.form_hooks import overlay_custom_choice_post_values

        kwargs = super().get_form_kwargs()
        if getattr(self.request, "method", "") != "POST":
            return kwargs
        form_data = kwargs.get("form_data")
        if form_data is None:
            return kwargs
        try:
            if overlay_custom_choice_post_values(self.request.POST, form_data):
                kwargs["form_data"] = form_data
                kwargs["data"] = form_data
                storage_key = getattr(self, "storage_key", None)
                if storage_key:
                    self.request.session[storage_key] = form_data
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "custom_fields: could not keep multi-select POST values"
            )
        return kwargs
