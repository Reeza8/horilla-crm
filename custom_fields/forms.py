# Third-party imports (Django)
from django import forms
from django.utils.safestring import mark_safe

from horilla.contrib.core.models import HorillaContentType
from horilla.contrib.generics.forms import HorillaModelForm

# First party imports (Horilla)
from horilla.core.exceptions import ValidationError
from horilla.utils.html import strip_tags
from horilla.utils.translation import gettext_lazy as _

from .models import CustomFieldDefinition

CHOICE_FIELD_TYPES = ("choice", "single_choice")

CHOICES_TOGGLE_SCRIPT = """
<script>
(function () {
  var select = document.getElementById("id_field_type");
  var box = document.getElementById("choices_container");
  var choiceTypes = %s;
  function syncChoicesVisibility() {
    if (!select || !box) return;
    box.style.display = choiceTypes.indexOf(select.value) !== -1 ? "" : "none";
  }
  if (!select) return;
  if (!select.dataset.cfChoicesBound) {
    select.dataset.cfChoicesBound = "1";
    select.addEventListener("change", syncChoicesVisibility);
    if (window.jQuery) {
      window.jQuery(select).on("change select2:select select2:clear", syncChoicesVisibility);
    }
  }
  syncChoicesVisibility();
})();
</script>
""" % list(
    CHOICE_FIELD_TYPES
)


def get_supported_custom_field_models():
    """
    Return the (app_label, model_name) pairs registered for custom fields.

    Backed by the same registry duplicate-checking and other Horilla
    features use — any app opts a model in with
    ``register_model_for_feature(..., features=["custom_fields_models"])``
    from its own ``registration.py``. No model is hardcoded here.
    """
    from horilla.registry.feature import FEATURE_REGISTRY

    return [
        f"{model._meta.app_label}.{model._meta.model_name}"
        for model in FEATURE_REGISTRY.get("custom_fields_models", [])
    ]


class FieldTypeSelect(forms.Select):
    """Select that toggles the choices textarea when Multiple Choice is picked."""

    def render(self, name, value, attrs=None, renderer=None):
        html = super().render(name, value, attrs, renderer)
        return mark_safe(str(html) + CHOICES_TOGGLE_SCRIPT)


class CustomFieldDefinitionForm(HorillaModelForm):
    """Form for creating / editing a custom field definition."""

    class Meta:
        model = CustomFieldDefinition
        fields = [
            "content_type",
            "name",
            "field_type",
            "is_required",
            "choices",
            "order",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        supported_pairs = [
            pair.split(".", 1) for pair in get_supported_custom_field_models()
        ]
        supported_cts = HorillaContentType.objects.filter(
            app_label__in=[pair[0] for pair in supported_pairs],
            model__in=[pair[1] for pair in supported_pairs],
        )
        self.fields["content_type"].queryset = supported_cts
        self.fields["content_type"].label = _("Model")

        self.fields["choices"].required = False
        self.fields["choices"].widget.attrs.update(
            {
                "rows": 3,
                "placeholder": _("Option 1, Option 2, Option 3"),
            }
        )
        if self._current_field_type() in CHOICE_FIELD_TYPES:
            self.fields["choices"].widget.attrs.pop("container_style", None)
        else:
            self.fields["choices"].widget.attrs["container_style"] = "display: none;"

        field_type_widget = self.fields["field_type"].widget
        self.fields["field_type"].widget = FieldTypeSelect(
            attrs=field_type_widget.attrs,
            choices=list(self.fields["field_type"].choices),
        )

    def _current_field_type(self):
        if self.is_bound and self.data is not None:
            return self.data.get("field_type") or ""
        if getattr(self.instance, "pk", None):
            return self.instance.field_type or ""
        return self.initial.get("field_type") or ""

    def _clear_submitted_name(self):
        """Drop the posted Field Name so the re-rendered form does not echo XSS."""
        if not self.is_bound or self.data is None:
            return
        try:
            data = self.data.copy()
        except (AttributeError, TypeError):
            data = dict(self.data)
        if hasattr(data, "setlist"):
            data.setlist("name", [""])
        else:
            data["name"] = ""
        self.data = data

    def clean_name(self):
        raw = self.cleaned_data.get("name") or ""
        stripped = strip_tags(raw).strip()
        if stripped != str(raw).strip() or "<" in raw or ">" in raw:
            self._clear_submitted_name()
            raise ValidationError(_("HTML is not allowed in Field Name."))
        if not stripped:
            raise ValidationError(self.fields["name"].error_messages["required"])
        return stripped

    def clean(self):
        cleaned_data = super().clean()
        field_type = cleaned_data.get("field_type")
        choices = cleaned_data.get("choices", "")
        if field_type in CHOICE_FIELD_TYPES and not choices.strip():
            self.add_error("choices", _("Choices are required for this field type."))
        ct = cleaned_data.get("content_type")
        if (
            ct
            and f"{ct.app_label}.{ct.model}" not in get_supported_custom_field_models()
        ):
            self.add_error(
                "content_type",
                _("Custom fields are not supported for this model."),
            )
        return cleaned_data
