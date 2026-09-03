"""
Integration hooks for injecting custom fields into Lead and Opportunity forms
and detail views.
"""

from custom_fields.utils import (
    CUSTOM_FIELD_PREFIX,
    build_custom_form_fields,
    get_custom_field_definitions,
    load_custom_field_values,
    save_custom_field_values,
)


class CustomFieldSaveMixin:
    """
    Persist extra ``cf_*`` form fields after the model instance is saved.

    Horilla multi-step and single-step views both call ``save(commit=False)``
    then ``instance.save()`` then ``form.save_m2m()``. Hooking ``save_m2m``
    is the reliable place to write custom field values without wrapping
    the view's ``form_valid``.

    ``use_required_attribute = False`` keeps Django's ``required`` validation
    but skips the HTML ``required`` attribute. Native browser validation
    otherwise blocks the last wizard step: the step body is in a 300px
    overflow box, and Select2-hidden choice fields are not focusable.
    """

    use_required_attribute = False

    def save(self, commit=True):
        instance = super().save(commit=commit)
        if commit:
            self._persist_custom_fields(instance)
        else:
            original_save_m2m = self.save_m2m

            def _save_m2m():
                original_save_m2m()
                self._persist_custom_fields(self.instance)

            self.save_m2m = _save_m2m
        return instance

    def _persist_custom_fields(self, instance):
        if not instance or not instance.pk:
            return
        cleaned = {
            key: value
            for key, value in (getattr(self, "cleaned_data", None) or {}).items()
            if key.startswith(CUSTOM_FIELD_PREFIX)
        }
        if not cleaned:
            return
        save_custom_field_values(
            instance.__class__,
            instance.pk,
            cleaned,
            company=getattr(instance, "company", None),
        )


class CustomFieldMultiStepMixin(CustomFieldSaveMixin):
    """
    Mixin for HorillaMultiStepForm subclasses. Injects custom fields into
    the last step. Must be prepended to the class's __bases__.
    """

    def __init__(self, *args, **kwargs):
        from django import forms as django_forms

        model = self._meta.model
        custom_fields_map = build_custom_form_fields(model)

        if custom_fields_map:
            original_step_fields = {}
            for klass in type(self).__mro__:
                if klass in (CustomFieldMultiStepMixin, CustomFieldSaveMixin):
                    continue
                step_fields = klass.__dict__.get("step_fields")
                if step_fields:
                    original_step_fields = dict(step_fields)
                    break

            last_step = max(original_step_fields.keys()) if original_step_fields else 1
            new_step_fields = dict(original_step_fields)
            new_step_fields[last_step] = list(
                new_step_fields.get(last_step, [])
            ) + list(custom_fields_map.keys())
            self.step_fields = new_step_fields

        super().__init__(*args, **kwargs)

        if not custom_fields_map:
            return

        current_step = getattr(self, "current_step", 1)
        last_step = max(self.step_fields.keys()) if self.step_fields else 1
        form_data = getattr(self, "form_data", None) or {}
        instance = getattr(self, "instance", None)
        existing_values = {}
        if instance and instance.pk:
            existing_values = load_custom_field_values(model, instance.pk)

        for key, field in custom_fields_map.items():
            val = form_data.get(key)
            if val in (None, ""):
                val = existing_values.get(key)
            if val is not None:
                field.initial = val

            self.fields[key] = field

            if current_step != last_step:
                self.fields[key].required = False
                self.fields[key].widget = django_forms.HiddenInput()
                self._step_hidden_fields.add(key)
            elif val is not None:
                self.initial[key] = val


class CustomFieldSingleFormMixin(CustomFieldSaveMixin):
    """
    Mixin for HorillaModelForm subclasses. Injects custom fields and populates
    existing values when editing.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        model = self._meta.model
        custom_fields_map = build_custom_form_fields(model)
        self.fields.update(custom_fields_map)

        instance = getattr(self, "instance", None)
        if instance and instance.pk:
            existing_values = load_custom_field_values(model, instance.pk)
            for key, val in existing_values.items():
                if key in self.fields:
                    self.initial[key] = val


class CustomFieldDetailMixin:
    """
    Append defined custom fields to a detail view's ``body`` so they render
    in the header grid and the Details tab. Values are attached on the
    instance so the existing ``display_field_value`` tag can read them.
    """

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = (
            context.get("obj")
            or context.get("object")
            or getattr(self, "object", None)
        )
        apply_custom_fields_to_detail_context(context, obj)
        return context


def apply_custom_fields_to_detail_context(context, obj):
    """Add ``(label, cf_<id>)`` rows to context['body'] and set values on obj."""
    if obj is None or not getattr(obj, "pk", None):
        return context

    definitions = list(get_custom_field_definitions(obj.__class__))
    if not definitions:
        return context

    values = load_custom_field_values(obj.__class__, obj.pk)
    extra_body = []
    extra_keys = []
    for defn in definitions:
        key = f"{CUSTOM_FIELD_PREFIX}{defn.pk}"
        value = values.get(key)
        setattr(obj, key, "" if value is None else value)
        extra_body.append((defn.name, key))
        extra_keys.append(key)

    body = list(context.get("body") or [])
    existing_names = {
        item[1] if isinstance(item, (list, tuple)) and len(item) >= 2 else item
        for item in body
    }
    for row in extra_body:
        if row[1] not in existing_names:
            body.append(row)
    context["body"] = body

    non_editable = list(context.get("non_editable_fields") or [])
    for key in extra_keys:
        if key not in non_editable:
            non_editable.append(key)
    context["non_editable_fields"] = non_editable
    return context
