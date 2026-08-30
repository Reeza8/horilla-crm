"""
Shared base and mixins for Horilla model forms.

Provides common field-permission removal, readonly enforcement, and
widget/initial configuration used by both HorillaModelForm and HorillaMultiStepForm.
"""

# Standard library imports
import logging

# Third-party imports (Django)
from django import forms

# First party imports (Horilla)
from horilla.core.exceptions import FieldDoesNotExist
from horilla.db import models
from horilla.urls import reverse_lazy
from horilla.utils.functional import cached_property
from horilla.utils.translation import gettext_lazy as _

# Local imports
from .constants import HORILLA_FORM_EXCLUDE

logger = logging.getLogger(__name__)

# Shared widget CSS classes (single-step and multi-step use the same styling)
WIDGET_INPUT_CSS_CLASS = (
    "text-color-600 p-2 placeholder:text-xs pr-[40px] w-full border border-dark-50 "
    "rounded-md mt-1 focus-visible:outline-0 placeholder:text-dark-100 text-sm "
    "[transition:.3s] focus:border-primary-600"
)
WIDGET_INPUT_CSS_CLASS_NO_PR = (
    "text-color-600 p-2 placeholder:text-xs w-full border border-dark-50 rounded-md "
    "mt-1 focus-visible:outline-0 placeholder:text-dark-100 text-sm [transition:.3s] "
    "focus:border-primary-600"
)
WIDGET_TIME_CSS_CLASS = (
    "text-color-600 p-2 placeholder:text-xs pr-[40px] w-full border border-dark-50 "
    "rounded-md mt-1 focus-visible:outline-0 placeholder:text-dark-100 text-sm "
    "transition duration-300 focus:border-primary-600"
)
SELECT_READONLY_CLASS_SUFFIX = " bg-gray-100 cursor-not-allowed opacity-60"


def apply_horilla_form_meta_exclude(meta) -> None:
    """
    Merge ``HORILLA_FORM_EXCLUDE`` into ``Meta.exclude``, honoring ``keep_on_form``.

    Used by ``HorillaFormMixin.__init_subclass__`` and composed form extensions
    (``new_class`` runs ``__init_subclass__`` before extension ``Meta`` is attached).
    """
    if meta is None:
        return
    keep_on_form = set(getattr(meta, "keep_on_form", ()) or ())
    child_exclude = list(getattr(meta, "exclude", None) or [])
    # Parent forms may already have core fields in exclude; re-apply from scratch.
    child_exclude = [f for f in child_exclude if f not in HORILLA_FORM_EXCLUDE]
    base_exclude = [f for f in HORILLA_FORM_EXCLUDE if f not in keep_on_form]
    merged = child_exclude + [f for f in base_exclude if f not in child_exclude]
    meta.exclude = merged


