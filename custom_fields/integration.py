"""
Integration hooks for injecting custom fields into Lead and Opportunity forms.
"""

CUSTOM_FIELD_PREFIX = "cf_"


class CustomFieldMultiStepMixin:
    """
    Mixin for HorillaMultiStepForm subclasses. Injects custom fields into
    the last step. Must be prepended to the class's __bases__.
    """

    def __init__(self, *args, **kwargs):
        from custom_fields.utils import build_custom_form_fields, load_custom_field_values

        model = self._meta.model
        custom_fields_map = build_custom_form_fields(model)

        if custom_fields_map:
            # Find the original step_fields from the class hierarchy (skip this mixin)
            original_step_fields = {}
            for klass in type(self).__mro__:
                if klass is CustomFieldMultiStepMixin:
                    continue
                sf = klass.__dict__.get("step_fields")
                if sf:
                    original_step_fields = dict(sf)
                    break

            # Set step_fields on the instance to include custom field keys in last step
            last_step = max(original_step_fields.keys()) if original_step_fields else 1
            new_step_fields = dict(original_step_fields)
            new_step_fields[last_step] = list(new_step_fields.get(last_step, [])) + list(
                custom_fields_map.keys()
            )
            # Attach to instance before super().__init__ so HorillaMultiStepForm sees them
            self.step_fields = new_step_fields

        super().__init__(*args, **kwargs)

        if custom_fields_map:
            # Now add the actual field objects (super init has already run and set up self.fields)
            # We need to handle visibility for the current step.
            from django import forms as django_forms

            current_step = getattr(self, "current_step", 1)
            last_step = max(self.step_fields.keys()) if self.step_fields else 1
            form_data = getattr(self, "form_data", None) or {}

            # Load existing values to pre-populate
            instance = getattr(self, "instance", None)
            existing_values = {}
            if instance and instance.pk:
                existing_values = load_custom_field_values(model, instance.pk)

            for key, field in custom_fields_map.items():
                # Set initial value
                val = form_data.get(key) or existing_values.get(key)
                if val is not None:
                    field.initial = val

                self.fields[key] = field

                # Apply visibility: visible only on last step
                if current_step != last_step:
                    self.fields[key].required = False
                    self.fields[key].widget = django_forms.HiddenInput()
                    self._step_hidden_fields.add(key)
                else:
                    # On the last step - apply initial value to data as well
                    if val is not None and key not in self.data:
                        # For multi-step forms, data is the form_data dict
                        # We need to set it in initial, not data, to avoid validation issues
                        self.initial[key] = val


class CustomFieldSingleFormMixin:
    """
    Mixin for HorillaModelForm subclasses. Injects custom fields and populates
    existing values when editing.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from custom_fields.utils import build_custom_form_fields, load_custom_field_values

        model = self._meta.model
        custom_fields_map = build_custom_form_fields(model)
        self.fields.update(custom_fields_map)

        instance = getattr(self, "instance", None)
        if instance and instance.pk:
            existing_values = load_custom_field_values(model, instance.pk)
            for key, val in existing_values.items():
                if key in self.fields:
                    self.initial[key] = val


class CustomFieldViewMixin:
    """
    Mixin for form views. Saves custom field values after the main object is saved.
    Compatible with both HorillaMultiStepFormView and HorillaSingleFormView.
    """

    def _save_custom_fields_for_instance(self, form, instance):
        from custom_fields.utils import CUSTOM_FIELD_PREFIX, save_custom_field_values

        cleaned = {}
        # Try cleaned_data first
        if hasattr(form, "cleaned_data"):
            cleaned = {
                k: v
                for k, v in form.cleaned_data.items()
                if k.startswith(CUSTOM_FIELD_PREFIX)
            }
        # Fallback: check session form_data for multi-step forms
        if not cleaned:
            storage_key = getattr(self, "storage_key", None)
            if storage_key:
                session_data = self.request.session.get(storage_key, {})
                cleaned = {
                    k: v
                    for k, v in session_data.items()
                    if k.startswith(CUSTOM_FIELD_PREFIX)
                }

        if cleaned:
            company = getattr(instance, "company", None)
            save_custom_field_values(
                instance.__class__, instance.pk, cleaned, company=company
            )

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.object and self.object.pk:
            try:
                self._save_custom_fields_for_instance(form, self.object)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning(
                    "custom_fields: error saving custom fields: %s", exc
                )
        return response
