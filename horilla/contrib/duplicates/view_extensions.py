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

``UpdateFieldView`` (inline field edit) is itself a single, concrete,
model-agnostic view (routed directly in ``urls.py``, never subclassed per
app) — exactly the shape ``_inherit_view`` targets without any base-class
fallback, so it is registered directly here too.

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
    create_form_valid_with_duplicate_check,
    create_prepare_tabs_with_duplicate_tab,
    create_update_field_with_duplicate_check,
)


class DuplicateCheckSingleFormExtension(ViewExtension):
    """Check for duplicates before saving a single-step create/edit form."""

    _inherit_view = "horilla.contrib.generics.views.single_form.HorillaSingleFormView"

    def _call_super_form_valid(self, form):
        return super().form_valid(form)

    def form_valid(self, form):
        wrapped = create_form_valid_with_duplicate_check(
            self._call_super_form_valid.__func__, is_multi_step=False
        )
        return wrapped(self, form)


class DuplicateCheckMultiStepFormExtension(ViewExtension):
    """Check for duplicates before saving the final step of a wizard form."""

    _inherit_view = "horilla.contrib.generics.views.multi_form.HorillaMultiStepFormView"

    def _call_super_form_valid(self, form):
        return super().form_valid(form)

    def form_valid(self, form):
        wrapped = create_form_valid_with_duplicate_check(
            self._call_super_form_valid.__func__, is_multi_step=True
        )
        return wrapped(self, form)


class DuplicateTabExtension(ViewExtension):
    """Add the Potential Duplicates tab to every detail view's tab list."""

    _inherit_view = "horilla.contrib.generics.views.detail_tabs.HorillaDetailTabView"

    def _call_super_prepare_detail_tabs(self):
        return super()._prepare_detail_tabs()

    def _prepare_detail_tabs(self):
        wrapped = create_prepare_tabs_with_duplicate_tab(
            self._call_super_prepare_detail_tabs.__func__
        )
        return wrapped(self)


class DuplicateCheckInlineEditExtension(ViewExtension):
    """Check for duplicates after an inline field edit is saved."""

    _inherit_view = "horilla.contrib.generics.views.helpers.edit_field.UpdateFieldView"

    def _call_super_post(self, request, pk, field_name, app_label, model_name):
        return super().post(request, pk, field_name, app_label, model_name)

    def post(self, request, pk, field_name, app_label, model_name):
        wrapped = create_update_field_with_duplicate_check(
            self._call_super_post.__func__
        )
        return wrapped(self, request, pk, field_name, app_label, model_name)