class HorillaFormMixin:
    """
    Mixin with shared logic for HorillaModelForm and HorillaMultiStepForm:
    - Auto-excluding HorillaCoreModel audit fields via __init_subclass__
    - Removing fields based on field_permissions (hidden/readonly)
    - Enforcing readonly in clean() by restoring original values and adding errors

    Meta escape hatches (on any subclass):
    * ``keep_on_form`` — fields to remove from the base exclude list (shown on form).
    * ``exclude`` — extra fields added to the merged list; core fields still excluded
      unless listed in ``keep_on_form``.
    """

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        meta = cls.__dict__.get("Meta")
        if meta is None:
            return
        apply_horilla_form_meta_exclude(meta)

    def _remove_fields_by_permission(
        self,
        skip_field_names=(),
        duplicate_mode=False,
        skip_hidden_widget=False,
    ):
        """
        Remove form fields based on field_permissions (hidden, readonly).
        In create/duplicate mode, mandatory fields are never removed.

        Args:
            skip_field_names: Field names to never remove (e.g. condition_fields, hidden_fields).
            duplicate_mode: If True, treat like create mode for mandatory checks (HorillaModelForm).
            skip_hidden_widget: If True, skip fields that already use HiddenInput (HorillaMultiStepForm).
        """
        field_permissions = getattr(self, "field_permissions", None) or {}
        if not field_permissions:
            return

        is_create_mode = not (self.instance and self.instance.pk)
        is_duplicate_mode = getattr(self, "duplicate_mode", False) or duplicate_mode
        fields_to_remove = []

        for field_name, field in list(self.fields.items()):
            if field_name in skip_field_names:
                continue
            if skip_hidden_widget and isinstance(field.widget, forms.HiddenInput):
                continue

            permission = field_permissions.get(field_name, "readwrite")

            if permission == "hidden":
                if is_create_mode or is_duplicate_mode:
                    is_mandatory = self.is_field_mandatory(field_name, field=field)
                    if not is_mandatory:
                        fields_to_remove.append(field_name)
                else:
                    fields_to_remove.append(field_name)
            elif permission == "readonly" and (is_create_mode or is_duplicate_mode):
                is_mandatory = self.is_field_mandatory(field_name, field=field)
                if not is_mandatory:
                    fields_to_remove.append(field_name)

        for field_name in fields_to_remove:
            if field_name in self.fields:
                del self.fields[field_name]

    # --- Field requiredness -------------------------------------------------
    #
    # The form layer asks about requiredness in two distinct ways, and both are
    # resolved here so an override only has to be made in one place:
    #
    #   is_field_required()  -- should the *form* field be marked required?
    #   is_field_mandatory() -- can the *column* reject an empty value?
    #
    # They are not interchangeable: a field declared ``null=True, blank=False``
    # is required on the form but not mandatory at the database level.

    def _get_model_field(self, field_name):
        """Return the model field for ``field_name``, or None when there is none.

        Form fields need not map to model fields (declared fields, condition
        rows, and fields rebuilt by subclasses all lack a model counterpart).
        """
        try:
            return self._meta.model._meta.get_field(field_name)
        except (AttributeError, FieldDoesNotExist):
            return None

    @cached_property
    def field_requirement_overrides(self):
        """Return the admin-configured requiredness overrides for this model.

        Resolved once per form instance, so the number of form fields does not
        affect the query count. Empty for models that have not opted in to
        configurable requiredness.
        """
        from horilla.contrib.core.utils import get_field_requirements_for_model

        model = getattr(getattr(self, "_meta", None), "model", None)
        if model is None:
            return {}
        try:
            return get_field_requirements_for_model(model)
        except Exception:
            # Never let a settings lookup stop a form from rendering; fall back
            # to the requiredness declared on the model.
            logger.exception("Could not load field requirement overrides for %s", model)
            return {}

    def is_field_required(self, field_name, field=None, model_field=None):
        """Return whether the form field should be marked ``required``.

        Defaults to Django's ``ModelForm`` rule (``required = not blank``), then
        lets an admin-configured override win. Override this method to change
        requiredness in code instead of assigning ``self.fields[name].required``
        at each call site.

        Args:
            field_name: Name of the field on the form.
            field: Form field, used for the fallback when there is no model field.
            model_field: Resolved model field, when the caller already has it.
        """
        override = self.field_requirement_overrides.get(field_name)
        if override is not None:
            return override
        if model_field is None:
            model_field = self._get_model_field(field_name)
        if model_field is not None and hasattr(model_field, "blank"):
            return not model_field.blank
        if field is None:
            field = self.fields.get(field_name)
        return bool(getattr(field, "required", False))

    def apply_field_requirement_overrides(self):
        """Re-resolve ``required`` for fields an admin explicitly configured.

        Single-step forms inherit ``required`` from Django, which derives it
        from ``blank`` when the field is built and never revisits it. Only the
        configured fields are touched, so forms behave exactly as before
        wherever nothing has been configured.

        Multi-step forms do not need this: they already resolve requiredness
        per step through :meth:`resolve_field_required`.
        """
        for field_name in self.field_requirement_overrides:
            if field_name in self.fields:
                self.fields[field_name].required = self.resolve_field_required(
                    field_name
                )

    def is_field_mandatory(
        self, field_name, field=None, model_field=None, fallback=None
    ):
        """Return whether the database rejects an empty value for this field.

        Distinct from :meth:`is_field_required`: this asks whether the column
        itself may be left empty (``null`` and ``blank`` both ``False``). It
        keeps a field editable even when field permissions mark it readonly or
        hidden, since the record could not otherwise be saved.

        Args:
            field_name: Name of the field on the form.
            field: Form field, used for the fallback.
            model_field: Resolved model field, when the caller already has it.
            fallback: Returned when there is no model field. When ``None``, the
                field's pre-step ``_original_required`` flag (or its current
                ``required`` flag) is used instead.
        """
        if model_field is None:
            model_field = self._get_model_field(field_name)
        if (
            model_field is not None
            and hasattr(model_field, "null")
            and hasattr(model_field, "blank")
        ):
            return not model_field.null and not model_field.blank
        if fallback is not None:
            return fallback
        if field is None:
            field = self.fields.get(field_name)
        return bool(
            getattr(field, "_original_required", getattr(field, "required", False))
        )

    def resolve_field_required(self, field_name):
        """Resolve ``required`` for a field, applying widget-level exemptions.

        Booleans are always optional (a required checkbox would force the box to
        be ticked), and file fields that already hold a value stay optional so
        the user is not made to re-upload. Everything else defers to
        :meth:`is_field_required`.
        """
        field = self.fields[field_name]
        model_field = self._get_model_field(field_name)
        if model_field is None or not hasattr(model_field, "blank"):
            return field.required
        if isinstance(model_field, models.BooleanField):
            return False
        if (
            isinstance(model_field, (models.FileField, models.ImageField))
            and model_field.blank
            and self._has_file_value(field_name)
        ):
            return False
        return self.is_field_required(field_name, field=field, model_field=model_field)

    def _has_file_value(self, field_name):
        """Return True when a file value is already present for ``field_name``."""
        instance = getattr(self, "instance", None)
        if (
            instance
            and getattr(instance, "pk", None)
            and getattr(instance, field_name, None)
        ):
            return True
        if field_name in (getattr(self, "stored_files", None) or {}):
            return True
        return f"{field_name}_filename" in (getattr(self, "form_data", None) or {})

    def _is_field_mandatory(self, field_name, field):
        """Deprecated alias for :meth:`is_field_mandatory`."""
        return self.is_field_mandatory(field_name, field=field)

    def _enforce_readonly_in_cleaned_data(self, cleaned_data):
        """
        Enforce readonly field permissions in edit mode: restore original values
        for readonly fields and add validation errors if the user changed them.
        Modifies cleaned_data in place and adds errors to self.
        """
        field_permissions = getattr(self, "field_permissions", None) or {}
        if not field_permissions or not (self.instance and self.instance.pk):
            return

        for field_name, permission in field_permissions.items():
            if permission != "readonly" or field_name not in self.fields:
                continue
            try:
                model_field = self._meta.model._meta.get_field(field_name)
            except Exception:
                continue

            if isinstance(model_field, models.ManyToManyField):
                original_value = list(getattr(self.instance, field_name).all())
            elif isinstance(model_field, models.ForeignKey):
                original_value = getattr(self.instance, field_name, None)
            else:
                original_value = getattr(self.instance, field_name, None)

            submitted_value = cleaned_data.get(field_name)
            value_changed = False

            if isinstance(model_field, models.ManyToManyField):
                original_pks = (
                    set(obj.pk for obj in original_value) if original_value else set()
                )
                submitted_pks = (
                    set(obj.pk for obj in submitted_value) if submitted_value else set()
                )
                value_changed = original_pks != submitted_pks
            elif isinstance(model_field, models.ForeignKey):
                original_pk = original_value.pk if original_value else None
                submitted_pk = submitted_value.pk if submitted_value else None
                value_changed = original_pk != submitted_pk
            else:
                value_changed = original_value != submitted_value

            if value_changed:
                cleaned_data[field_name] = original_value
                self.add_error(
                    field_name,
                    forms.ValidationError(
                        _("This field is read-only and cannot be modified."),
                        code="readonly_field",
                    ),
                )
            else:
                cleaned_data[field_name] = original_value

    # Default phone field names — automatically get PhoneField widget.
    # Subclasses can extend with extra names:
    #   phone_fields = ["work_phone", "home_phone"]
    # Or disable entirely:
    #   phone_fields = []
    _DEFAULT_PHONE_FIELD_NAMES = {
        "phone",
        "mobile",
        "contact_number",
        "phone_number",
        "mobile_number",
        "secondary_phone",
        "assistant_phone",
        "secondary_contact_number",
        "assistant_contact_number",
        "fax",
        "whatsapp",
        "telephone",
        "cell",
        "cell_number",
        "alt_phone",
        "alternate_phone",
    }

    def _apply_default_time_zone(self):
        """Default a blank ``time_zone`` field to the requesting user's/company's
        configured time zone instead of the model's hardcoded "UTC" default.

        Only applies when creating a new record (no instance pk) and no explicit
        initial/submitted value is already present for the field.
        """
        field = self.fields.get("time_zone")
        if not field or (self.instance and self.instance.pk):
            return
        if self.initial.get("time_zone") or (self.data and self.data.get("time_zone")):
            return

        request = getattr(self, "request", None)
        user = getattr(request, "user", None) if request else None
        if not user or not getattr(user, "is_authenticated", False):
            return

        time_zone = getattr(user, "time_zone", None) or getattr(
            getattr(user, "company", None), "time_zone", None
        )
        if time_zone:
            self.initial["time_zone"] = time_zone

    def _apply_phone_fields(self):
        """Replace CharFields whose names are in the phone field set with PhoneField.

        Subclass override examples::

            # Add extra field names on top of defaults
            phone_fields = ["work_phone", "home_phone"]

            # Opt out entirely
            phone_fields = []
        """
        from horilla.contrib.generics.forms.generics import PhoneField

        phone_fields_attr = self.__class__.__dict__.get("phone_fields", None)
        if phone_fields_attr is None:
            # Not declared on this class — check MRO for any parent override
            phone_fields_attr = getattr(self.__class__, "phone_fields", None)

        if phone_fields_attr is None:
            active_names = self._DEFAULT_PHONE_FIELD_NAMES
        elif len(phone_fields_attr) == 0:
            return  # opted out
        else:
            active_names = self._DEFAULT_PHONE_FIELD_NAMES | set(phone_fields_attr)

        for field_name, field in list(self.fields.items()):
            if field_name not in active_names:
                continue
            if isinstance(field, PhoneField):
                continue
            if not isinstance(field, forms.CharField):
                continue
            current_value = (
                getattr(self.instance, field_name, None)
                if hasattr(self, "instance")
                and self.instance
                and getattr(self.instance, "pk", None)
                else None
            )
            phone_field = PhoneField(label=field.label, required=field.required)
            if current_value:
                phone_field.initial = current_value
            self.fields[field_name] = phone_field

    # --- Shared widget / initial helpers (each form gets initials its own way, same attrs) ---

    def _should_disable_select_for_permission(self, field_name, model_field):
        """Return True if this FK/M2M/Select should be disabled (readonly and not mandatory in create/duplicate)."""
        field_permissions = getattr(self, "field_permissions", None) or {}
        permission = field_permissions.get(field_name, "readwrite")
        if permission != "readonly":
            return False
        is_create_mode = not (self.instance and self.instance.pk)
        is_duplicate_mode = getattr(self, "duplicate_mode", False)
        is_mandatory = self.is_field_mandatory(
            field_name, model_field=model_field, fallback=False
        )
        return not ((is_create_mode or is_duplicate_mode) and is_mandatory)

    def _apply_readonly_to_select_attrs(self, attrs):
        """Mutate attrs to add disabled and readonly styling for select widgets."""
        attrs["disabled"] = "disabled"
        attrs["data-disabled"] = "true"
        existing = attrs.get("class", "")
        if SELECT_READONLY_CLASS_SUFFIX.strip() not in existing:
            attrs["class"] = f"{existing}{SELECT_READONLY_CLASS_SUFFIX}".strip()

    def _build_select2_m2m_attrs(
        self,
        field_name,
        model_field,
        initial_value,
        object_id=None,
        existing_attrs=None,
    ):
        """Build widget attrs for a ManyToManyField with select2-pagination. Caller sets initial_value source."""
        related_model = model_field.related_model
        app_label = related_model._meta.app_label
        model_name = related_model._meta.model_name
        data_initial = ",".join(map(str, initial_value)) if initial_value else ""
        attrs = {
            "class": "select2-pagination w-full text-sm",
            "data-url": reverse_lazy(
                "generics:model_select2",
                kwargs={"app_label": app_label, "model_name": model_name},
            ),
            "data-placeholder": _("Select %(field)s")
            % {"field": model_field.verbose_name.title()},
            "multiple": "multiple",
            "data-initial": data_initial,
            "data-field-name": field_name,
            "id": f"id_{field_name}",
            "data-form-class": getattr(
                self.__class__,
                "__horilla_form_path__",
                f"{self.__module__}.{self.__class__.__name__}",
            ),
            **(existing_attrs or {}),
        }
        if object_id is not None:
            attrs["data-object-id"] = str(object_id)
        if self.__class__.__name__ == "DynamicForm":
            attrs["data-parent-model"] = (
                f"{self._meta.model._meta.app_label}.{self._meta.model._meta.model_name}"
            )
        return attrs

    def _build_select2_fk_attrs(
        self,
        field_name,
        model_field,
        initial_value,
        object_id=None,
        existing_attrs=None,
    ):
        """Build widget attrs for a ForeignKey with select2-pagination. Caller sets initial_value source."""
        related_model = model_field.related_model
        app_label = related_model._meta.app_label
        model_name = related_model._meta.model_name
        attrs = {
            "class": "select2-pagination w-full",
            "data-url": reverse_lazy(
                "generics:model_select2",
                kwargs={"app_label": app_label, "model_name": model_name},
            ),
            "data-placeholder": _("Select %(field)s")
            % {"field": model_field.verbose_name.title()},
            "data-initial": str(initial_value) if initial_value is not None else "",
            "data-field-name": field_name,
            "id": f"id_{field_name}",
            "data-form-class": getattr(
                self.__class__,
                "__horilla_form_path__",
                f"{self.__module__}.{self.__class__.__name__}",
            ),
            **(existing_attrs or {}),
        }
        if object_id is not None:
            attrs["data-object-id"] = str(object_id)
        if self.__class__.__name__ == "DynamicForm":
            attrs["data-parent-model"] = (
                f"{self._meta.model._meta.app_label}.{self._meta.model._meta.model_name}"
            )
        return attrs

    def _build_datetime_widget_attrs(self, existing_attrs=None, readonly=False):
        """Build attrs for DateTimeInput (type=datetime-local)."""
        base = {
            "type": "datetime-local",
            "class": WIDGET_INPUT_CSS_CLASS_NO_PR,
            **(existing_attrs or {}),
        }
        if readonly:
            base["readonly"] = "readonly"
        return base

    def _build_date_widget_attrs(self, existing_attrs=None, readonly=False):
        """Build attrs for DateInput (type=date)."""
        base = {
            "type": "date",
            "class": WIDGET_INPUT_CSS_CLASS_NO_PR,
            **(existing_attrs or {}),
        }
        if readonly:
            base["readonly"] = "readonly"
        return base

    def _build_time_widget_attrs(
        self, existing_attrs=None, readonly=False, extra_style=None
    ):
        """Build attrs for TimeInput (type=time). extra_style for e.g. clock icon (single-step)."""
        base = {
            "type": "time",
            "class": WIDGET_TIME_CSS_CLASS,
            **(existing_attrs or {}),
        }
        if extra_style:
            base["style"] = extra_style
        if readonly:
            base["readonly"] = "readonly"
        return base
