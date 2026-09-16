"""
Integration hooks for injecting custom fields into Lead and Opportunity forms
and detail views.
"""

from custom_fields.utils import (
    CUSTOM_FIELD_PREFIX,
    assign_custom_field_attr,
    build_custom_form_fields,
    choice_values_from_data,
    custom_field_form_name,
    format_custom_field_display,
    get_custom_field_definitions,
    is_custom_field_name,
    load_custom_field_values,
    safe_custom_field_label,
    save_custom_field_values,
)


def persist_custom_fields_for_form(form, instance):
    """Save a form's ``cf_*`` cleaned_data values against a saved instance."""
    if not instance or not instance.pk:
        return
    cleaned = {
        key: value
        for key, value in (getattr(form, "cleaned_data", None) or {}).items()
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


def save_with_custom_fields(form, original_save, commit=True):
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
    form.use_required_attribute = False
    instance = original_save(commit=commit)
    if commit:
        persist_custom_fields_for_form(form, instance)
    else:
        original_save_m2m = form.save_m2m

        def _save_m2m():
            original_save_m2m()
            persist_custom_fields_for_form(form, form.instance)

        form.save_m2m = _save_m2m
    return instance


class CustomFieldSaveMixin:
    """
    Persist extra ``cf_*`` form fields after the model instance is saved.
    Kept for any form that still prepends mixins directly rather than
    going through the generic base-class injection in ``inject.py``.
    """

    use_required_attribute = False

    def save(self, commit=True):
        return save_with_custom_fields(
            self,
            lambda commit: super(CustomFieldSaveMixin, self).save(commit=commit),
            commit,
        )


def apply_multi_step_custom_fields(form, model):
    """
    Build and attach ``cf_*`` fields onto a HorillaMultiStepForm instance's
    last step. Called from HorillaMultiStepForm.__init__ (after the base
    __init__ has run) for any model registered for custom fields.

    ``use_required_attribute = False`` keeps Django's ``required`` validation
    but skips the HTML ``required`` attribute. Native browser validation
    otherwise blocks the last wizard step: the step body is in a 300px
    overflow box, and Select2-hidden choice fields are not focusable.
    """
    from django import forms as django_forms

    custom_fields_map = build_custom_form_fields(model)
    if not custom_fields_map:
        return

    form.use_required_attribute = False

    current_step = getattr(form, "current_step", 1)
    last_step = max(form.step_fields.keys()) if form.step_fields else 1
    form_data = getattr(form, "form_data", None) or {}
    instance = getattr(form, "instance", None)
    existing_values = {}
    if instance and instance.pk:
        existing_values = load_custom_field_values(model, instance.pk)

    for key, field in custom_fields_map.items():
        val = form_data.get(key)
        if val in (None, ""):
            val = existing_values.get(key)
        if isinstance(field, django_forms.MultipleChoiceField):
            val = choice_values_from_data(val)
        if val is not None:
            field.initial = val

        form.fields[key] = field

        if current_step != last_step:
            form.fields[key].required = False
            if isinstance(field, django_forms.MultipleChoiceField):
                form.fields[key].widget = django_forms.MultipleHiddenInput()
            else:
                form.fields[key].widget = django_forms.HiddenInput()
            form._step_hidden_fields.add(key)
        elif val is not None:
            form.initial[key] = val


def extend_multi_step_fields(model, step_fields):
    """Return ``step_fields`` with this model's ``cf_*`` names appended to the last step."""
    custom_fields_map = build_custom_form_fields(model)
    if not custom_fields_map:
        return step_fields

    original_step_fields = dict(step_fields or {})
    last_step = max(original_step_fields.keys()) if original_step_fields else 1
    new_step_fields = dict(original_step_fields)
    new_step_fields[last_step] = list(new_step_fields.get(last_step, [])) + list(
        custom_fields_map.keys()
    )
    return new_step_fields


def clean_multi_step_custom_fields(form, original_clean):
    """
    HorillaMultiStepForm.clean() calls ``model._meta.get_field`` for every
    current-step name and catches ``models.FieldDoesNotExist``, which does
    not exist on ``horilla.db.models``. Extra ``cf_*`` fields would then
    raise ``AttributeError``. It also drops errors for any field name not
    listed in ``step_fields[current_step]`` — which ``cf_*`` names never are
    (which custom fields exist is per-request/per-company dynamic, so their
    names cannot be baked into the static, class-level ``step_fields`` the
    extension framework composes once at registration time).

    Strip custom fields from ``step_fields`` before Horilla's ``clean``
    (so the AttributeError above can't happen), then restore ``cf_*``
    errors ``_clean_fields`` already collected for fields actually present
    on this form instance right now (``form.fields``, not ``step_fields``)
    on the current step. Horilla sources stay unchanged.
    """
    original_step_fields = form.step_fields
    current_step_cf_names = {
        name
        for name in form.fields
        if is_custom_field_name(name) and name not in form._step_hidden_fields
    }
    saved_cf_errors = {}
    error_dict = getattr(form, "_errors", None)
    if error_dict:
        for name in current_step_cf_names:
            if name in error_dict:
                saved_cf_errors[name] = error_dict[name]
    try:
        form.step_fields = {
            step: [name for name in fields if not is_custom_field_name(name)]
            for step, fields in (original_step_fields or {}).items()
        }
        cleaned_data = original_clean()
    finally:
        form.step_fields = original_step_fields

    for name, errors in saved_cf_errors.items():
        form._errors[name] = errors
    return cleaned_data


def apply_single_form_custom_fields(form, model):
    """
    Build and attach ``cf_*`` fields onto a HorillaModelForm instance,
    populating existing values when editing. Called from
    HorillaModelForm.__init__ (after the base __init__ has run) for any
    model registered for custom fields.
    """
    from django import forms as django_forms

    custom_fields_map = build_custom_form_fields(model)
    form.fields.update(custom_fields_map)

    instance = getattr(form, "instance", None)
    if instance and instance.pk:
        existing_values = load_custom_field_values(model, instance.pk)
        for key, val in existing_values.items():
            if key in form.fields:
                field = form.fields[key]
                if isinstance(field, django_forms.MultipleChoiceField):
                    val = choice_values_from_data(val)
                form.initial[key] = val


class CustomFieldMultiStepMixin(CustomFieldSaveMixin):
    """
    Mixin for HorillaMultiStepForm subclasses. Injects custom fields into
    the last step. Kept for any form that still prepends mixins directly
    rather than going through the generic base-class injection in
    ``inject.py``. Must be prepended to the class's __bases__.
    """

    def __init__(self, *args, **kwargs):
        model = self._meta.model
        self.step_fields = extend_multi_step_fields(
            model, getattr(self, "step_fields", None)
        )
        super().__init__(*args, **kwargs)
        apply_multi_step_custom_fields(self, model)

    def clean(self):
        return clean_multi_step_custom_fields(
            self, lambda: super(CustomFieldMultiStepMixin, self).clean()
        )


class CustomFieldSingleFormMixin(CustomFieldSaveMixin):
    """
    Mixin for HorillaModelForm subclasses. Injects custom fields and populates
    existing values when editing. Kept for any form that still prepends
    mixins directly rather than going through the generic base-class
    injection in ``inject.py``.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_single_form_custom_fields(self, self._meta.model)


class CustomFieldDetailMixin:
    """
    Merge custom fields into a detail view's ``body`` so they render in the
    header grid and the Details tab. Values are attached on the instance so
    ``display_field_value`` can read them. Fields stay editable (pen icon)
    unless Horilla already marked them non-editable.
    """

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = (
            context.get("obj") or context.get("object") or getattr(self, "object", None)
        )
        apply_custom_fields_to_detail_context(
            context, obj, request=getattr(self, "request", None), view=self
        )
        return context


def _visibility_field_names(visibility, attr):
    if visibility is None:
        return None
    saved = getattr(visibility, attr, None)
    if not saved:
        return None
    from custom_fields.detail_hooks import field_names_from_list

    return field_names_from_list(saved)


def _detail_visibility_for(request, obj):
    if request is None or not getattr(request, "user", None):
        return None
    if not getattr(obj, "_meta", None):
        return None
    from horilla.contrib.core.models import DetailFieldVisibility
    from horilla.urls import resolve

    url_name = request.GET.get("detail_url_name") or ""
    if not url_name:
        try:
            resolved = resolve(request.path)
            url_name = resolved.url_name if resolved else ""
        except Exception:
            url_name = ""
    return DetailFieldVisibility.all_objects.filter(
        user=request.user,
        app_label=obj._meta.app_label,
        model_name=obj._meta.model_name,
        url_name=url_name,
    ).first()


def merge_custom_fields_into_body(
    body, ordered_names, definitions, obj, values, add_unplaced_defs=True
):
    """
    Rebuild a detail ``body`` list so ``cf_*`` rows follow saved picker order.

    ``ordered_names is None`` means the user has no saved visibility for this
    section: keep model fields and, when ``add_unplaced_defs`` is True,
    append every custom field that has not been placed elsewhere. New custom
    fields default into the Details tab only (matching
    ``append_custom_fields_to_defaults``), so the header call passes
    ``add_unplaced_defs=False`` to avoid showing the same unplaced field in
    both sections before the user ever saves a layout. When ``ordered_names``
    is a list, only custom fields present in that list are shown, at that
    index.
    """
    model_rows = []
    model_by_name = {}
    for item in body or []:
        name = item[1] if isinstance(item, (list, tuple)) and len(item) >= 2 else item
        name = str(name)
        if is_custom_field_name(name):
            continue
        model_rows.append(item)
        model_by_name[name] = item

    defs_by_key = {custom_field_form_name(defn): defn for defn in definitions}

    def cf_row(defn):
        key = custom_field_form_name(defn)
        value = values.get(key)
        assign_custom_field_attr(obj, key, format_custom_field_display(defn, value))
        return (safe_custom_field_label(defn), key)

    if ordered_names is None:
        result = list(model_rows)
        if not add_unplaced_defs:
            return result
        existing = {
            str(item[1] if isinstance(item, (list, tuple)) and len(item) >= 2 else item)
            for item in result
        }
        for defn in definitions:
            key = custom_field_form_name(defn)
            if key not in existing:
                result.append(cf_row(defn))
                existing.add(key)
        return result

    result = []
    for name in ordered_names:
        name = str(name)
        if is_custom_field_name(name):
            defn = defs_by_key.get(name)
            if defn:
                result.append(cf_row(defn))
        elif name in model_by_name:
            result.append(model_by_name[name])
    return result


def apply_custom_fields_to_detail_context(context, obj, request=None, view=None):
    """Add ``(label, cf_<id>)`` rows to context['body'] and set values on obj."""
    if obj is None or not getattr(obj, "pk", None):
        return context

    definitions = list(get_custom_field_definitions(obj.__class__))
    if not definitions:
        return context

    values = load_custom_field_values(obj.__class__, obj.pk)
    visibility = _detail_visibility_for(request, obj)

    from horilla.contrib.generics.views.detail_tabs import HorillaDetailSectionView

    is_details_section = view is not None and isinstance(view, HorillaDetailSectionView)
    if is_details_section:
        ordered_names = _visibility_field_names(visibility, "details_fields")
    else:
        ordered_names = _visibility_field_names(visibility, "header_fields")

    context["body"] = merge_custom_fields_into_body(
        context.get("body"),
        ordered_names,
        definitions,
        obj,
        values,
        add_unplaced_defs=is_details_section,
    )
    return context
