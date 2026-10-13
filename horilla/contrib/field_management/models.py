"""
Models for the Field Management app.

Three independent features share this app:

* ``FieldRequirement`` -- per-company override of whether a model field is
  required on its forms.
* ``FormLayoutField`` -- per-company visibility and order of a model's fields
  on its "Custom Layout" form mode.
* ``CustomFieldDefinition`` / ``CustomFieldValue`` -- user-defined extra fields
  on opted-in models and their per-record values.
"""

# Standard library imports
import json
from datetime import date, datetime

# Third-party imports (Django)
from django.utils.dateparse import parse_date, parse_datetime

# First party imports (Horilla)
from horilla.contrib.core.models import HorillaContentType, HorillaCoreModel
from horilla.core.exceptions import FieldDoesNotExist, ValidationError
from horilla.db import models
from horilla.urls import reverse_lazy
from horilla.utils import timezone
from horilla.utils.translation import gettext_lazy as _

# Local imports
from .registry.field_requirements import (
    can_relax_requirement,
    get_excluded_fields,
    is_requirement_configurable,
)
from .registry.field_requirements import (
    limit_content_types as limit_requirement_content_types,
)
from .registry.form_layouts import (
    limit_content_types as limit_form_layout_content_types,
)

# ---------------------------------------------------------------------------
# Field requirements
# ---------------------------------------------------------------------------


class FieldRequirement(HorillaCoreModel):
    """
    Per-company override for whether a model field is required on its forms.

    Only affects form validation. The underlying column is never altered, so a
    field can be relaxed only when the database already has a way to store an
    empty value for it -- enforced by :meth:`clean`.
    """

    content_type = models.ForeignKey(
        HorillaContentType,
        on_delete=models.CASCADE,
        limit_choices_to=limit_requirement_content_types,
        related_name="%(app_label)s_%(class)s_set",
        verbose_name=_("Model"),
    )
    field_name = models.CharField(max_length=255, verbose_name=_("Field"))
    is_required = models.BooleanField(
        default=True,
        verbose_name=_("Required"),
        help_text=_(
            "When enabled the field must be filled in. When disabled the field "
            "becomes optional on create and edit forms."
        ),
    )

    class Meta:
        """
        Meta options for the FieldRequirement model.
        """

        verbose_name = _("Field Requirement")
        verbose_name_plural = _("Field Requirements")
        unique_together = (("content_type", "field_name", "company"),)
        ordering = ["content_type__model", "field_name"]

    def __str__(self):
        return f"{self.model_label} - {self.field_label}"

    @property
    def model_class(self):
        """Return the target model class, or None when it can no longer resolve."""
        if not self.content_type_id:
            return None
        return self.content_type.model_class()

    @property
    def model_label(self):
        """Return the target model's human-readable name.

        Falls back to the content type's own label when the model class can no
        longer be resolved, so a row for an uninstalled app still lists.
        """
        model = self.model_class
        if model is not None:
            return str(model._meta.verbose_name)
        if self.content_type_id:
            return str(self.content_type)
        return ""

    @property
    def model_field(self):
        """Return the target model field, or None when it no longer exists."""
        model = self.model_class
        if model is None or not self.field_name:
            return None
        try:
            return model._meta.get_field(self.field_name)
        except FieldDoesNotExist:
            return None

    @property
    def field_label(self):
        """Return the target field's human-readable name."""
        field = self.model_field
        if field is None:
            return self.field_name
        return str(field.verbose_name)

    @property
    def requirement_label(self):
        """Return a display label for the configured requiredness."""
        return _("Required") if self.is_required else _("Optional")

    def get_edit_url(self):
        """Return the URL for editing this override in the settings modal."""
        return reverse_lazy(
            "field_management:field_requirement_update_form",
            kwargs={"pk": self.pk},
        )

    def get_delete_url(self):
        """Return the URL for deleting this override from the settings page."""
        return reverse_lazy(
            "field_management:field_requirement_delete_view",
            kwargs={"pk": self.pk},
        )

    def clean(self):
        """Reject overrides that target unknown fields or would break saves."""
        super().clean()

        model = self.model_class
        if model is None:
            raise ValidationError({"content_type": _("Select a valid model.")})

        if not is_requirement_configurable(model):
            raise ValidationError(
                {
                    "content_type": _(
                        "%(model)s does not support configurable field requirements."
                    )
                    % {"model": model._meta.verbose_name}
                }
            )

        field = self.model_field
        if field is None:
            raise ValidationError(
                {
                    "field_name": _("%(field)s is not a field on %(model)s.")
                    % {"field": self.field_name, "model": model._meta.verbose_name}
                }
            )

        if self.field_name in get_excluded_fields(model):
            raise ValidationError({"field_name": _("This field cannot be configured.")})

        if not self.is_required and not can_relax_requirement(field):
            raise ValidationError(
                {
                    "is_required": _(
                        "%(field)s cannot be made optional because the database "
                        "has no way to store an empty value for it. Allow null "
                        "values on the field first."
                    )
                    % {"field": field.verbose_name}
                }
            )


