"""
Mixins for integrating custom fields into existing Horilla forms and views.
"""

from .utils import (
    CUSTOM_FIELD_PREFIX,
    build_custom_form_fields,
    load_custom_field_values,
    save_custom_field_values,
)


class CustomFieldFormMixin:
    """
    Mixin for ModelForm subclasses. Dynamically adds custom field form fields
    in __init__ and populates them with existing values when editing.

    Must be placed before the ModelForm in the MRO.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        model = self._meta.model
        custom_fields = build_custom_form_fields(model)
        self.fields.update(custom_fields)

        if self.instance and self.instance.pk:
            existing_values = load_custom_field_values(model, self.instance.pk)
            for key, val in existing_values.items():
                if key in self.fields:
                    self.initial[key] = val

        # For multi-step forms, populate from form_data (session data)
        form_data = getattr(self, "form_data", None)
        if form_data:
            for key in custom_fields:
                if key in form_data:
                    self.initial[key] = form_data[key]


class CustomFieldViewMixin:
    """
    Mixin for form views. Overrides form_valid to save custom field values
    after the instance is saved.

    For multi-step views, this hooks into the final save.
    For single-step views, this hooks into form_valid.
    """

    def save_custom_fields(self, form, instance):
        cleaned = {}
        for key, value in (form.cleaned_data or {}).items():
            if key.startswith(CUSTOM_FIELD_PREFIX):
                cleaned[key] = value
        if cleaned:
            company = getattr(instance, "company", None)
            save_custom_field_values(
                instance.__class__, instance.pk, cleaned, company=company
            )
