# Form class mixin (`horilla_generics/forms/form_class_mixin.py`)

## Purpose

`form_class_mixin.py` defines shared form-class behavior used by both:

- `HorillaModelForm` (single-step)
- `HorillaMultiStepForm` (wizard/multi-step)

It centralizes:

- field-permission based field removal
- readonly enforcement at clean-time (anti-tampering)
- reusable widget attribute builders (Select2/date/time/etc.)

This avoids duplication and keeps permission/widget behavior consistent across form types.

---

## Constants for consistent widget styling

Module-level CSS constants:

- `WIDGET_INPUT_CSS_CLASS`
- `WIDGET_INPUT_CSS_CLASS_NO_PR`
- `WIDGET_TIME_CSS_CLASS`
- `SELECT_READONLY_CLASS_SUFFIX`

These ensure single-step and multi-step forms render inputs/selects with unified visual style.

---

## `HorillaFormMixin`

Main shared mixin class.

Responsibilities:

- remove fields according to `field_permissions`
- preserve mandatory fields in create/duplicate mode
- enforce readonly constraints in cleaned data
- build standardized attrs for select2/date/datetime/time widgets

Expected form attributes:

- `field_permissions` mapping (`field -> readwrite|readonly|hidden`)
- `instance`
- optional `duplicate_mode`
- `self._meta.model`

---

## Permission-driven field removal

## `_remove_fields_by_permission(...)`

Arguments:

- `skip_field_names=()`
- `duplicate_mode=False`
- `skip_hidden_widget=False`

Behavior:

1. exits early if no `field_permissions`,
2. determines mode:
   - create (`instance` missing pk)
   - duplicate (from form attr or argument),
3. iterates current form fields,
4. skips protected names and optionally hidden widgets,
5. applies rules:
   - `hidden`:
     - remove in edit mode
     - in create/duplicate, remove only if not mandatory
   - `readonly` in create/duplicate:
     - remove only if not mandatory
6. deletes accumulated fields.

Why important:

- hidden/readonly permissions should not remove required inputs in create/duplicate flows.

---

## Field requiredness

Requiredness is asked in **two distinct ways**, and both resolve here so an
override only has to be made in one place. They are *not* interchangeable — a
field declared `null=True, blank=False` is required on the form but not
mandatory at the database level.