# ---------------------------------------------------------------------------
# Form layouts
# ---------------------------------------------------------------------------


class FormLayoutField(HorillaCoreModel):
    """
    Per-company position and visibility of one field on a form.

    Only affects which fields are rendered when the "Custom Layout" form mode
    is active (an opt-in alongside the default form, on both create and edit
    requests) — the default form is never affected. A field the form
    requires is shown regardless of ``is_visible`` so a saved layout can
    never block a save; removing an optional field never touches its stored
    value on an existing record (see ``extensions/form_layouts.py``).
    """

    content_type = models.ForeignKey(
        HorillaContentType,
        on_delete=models.CASCADE,
        limit_choices_to=limit_form_layout_content_types,
        related_name="%(app_label)s_%(class)s_set",
        verbose_name=_("Model"),
    )
    field_name = models.CharField(max_length=255, verbose_name=_("Field"))
    is_visible = models.BooleanField(
        default=True,
        verbose_name=_("Show on Form"),
    )
    sequence = models.PositiveIntegerField(default=0, verbose_name=_("Sequence"))
    is_full_width = models.BooleanField(default=False, verbose_name=_("Full Width"))

    class Meta:
        """
        Meta options for the FormLayoutField model.
        """

        verbose_name = _("Form Layout Field")
        verbose_name_plural = _("Form Layout Fields")
        unique_together = (("content_type", "field_name", "company"),)
        ordering = ["content_type__model", "sequence", "pk"]

    def __str__(self):
        return f"{self.content_type} - {self.field_name}"

    @property
    def model_label(self):
        """Return the configured model's human-readable name."""
        model = self.content_type.model_class() if self.content_type_id else None
        if model is not None:
            return str(model._meta.verbose_name)
        return str(self.content_type) if self.content_type_id else ""

    @property
    def fields_shown(self):
        """Return "shown / total" for the layout this row belongs to."""
        rows = FormLayoutField.objects.filter(content_type_id=self.content_type_id)
        return f"{rows.filter(is_visible=True).count()} / {rows.count()}"

    def get_delete_url(self):
        """Return the endpoint that removes this row's whole layout."""
        return (
            f"{reverse_lazy('field_management:form_layout_reset')}"
            f"?model={self.content_type_id}"
        )

    def get_detail_url(self):
        """Return the layout detail page for this row's model."""
        return reverse_lazy(
            "field_management:form_layout_detail",
            kwargs={"ct": self.content_type_id},
        )


# ---------------------------------------------------------------------------
# Custom fields
# ---------------------------------------------------------------------------


