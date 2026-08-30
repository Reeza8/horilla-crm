# Multi-step form base (`horilla_generics/forms/multi_step.py`)

## Purpose

`HorillaMultiStepForm` is the base `ModelForm` for wizard-style workflows where fields are split across steps.

It combines:

- step-aware field visibility and validation
- persisted cross-step form data normalization
- file field continuity support
- Select2 pagination widgets for FK/M2M
- field permission handling (hidden/readonly) via `HorillaFormMixin`

This class is the form-side engine used by multi-step generic views.

---

## Class overview

```python
class HorillaMultiStepForm(HorillaFormMixin, forms.ModelForm):
    step_fields = {}
```

Key constructor kwargs consumed:

- `step` (current step number)
- `form_data` (accumulated data from previous steps/session)
- `full_width_fields`
- `dynamic_create_fields`
- `request`
- `field_permissions`

Internal state:

- `self.current_step`
- `self.form_data`
- `self.stored_files` (uploaded files present in current request)

---

## Initialization pipeline (`__init__`)

`__init__` performs a long setup pipeline; order matters.

## 1) Step map flattening, auto-assignment, and unsupported M2M removal

- flattens all fields listed in `step_fields`
- **auto-assigns unstepped fields to the last step** — any non-M2M field present in the form but not listed in any step is appended to `step_fields[max_step]`. This means `Meta.fields = "__all__"` works without having to enumerate every field explicitly.
- removes ManyToMany fields not present in any step
  - avoids accidental exposure of fields like `groups/user_permissions`.

## 2) Preserve original required flags

- stores `field._original_required`
- makes checkbox widgets non-required to avoid browser-level required quirks.

## 3) Capture uploaded files

- copies `request.FILES` to `self.files`
- mirrors entries into `self.stored_files` for later required checks.

## 4) Merge instance values into `form_data` (edit mode)

For missing/empty form_data keys, injects values from instance with type-aware conversion:

- FK -> pk
- M2M -> list of pks
- datetime -> `%Y-%m-%dT%H:%M`
- date -> `%Y-%m-%d`
- Decimal -> string
- bool -> bool
- Country -> string
- file/image -> filename + `<field>_filename`

## 5) Normalize `form_data` typing

Converts values for model compatibility:

- boolean string -> bool
- DateField strips `T` part
- DateTimeField ensures `T` segment exists
- CountryField -> string

Assigns normalized mapping to `self.data`.

## 6) Configure widgets

Calls `_configure_field_widgets()` for type-specific widgets/placeholders/select2 setup.

## 7) Apply permission-driven field removal

Calls:

- `_remove_fields_by_permission(skip_hidden_widget=True)`

inherited from `HorillaFormMixin`.

## 8) Apply phone field widgets

Calls:

- `_apply_phone_fields()`

inherited from `HorillaFormMixin`.

Replaces any `CharField` whose name matches the active phone field set (e.g. `phone`, `mobile`, `contact_number`, `fax`, etc.) with `PhoneField` — a country-code Select2 selector + number text input that stores `+XX NNNNNN` in the existing column, no migration required.

Subclasses can extend or disable this via the `phone_fields` class attribute. See `form_class_mixin.md` for full details.

## 9) Apply step visibility rules

For current step:

- fields not in step become hidden + non-required
- mandatory readonly/hidden fields in create mode may remain visible — resolved
  via `is_field_mandatory()`
- required flags for current-step fields are resolved via
  `resolve_field_required()`, which handles the boolean and
  already-uploaded-file exemptions before deferring to `is_field_required()`

