import re

from django import forms
from django.utils.html import strip_tags

from horilla.contrib.core.models import HorillaContentType
from horilla.utils.translation import gettext as _

from .models import (
    CustomFieldDefinition,
    CustomFieldValue,
    format_choice_display,
    parse_choice_values,
)

SELECT2_MULTI_CLASS = "js-example-basic-multiple headselect w-full"

CUSTOM_FIELD_PREFIX = "cf_"

_UNSAFE_LABEL_CHARS = re.compile(r"[^\w\s.-]", re.UNICODE)

INLINE_FIELD_TYPES = {
    "small_text": "text",
    "large_text": "textarea",
    "number": "number",
    "choice": "select",
}


def is_custom_field_name(name):
    """Return True if ``name`` is a custom-field form/detail key (``cf_<id>``)."""
    return str(name).startswith(CUSTOM_FIELD_PREFIX)


def custom_field_form_name(definition):
    """Return the form/detail key for a ``CustomFieldDefinition``."""
    return f"{CUSTOM_FIELD_PREFIX}{definition.pk}"


def parse_custom_field_pk(name):
    """Return the definition pk from ``cf_<id>``, or None if the name is invalid."""
    if not is_custom_field_name(name):
        return None
    try:
        return int(str(name)[len(CUSTOM_FIELD_PREFIX) :])
    except (TypeError, ValueError):
        return None


def assign_custom_field_attr(obj, key, value):
    """Store a ``cf_*`` value on the instance without going through Django fields."""
    obj.__dict__[key] = "" if value is None else value


def safe_custom_field_label(definition):
    """
    Label safe for Horilla's Details-tab input ids (``{{ col.0 }}-details-tab``).

    HTML in the field name is stripped so HTMX ``querySelector`` does not
    receive ``<``, quotes, or other selector-breaking characters.
    """
    raw = str(getattr(definition, "name", "") or "")
    text = strip_tags(raw)
    text = _UNSAFE_LABEL_CHARS.sub("", text)
    text = re.sub(r"\s+", " ", text).strip(" .-")
    if not text:
        return f"{_('Custom Field')} {definition.pk}"
    return text


def get_definition_by_form_name(model, field_name):
    """
    Return the active ``CustomFieldDefinition`` for ``field_name`` on ``model``.

    ``field_name`` must be ``cf_<id>`` and belong to this model's content type.
    """
    pk = parse_custom_field_pk(field_name)
    if pk is None:
        return None
    ct = HorillaContentType.objects.get_for_model(model)
    try:
        return CustomFieldDefinition.objects.get(
            pk=pk, content_type=ct, is_active=True
        )
    except CustomFieldDefinition.DoesNotExist:
        return None


def get_custom_field_definitions(model):
    """Return all active custom field definitions for a given model class."""
    ct = HorillaContentType.objects.get_for_model(model)
    return CustomFieldDefinition.objects.filter(content_type=ct, is_active=True)


def build_custom_form_fields(model):
    """
    Build a dict of Django form fields for all custom field definitions
    attached to the given model. Keys are prefixed with CUSTOM_FIELD_PREFIX.
    """
    fields = {}
    for defn in get_custom_field_definitions(model):
        key = f"{CUSTOM_FIELD_PREFIX}{defn.pk}"
        if defn.field_type == "small_text":
            field = forms.CharField(
                max_length=255,
                required=defn.is_required,
                label=safe_custom_field_label(defn),
                widget=forms.TextInput(
                    attrs={
                        "class": "text-color-600 p-2 placeholder:text-xs w-full border border-dark-50 rounded-md mt-1 focus-visible:outline-0 placeholder:text-dark-100 text-sm transition duration-300 focus:border-primary-600",
                        "placeholder": _("Enter %(name)s")
                        % {"name": safe_custom_field_label(defn)},
                    }
                ),
            )
        elif defn.field_type == "large_text":
            field = forms.CharField(
                required=defn.is_required,
                label=safe_custom_field_label(defn),
                widget=forms.Textarea(
                    attrs={
                        "class": "text-color-600 p-2 placeholder:text-xs w-full border border-dark-50 rounded-md mt-1 focus-visible:outline-0 placeholder:text-dark-100 text-sm transition duration-300 focus:border-primary-600",
                        "rows": 3,
                        "placeholder": _("Enter %(name)s")
                        % {"name": safe_custom_field_label(defn)},
                    }
                ),
            )
        elif defn.field_type == "number":
            field = forms.DecimalField(
                max_digits=20,
                decimal_places=4,
                required=defn.is_required,
                label=safe_custom_field_label(defn),
                widget=forms.NumberInput(
                    attrs={
                        "class": "text-color-600 p-2 placeholder:text-xs w-full border border-dark-50 rounded-md mt-1 focus-visible:outline-0 placeholder:text-dark-100 text-sm transition duration-300 focus:border-primary-600",
                        "placeholder": _("Enter %(name)s")
                        % {"name": safe_custom_field_label(defn)},
                    }
                ),
            )
        elif defn.field_type == "choice":
            choices_list = [(c, c) for c in defn.get_choices_list()]
            field = forms.MultipleChoiceField(
                choices=choices_list,
                required=defn.is_required,
                label=safe_custom_field_label(defn),
                widget=forms.SelectMultiple(
                    attrs={
                        "class": SELECT2_MULTI_CLASS,
                        "data-placeholder": "Select options...",
                    }
                ),
            )
        else:
            continue
        fields[key] = field
    return fields


def load_custom_field_values(model_class, instance_pk):
    """Return a dict of {cf_<defn_pk>: value} for a saved instance."""
    ct = HorillaContentType.objects.get_for_model(model_class)
    values = {}
    for cfv in CustomFieldValue.objects.filter(
        content_type=ct, object_id=instance_pk
    ).select_related("field_definition"):
        key = f"{CUSTOM_FIELD_PREFIX}{cfv.field_definition_id}"
        values[key] = cfv.get_value()
    return values


def save_custom_field_values(model_class, instance_pk, cleaned_data, company=None):
    """
    Persist custom field values from cleaned_data for the given instance.
    Only processes keys that start with CUSTOM_FIELD_PREFIX.
    """
    ct = HorillaContentType.objects.get_for_model(model_class)
    for key, value in cleaned_data.items():
        if not key.startswith(CUSTOM_FIELD_PREFIX):
            continue
        defn_pk = int(key[len(CUSTOM_FIELD_PREFIX) :])
        try:
            defn = CustomFieldDefinition.objects.get(pk=defn_pk)
        except CustomFieldDefinition.DoesNotExist:
            continue

        cfv, _created = CustomFieldValue.objects.update_or_create(
            field_definition=defn,
            content_type=ct,
            object_id=instance_pk,
            defaults={"company": company} if company else {},
        )
        cfv.set_value(value)
        if company and cfv.company != company:
            cfv.company = company
        cfv.save()


def format_custom_field_display(definition, value):
    """Plain-text value for detail, list, export, and inline display."""
    if definition.field_type == "choice":
        return format_choice_display(value)
    if value is None:
        return ""
    return str(value)


def choice_values_from_data(value):
    """Normalize POST/session/form data into a list of selected choices."""
    return parse_choice_values(value)