def parse_choice_values(stored):
    """Return selected Multiple Choice values from stored text or a list."""
    if stored in (None, ""):
        return []
    if isinstance(stored, (list, tuple, set)):
        return [str(item) for item in stored if item not in (None, "")]
    text = str(stored).strip()
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if item not in (None, "")]
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return [text]


def serialize_choice_values(val):
    """Store Multiple Choice selections as a JSON list (legacy singles still parse)."""
    items = parse_choice_values(val)
    if not items:
        return ""
    return json.dumps(items, ensure_ascii=False)


def format_choice_display(val):
    """Join selected choices for detail, list, export, and inline display."""
    return ", ".join(parse_choice_values(val))


def to_date_value(val):
    """
    Return a Gregorian ``date`` from a date, datetime, or ISO string, else None.

    Date inputs always post ISO ``YYYY-MM-DD``; the Jalali picker converts
    Shamsi selections back to Gregorian before submit, so no calendar
    conversion is needed here.
    """
    if val in (None, ""):
        return None
    if isinstance(val, datetime):
        return timezone.localtime(val).date() if timezone.is_aware(val) else val.date()
    if isinstance(val, date):
        return val
    text = str(val).strip()
    try:
        return parse_date(text) or _date_from_datetime_text(text)
    except ValueError:
        return None


def _date_from_datetime_text(text):
    parsed = to_datetime_value(text)
    return timezone.localtime(parsed).date() if parsed else None


def to_datetime_value(val):
    """
    Return an aware ``datetime`` from a datetime, date, or ISO string, else None.

    Naive values (e.g. ``datetime-local`` input ``YYYY-MM-DDTHH:MM``) are read
    in the active timezone, matching how Django forms clean ``DateTimeField``.
    """
    if val in (None, ""):
        return None
    if isinstance(val, datetime):
        parsed = val
    elif isinstance(val, date):
        parsed = datetime(val.year, val.month, val.day)
    else:
        text = str(val).strip()
        try:
            parsed = parse_datetime(text)
            if parsed is None:
                day = parse_date(text)
                parsed = datetime(day.year, day.month, day.day) if day else None
        except ValueError:
            return None
        if parsed is None:
            return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


class CustomFieldDefinition(HorillaCoreModel):
    """
    Defines a user-created custom field attached to a specific model
    (currently Lead or Opportunity).
    """

    FIELD_TYPES = [
        ("small_text", _("Small Text")),
        ("large_text", _("Large Text")),
        ("number", _("Number")),
        ("choice", _("Multiple Choice")),
        ("single_choice", _("Single Choice")),
        ("date", _("Date")),
        ("datetime", _("Date and Time")),
    ]

    content_type = models.ForeignKey(
        HorillaContentType,
        on_delete=models.CASCADE,
        verbose_name=_("Model"),
    )
    name = models.CharField(max_length=255, verbose_name=_("Field Name"))
    field_type = models.CharField(
        max_length=20, choices=FIELD_TYPES, verbose_name=_("Field Type")
    )
    is_required = models.BooleanField(default=False, verbose_name=_("Required"))
    choices = models.TextField(
        blank=True,
        help_text=_("Comma-separated list of choices (only for Multiple Choice type)"),
        verbose_name=_("Choices"),
    )
    order = models.PositiveIntegerField(default=0, verbose_name=_("Display Order"))
    is_full_width = models.BooleanField(
        default=False,
        verbose_name=_("Full Width"),
        help_text=_("Span both columns of the form."),
    )

    class Meta:
        """Ordering and uniqueness for custom field definitions per company."""

        ordering = ["order", "pk"]
        unique_together = [("content_type", "name", "company")]
        verbose_name = _("Custom Field")
        verbose_name_plural = _("Custom Fields")

    def __str__(self):
        return f"{self.name}"

    def get_edit_url(self):
        """Return the HTMX edit URL for this definition."""
        return reverse_lazy(
            "field_management:custom_fields_edit", kwargs={"pk": self.pk}
        )

    def get_delete_url(self):
        """Return the HTMX delete URL for this definition."""
        return reverse_lazy(
            "field_management:custom_fields_delete", kwargs={"pk": self.pk}
        )

    def get_choices_list(self):
        """Return choice options as a stripped list of strings."""
        if not self.choices:
            return []
        return [c.strip() for c in self.choices.split(",") if c.strip()]


