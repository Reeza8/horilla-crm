"""Horilla generic edit views, including FormView with form-class composition."""

from django.views.generic import FormView as DjangoFormView

from horilla.views.generic.base import View


class FormView(View, DjangoFormView):
    """
    Django FormView that composes ``form_class`` via ``_inherit_form``
    extensions, and the view class itself via ``_inherit_view``.

    Inherits ``View``'s ``as_view()``, so ``_inherit_view`` extensions
    (``horilla.extension.view``) can override this view's own methods
    (``get_context_data``, ``form_valid``, ``get_form_kwargs``, etc.) on
    the concrete subclass, the same mechanism already used by
    ``EditFieldView``/``UpdateFieldView``. Previously this class subclassed
    Django's ``FormView`` directly, so only the *form class* it built
    (via ``get_form_class()`` below) was extensible — the view's own
    methods were not (e.g. ``horilla.contrib.generics.views.multi_form.HorillaMultiStepFormView``,
    ``horilla.contrib.generics.views.helpers.list_column.ListColumnSelectFormView``).
    """

    def get_form_class(self):
        """Return composed form when extensions are registered for ``form_class``."""
        # Lazy import: horilla.extension.forms.compose imports HorillaModelForm
        # from this package — a top-level import would circularize.
        from horilla.extension.forms.resolve import resolve_form_class

        base = super().get_form_class()
        if base is None:
            return base
        return resolve_form_class(base)