Both hooks live on `HorillaFormMixin` — override `is_field_required()` there (or
on the form) rather than reassigning `required` here. See
[`form_class_mixin.md`](form_class_mixin.md#field-requiredness).

## 10) Apply readonly widget state from `field_permissions`

Readonly behavior differs by field type:

- select-like fields -> `disabled` + disabled styles
- text-like fields -> `readonly` + readonly styles/tabindex
- in create mode, mandatory readonly fields stay editable.

---

## Step behavior utilities

## `step_fields`

Mapping format:

```python
{
  1: ["name", "email"],
  2: ["department", "manager"],
  3: ["attachments"],
}
```

Determines:

- which fields appear per step
- which fields are hidden in each request
- which errors should be kept in `clean()`.

---

## `get_fields_for_step(step)`

Returns bound fields for given step.

Behavior:

- includes fields listed in `step_fields[step]` that exist in form
- if `step_fields` absent/empty -> returns `visible_fields()`

Used by templates/components rendering only current step inputs.

---

## Widget configuration engine

## `_configure_field_widgets()`

Applies type-aware widget behavior for all fields.

Highlights:

- File/Image fields:
  - manages required based on current step + existing/new file state
  - image inputs get `accept="image/*"`
  - adds `formnovalidate`
- Date fields:
  - `DateInput(type=date)` with `%Y-%m-%d`
- DateTime fields:
  - `DateTimeInput(type=datetime-local)` with multiple accepted input formats
- Time fields:
  - `TimeInput(type=time)`
- M2M fields:
  - if in any step -> configured with paginated select2 (`_configure_many_to_many_field`)
  - else hidden and non-required
- FK fields:
  - configured with paginated select2 (`_configure_foreign_key_field`)
- TextField:
  - converted to `Textarea`
- Boolean:
  - `CheckboxInput`
- generic placeholder/class defaults for remaining fields

Select/date/textarea/checkbox class adjustments are appended by widget type.

---

## Select2 FK/M2M configuration

## `_configure_many_to_many_field(...)`

Complex initial-value resolution priority:

1. instance selected values (edit mode)
2. `form_data` overrides (including stringified list parsing)
3. `initial` values

Then:

- cleans values to integer PK list
- loads selected object labels for initial options
- builds attrs via `_build_select2_m2m_attrs(...)`
- sets `SelectMultiple` with `_pagination_configured=True`.

## `_configure_foreign_key_field(...)`

Initial resolution:

1. instance FK pk
2. `initial`
3. `form_data`

Then:

- loads selected option label if object exists
- handles deleted/invalid initial IDs gracefully
- builds attrs via `_build_select2_fk_attrs(...)`
- sets select widget with `_pagination_configured=True`.

---

## Validation behavior (`clean`)

`clean()` extends default validation with step-awareness and readonly enforcement.

Pipeline:

1. `cleaned_data = super().clean()`
2. enforce readonly integrity:
   - `_enforce_readonly_in_cleaned_data(cleaned_data)`
3. remove errors for fields not in current step
4. apply file-field required checks for current step:
   - if required and no file from any source -> add required error
   - if blank allowed or file exists -> remove required-only errors

Returns cleaned_data.

This ensures users are blocked only by current step constraints while preserving file continuity.

---

## Interaction with `HorillaFormMixin`

Inherited helpers provide shared policy:

- `__init_subclass__` — auto-merges `HORILLA_FORM_EXCLUDE` (`company`, `is_active`, `created_at`, `updated_at`, `created_by`, `updated_by`, `additional_info`) into `Meta.exclude` at class definition time. Two escape hatches on `Meta`:
  - `keep_on_form = ("company",)` — removes a field from the base exclude list so it stays visible
  - `exclude = ("my_field",)` — adds extra exclusions; core fields are still excluded unless in `keep_on_form`
- `_remove_fields_by_permission`
- `_is_field_mandatory`
- `_enforce_readonly_in_cleaned_data`
- `_apply_phone_fields` — auto-replaces phone-named `CharField`s with `PhoneField`
- select/date/time attr builders

`HorillaMultiStepForm` adds step/session/file semantics on top of that common layer.

---

## Practical subclass example

```python
from horilla_generics.forms.multi_step import HorillaMultiStepForm
from employees.models import Employee


class EmployeeWizardForm(HorillaMultiStepForm):
    class Meta:
        model = Employee
        fields = "__all__"
        # HorillaCoreModel audit fields (company, is_active, created_at, etc.)
        # are excluded automatically — no need to list them here.
        # Use exclude to hide additional fields:
        exclude = ["employee_score"]
        # Use keep_on_form to show a field that would otherwise be auto-excluded:
        # keep_on_form = ("company",)

    step_fields = {
        1: ["first_name", "last_name", "email"],
        2: ["department", "manager", "joining_date"],
        3: ["profile_image", "resume"],
        # Any fields present in Meta.fields but not listed in any step are
        # automatically appended to the last step (step 3 here).
    }
```

View layer typically instantiates with:

- `step=<current_step>`
- `form_data=<session_accumulated_data>`
- `field_permissions=<user/model field permissions>`

---

## Caveats and implementation notes

- Constructor is intentionally heavy; keep kwargs complete and consistent from view flow.
- `__init_subclass__` runs at class definition time — `Meta.exclude` is patched before any instance is created. If you manually set `Meta.exclude` after class definition it will be overwritten on the next subclass; always use `keep_on_form` instead.
- Auto-assignment of unstepped fields to the last step applies to non-M2M fields only. M2M fields not listed in any step are removed from the form entirely.
- M2M initial parsing handles stringified lists (`"[1,2]"`) defensively, but malformed payloads can still lead to dropped values.
- Hidden-field/readonly interactions are nuanced; mandatory readonly fields remain visible in create mode by design.
- File required logic depends on stored filename markers (`<field>_filename`, `<field>_new_file`) in form data/session conventions.
- `self.data` is rewritten to normalized dict; debugging should inspect post-normalization state.

---

## Summary

`HorillaMultiStepForm` is the core form engine for wizard workflows in Horilla. It orchestrates step-based field visibility, permission-aware readonly/hidden behavior, robust file persistence checks, and dynamic FK/M2M widget configuration while preserving consistent validation semantics per step.