class CustomFieldValue(HorillaCoreModel):
    """
    Stores the value of a custom field for a specific object instance.
    """

    field_definition = models.ForeignKey(
        CustomFieldDefinition,
        on_delete=models.CASCADE,
        related_name="values",
        verbose_name=_("Field Definition"),
    )
    content_type = models.ForeignKey(
        HorillaContentType,
        on_delete=models.CASCADE,
        verbose_name=_("Model"),
    )
    object_id = models.PositiveIntegerField(verbose_name=_("Object ID"))

    value_text = models.TextField(blank=True, default="", verbose_name=_("Value"))
    value_number = models.DecimalField(
        max_digits=20,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name=_("Numeric Value"),
    )
    value_date = models.DateField(null=True, blank=True, verbose_name=_("Date Value"))
    value_datetime = models.DateTimeField(
        null=True, blank=True, verbose_name=_("Date and Time Value")
    )

    class Meta:
        """One value per definition and target object."""

        unique_together = [("field_definition", "content_type", "object_id")]
        verbose_name = _("Custom Field Value")
        verbose_name_plural = _("Custom Field Values")

    def __str__(self):
        return f"{self.field_definition.name}: {self.get_display_value()}"

    def get_value(self):
        """Return the typed Python value for this field's type."""
        field_type = self.field_definition.field_type
        if field_type == "number":
            return self.value_number
        if field_type == "date":
            return self.value_date
        if field_type == "datetime":
            return self.value_datetime
        if field_type == "choice":
            return parse_choice_values(self.value_text)
        if field_type == "single_choice":
            values = parse_choice_values(self.value_text)
            return values[0] if values else ""
        return self.value_text

    def get_display_value(self):
        """Return a user-facing string for list/detail display."""
        if self.field_definition.field_type in ("choice", "single_choice"):
            return format_choice_display(self.value_text)
        value = self.get_value()
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        return "" if value is None else str(value)

    def set_value(self, val):
        """Store ``val`` in the column for this field type and clear the others."""
        from decimal import Decimal, InvalidOperation

        field_type = self.field_definition.field_type
        self.value_text = ""
        self.value_number = None
        self.value_date = None
        self.value_datetime = None
        if field_type == "number":
            try:
                self.value_number = Decimal(str(val)) if val not in (None, "") else None
            except (InvalidOperation, ValueError):
                self.value_number = None
        elif field_type == "date":
            self.value_date = to_date_value(val)
        elif field_type == "datetime":
            self.value_datetime = to_datetime_value(val)
        elif field_type in ("choice", "single_choice"):
            self.value_text = serialize_choice_values(val)
        else:
            self.value_text = str(val) if val is not None else ""


# Django and Horilla store these on auth.Permission.name. Groups & Permissions
# gettext's perm.name for extra actions, and titles the row with verbose_name.
PERMISSION_UI_NAMES = (
    _("Can add Custom Field"),
    _("Can change Custom Field"),
    _("Can delete Custom Field"),
    _("Can view Custom Field"),
    _("Can create own Custom Field"),
    _("Can change own Custom Field"),
    _("Can delete own Custom Field"),
    _("Can view own Custom Field"),
    _("Can add Custom Field Value"),
    _("Can change Custom Field Value"),
    _("Can delete Custom Field Value"),
    _("Can view Custom Field Value"),
    _("Can create own Custom Field Value"),
    _("Can change own Custom Field Value"),
    _("Can delete own Custom Field Value"),
    _("Can view own Custom Field Value"),
)
