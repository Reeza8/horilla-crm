"""
Inject duplicate-checking behavior into shared Horilla view base classes
through ViewExtension (_inherit_view), targeting each base class directly.

``HorillaSingleFormView``, ``HorillaMultiStepFormView``, and
``HorillaDetailTabView`` are shared base classes every concrete form/detail
view across every app inherits — there is no single concrete class to name.
``resolve_view_class()`` (the same resolver every ``_inherit_view``
registration goes through at ``as_view()`` time) checks an exact match for
the concrete class first, then falls back to checking each base class in
the concrete class's MRO, so a registration on one of these bases here is
picked up by every concrete subclass automatically — present and future,
across every app — the same way registering directly on one concrete view
would be for just that view. See
``horilla/extension/view/resolve.py``'s ``_resolve_via_base_class`` and
``docs/horilla/extension/inherit.md``'s "Targeting a shared base class".

``UpdateAllFieldsView`` (the "Edit Details" bulk-edit save endpoint) is
itself a single, concrete, model-agnostic view (routed directly in
``urls.py``, never subclassed per app) — exactly the shape ``_inherit_view``
targets without any base-class fallback, so it is registered directly here
too, hooking its ``check_before_save`` seam rather than wrapping ``post``
directly (every submitted field is already applied to the object in-memory
by the time that hook runs, so the check runs once against the combined
result instead of per field).

The actual duplicate-checking logic lives unchanged in
``form_integration.py`` — each ``create_*_with_duplicate_check(original)``
factory expects ``original`` to be a plain, unbound-style callable taking
``self`` as its first argument (``original(self, ...)``); ``_call_super_*``
below adapts a real zero-arg ``super()`` call (the correct way to reach
"the rest of the chain" from a composed extension — see
``horilla.extension._super_rebind``) to that shape.
"""

from horilla.extension.view import ViewExtension

from .form_integration import (
    create_bulk_update_check_before_save,
    create_form_valid_with_duplicate_check,
    create_prepare_tabs_with_duplicate_tab,
)


class DuplicateCheckSingleFormExtension(ViewExtension):
    """Check for duplicates before saving a single-step create/edit form."""

    _inherit_view = "horilla.contrib.generics.views.single_form.HorillaSingleFormView"

    def _call_super_form_valid(self, form):
        return super().form_valid(form)

    def form_valid(self, form):
        """Block the save and report duplicates instead, unless overridden."""
        wrapped = create_form_valid_with_duplicate_check(
            self._call_super_form_valid.__func__, is_multi_step=False
        )
        return wrapped(self, form)


class DuplicateCheckMultiStepFormExtension(ViewExtension):
    """Check for duplicates before saving the final step of a wizard form."""

    _inherit_view = "horilla.contrib.generics.views.multi_form.HorillaMultiStepFormView"

    def _call_super_form_valid(self, form):
        """Reach the real ``super().form_valid`` from the unbound wrapper below."""
        return super().form_valid(form)

    def form_valid(self, form):
        """Block the final wizard step's save and report duplicates instead, unless overridden."""
        wrapped = create_form_valid_with_duplicate_check(
            self._call_super_form_valid.__func__, is_multi_step=True
        )
        return wrapped(self, form)


class DuplicateTabExtension(ViewExtension):
    """Add the Potential Duplicates tab to every detail view's tab list."""

    _inherit_view = "horilla.contrib.generics.views.detail_tabs.HorillaDetailTabView"

    def _call_super_prepare_detail_tabs(self):
        """Reach the real ``super()._prepare_detail_tabs`` from the wrapper below."""
        return super()._prepare_detail_tabs()

    def _prepare_detail_tabs(self):
        wrapped = create_prepare_tabs_with_duplicate_tab(
            self._call_super_prepare_detail_tabs.__func__
        )
        return wrapped(self)


class DuplicateCheckBulkInlineEditExtension(ViewExtension):
    """Check for duplicates before a bulk "Edit Details" save is persisted."""

    _inherit_view = (
        "horilla.contrib.generics.views.helpers.edit_field.UpdateAllFieldsView"
    )

    def _call_super_check_before_save(self, request, obj, changed_fields):
        """Reach the real ``super().check_before_save`` from the unbound wrapper below."""
        return super().check_before_save(request, obj, changed_fields)

    def check_before_save(self, request, obj, changed_fields):
        """Check for duplicates against the in-memory-updated record before it saves."""
        wrapped = create_bulk_update_check_before_save(
            self._call_super_check_before_save.__func__
        )
        return wrapped(self, request, obj, changed_fields)

    def post(self, request, pk, app_label, model_name):
        """Refresh the Potential Duplicates tab after a successful bulk save."""
        from .form_integration import append_bulk_edit_tab_refresh

        response = super().post(request, pk, app_label, model_name)
        return append_bulk_edit_tab_refresh(
            request, response, app_label, model_name, pk
        )
