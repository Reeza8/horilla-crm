"""Horilla generic edit views, including FormView with form-class composition."""

from django.views.generic import FormView as DjangoFormView


class FormView(DjangoFormView):
    """Django FormView that composes ``form_class`` via ``_inherit_form`` extensions."""

    def get_form_class(self):
        """Return composed form when extensions are registered for ``form_class``."""
        # Lazy import: horilla.extension.forms.compose imports HorillaModelForm
        # from this package — a top-level import would circularize.
        from horilla.extension.forms.resolve import resolve_form_class

        base = super().get_form_class()
        if base is None:
            return base
        return resolve_form_class(base)