| Hook | Question | Default rule |
|------|----------|--------------|
| `is_field_required(field_name, field=None, model_field=None)` | Should the **form** field be marked `required`? | Admin-configured override, else `not model_field.blank` (Django's `ModelForm` rule) |
| `is_field_mandatory(field_name, field=None, model_field=None, fallback=None)` | Can the **column** reject an empty value? | `not null and not blank` |

### `is_field_required(...)`

The hook to override when relaxing or tightening requiredness. Override this
rather than assigning `self.fields[name].required` at individual call sites:

```python
class LeadFormOptionalEmail(FormExtension):
    _inherit_form = "horilla_crm.leads.forms.LeadFormClass"

    def setup_form_extension_fields(self):
        self.fields["email"].required = False
```

Before applying the model's `blank` flag, the hook consults
`field_requirement_overrides` — the per-company settings configured on the
[Field Requirements](../../core/field_requirements.md) page. Only fields an
admin explicitly configured appear there, so forms are unchanged wherever
nothing is set.

> **Warning:** relaxing requiredness only reaches the database safely for
> columns that accept an empty value — text-like fields (`""`) or anything with
> `null=True`. A non-nullable `ForeignKey`, numeric, or date field will raise
> `IntegrityError` on save. The settings page enforces this via
> `can_relax_requirement`; code that overrides this hook directly is
> responsible for it.

### `field_requirement_overrides`

Cached mapping of `{field_name: bool}` for the form's model, resolved once per
form instance so field count does not affect query count. Empty for models that
have not opted in via `@configurable_field_requirements`.

### `apply_field_requirement_overrides()`

Re-resolves `required` for the configured fields only. Single-step forms call
this at the end of `__init__` because Django derives `required` from `blank`
once when the field is built and never revisits it. Multi-step forms do not
need it — they already resolve per step through `resolve_field_required`.

### `is_field_mandatory(...)`

Used to keep a field editable even when field permissions mark it readonly or
hidden, since the record could not otherwise be saved. `fallback` is returned
when the form field has no model counterpart; when omitted, the field's
pre-step `_original_required` flag (or its current `required` flag) is used.

Consumed by `_remove_fields_by_permission`, `_should_disable_select_for_permission`,
`_readonly_for_datetime_like_field`, and the multi-step permission pass.

### `resolve_field_required(field_name)`

Applies widget-level exemptions before deferring to `is_field_required`:

- `BooleanField` -> always `False` (a required checkbox would force a tick)
- `FileField`/`ImageField` that is `blank=True` and already holds a value ->
  `False`, so the user is not made to re-upload
- otherwise -> `is_field_required(...)`

Used by `HorillaMultiStepForm` when marking current-step fields.

### `_get_model_field(field_name)`

Returns the model field, or `None` when the form field has no model counterpart
(declared fields, condition rows, fields rebuilt by subclasses).

### `_is_field_mandatory(field_name, field)`

Deprecated alias for `is_field_mandatory`, kept for subclasses that call it.

---

## Readonly enforcement in `clean()`

## `_enforce_readonly_in_cleaned_data(cleaned_data)`

Server-side safety check for edit mode.

Runs only when:

- `field_permissions` present
- editing existing instance (`instance.pk`)

Flow per readonly field:

1. resolve model field type
2. compute original value from instance:
   - M2M -> list of related objects
   - FK/scalar -> attribute
3. compare original vs submitted using type-aware logic:
   - M2M by pk set
   - FK by related pk
   - scalar by direct value
4. if changed:
   - restore original value in `cleaned_data`
   - add `ValidationError(code="readonly_field")`
5. if unchanged:
   - still normalize cleaned value back to original

This prevents client-side tampering from bypassing readonly UI.

---

## Select/FK/M2M permission helpers

## `_should_disable_select_for_permission(field_name, model_field)`

Returns whether select-like widget should be disabled for readonly permissions.

Logic:

- only applies when permission is `readonly`
- in create/duplicate mode:
  - mandatory fields remain enabled
- otherwise disabled

Used when deciding widget interactivity for FK/M2M/select controls.

---

## `_apply_readonly_to_select_attrs(attrs)`

Mutates attrs for readonly select appearance:

- adds `disabled` + `data-disabled`
- appends readonly visual class suffix:
  - `bg-gray-100 cursor-not-allowed opacity-60`

Provides consistent readonly style for select widgets.

---

## Select2 attribute builders

## `_build_select2_m2m_attrs(...)`

Builds attrs for M2M select2 widget with pagination.

Includes:

- `data-url` -> `horilla_generics:model_select2`
- placeholder text from model verbose name
- `multiple=true`
- `data-initial` as comma-joined selected IDs
- `data-field-name`, `id`, `data-form-class`
- optional `data-object-id`
- optional `data-parent-model` for runtime `DynamicForm`

Used by form classes to initialize M2M select widgets uniformly.

---

## `_build_select2_fk_attrs(...)`

FK counterpart of M2M builder.

Differences:

- no `multiple`
- `data-initial` is single selected ID string
- same endpoint/metadata conventions as M2M builder

---

## Date/time widget attribute builders

## `_build_datetime_widget_attrs(existing_attrs=None, readonly=False)`

Returns attrs for `datetime-local` input:

- `type=datetime-local`
- shared no-right-padding input class
- optional `readonly`

## `_build_date_widget_attrs(existing_attrs=None, readonly=False)`

Returns attrs for `date` input:

- `type=date`
- shared no-right-padding class
- optional `readonly`

## `_build_time_widget_attrs(existing_attrs=None, readonly=False, extra_style=None)`

Returns attrs for `time` input:

- `type=time`
- time-specific CSS class
- optional extra inline style (icon spacing etc.)
- optional `readonly`

These builders standardize widget attrs and reduce repeated widget setup code.

---

## Automatic phone field widget injection

## `_apply_phone_fields()`

Auto-applies `PhoneField` (country-code Select2 + number input) to any `CharField` whose name matches the active phone field name set.

Called at the end of `__init__` in both `HorillaModelForm` and `HorillaMultiStepForm` — no per-form setup required.

### Default field names

```python
_DEFAULT_PHONE_FIELD_NAMES = {
    "phone", "mobile", "contact_number", "phone_number", "mobile_number",
    "secondary_phone", "assistant_phone", "fax", "whatsapp", "telephone",
    "cell", "cell_number", "alt_phone", "alternate_phone",
}
```

### Subclass override: `phone_fields`

Declare `phone_fields` on any subclass to control which fields get the phone widget:

```python
# Add extra field names on top of the defaults
class MyForm(HorillaModelForm):
    phone_fields = ["work_phone", "home_phone"]

# Opt out entirely — no phone widgets on this form
class MyForm(HorillaModelForm):
    phone_fields = []
```

Rules:

| `phone_fields` value | Active set |
|---|---|
| Not declared (default) | `_DEFAULT_PHONE_FIELD_NAMES` |
| `["work_phone"]` | `_DEFAULT_PHONE_FIELD_NAMES` ∪ `{"work_phone"}` |
| `[]` | None — method returns early, no phone widgets applied |

### Behavior per field

For each matching field the method:

1. skips if already a `PhoneField` (idempotent)
2. skips if not a plain `CharField` (FK, M2M, etc. are left untouched)
3. reads the current instance value (edit mode) and sets it as `initial`
4. replaces the field with a new `PhoneField` preserving `label` and `required`

Storage format is `+XX NNNNNN` in the existing `CharField` — **no migration needed**.

---

## Integration in form classes

`HorillaModelForm` and `HorillaMultiStepForm` typically use this mixin to:

- remove disallowed fields early,
- enforce readonly integrity during cleaning,
- apply unified attrs on dynamic FK/M2M/date/time widgets,
- auto-apply phone widgets to phone-named fields.

Typical pattern:

1. initialize fields and permissions
2. call `_remove_fields_by_permission(...)`
3. call `_apply_phone_fields()`
4. build/assign widget attrs via builder helpers
5. in `clean()`, call `_enforce_readonly_in_cleaned_data(cleaned_data)`

---

## Practical example (conceptual)

```python
class MyForm(HorillaFormMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.field_permissions = kwargs.pop("field_permissions", {})
        super().__init__(*args, **kwargs)
        self._remove_fields_by_permission(
            skip_field_names=("condition_fields",),
            duplicate_mode=kwargs.get("duplicate_mode", False),
        )

    def clean(self):
        cleaned = super().clean()
        self._enforce_readonly_in_cleaned_data(cleaned)
        return cleaned
```

---

## Caveats

- Readonly enforcement runs only in edit mode; create/duplicate rely on field removal/visibility decisions.
- M2M/FK comparison logic assumes submitted cleaned values are model instances (typical Django behavior).
- `data-parent-model` is added only for class name `DynamicForm`; custom dynamic class names may need override.
- Widget class constants are global; project-specific theme changes may require updating these shared strings.
- `_apply_phone_fields()` only replaces plain `CharField` instances. Fields already typed as something other than `CharField` (e.g. custom field classes) are skipped silently.
- `phone_fields = []` on a subclass opts out completely for that form, including all defaults. Use a specific list if you only want to suppress one field while keeping others.
- `_apply_phone_fields()` is called after `_remove_fields_by_permission()`, so fields already removed by permission rules are not affected.

---

## Summary

`form_class_mixin.py` is the shared policy and widget utility layer for Horilla forms. It enforces field-permission behavior consistently, protects readonly fields from tampering, standardizes complex widget attribute construction across single-step and multi-step form implementations, and automatically applies country-code phone widgets to phone-named fields across the entire form system.
