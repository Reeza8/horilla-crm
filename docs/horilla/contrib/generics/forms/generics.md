# Generic forms (`horilla_generics/forms/generics.py`)

## Purpose

`generics.py` is the shared form collection for multiple Horilla generic view features.

It includes forms/widgets for:

- Kanban/GroupBy configuration
- Timeline span settings
- List column selection
- Saved filter list naming
- Password input UX helper
- History date filtering
- Row-composed field rendering
- Phone number input with country-code selector
- Attachment create/edit (title/file/description)

This module is a mixed "form toolkit" rather than a single feature file.

---

## Form classes at a glance

- `KanbanGroupByForm` (`ModelForm`)
- `TimelineSpanByForm` (`ModelForm`)
- `ColumnSelectionForm` (`Form`)
- `SaveFilterListForm` (`Form`)
- `HorillaHistoryForm` (`Form`)
- `HorillaAttachmentForm` (`ModelForm`)

Custom widgets/fields:

- `PasswordInputWithEye`
- `RowFieldWidget`
- `RowField`
- `CustomFileInput`
- `PhoneWidget`
- `PhoneField`

---

## `KanbanGroupByForm`

Backs persisted group-by settings for kanban/group-by views.

Model:

- `horilla_core.models.KanbanGroupBy`

Fields:

- `model_name` (hidden)
- `app_label` (hidden)
- `view_type` (hidden)
- `field_name` (select)

### Dynamic choice loading

In `__init__`:

- resolves model/app from posted data, initial values, or instance
- builds available group fields via:
  - `KanbanGroupBy(...).get_model_groupby_fields(...)`
- respects `exclude_fields` / `include_fields` passed in kwargs
- uses thread-local request user for permission-aware filtering.

### Validation

`clean()` instantiates temp `KanbanGroupBy` and calls model `clean()`:

- adds error to `field_name` if invalid
- ensures selected group-by field is legal for target model/view type.

---

## `TimelineSpanByForm`

Backs timeline start/end field preferences.

Model:

- `horilla_core.models.TimelineSpanBy`

Fields:

- `model_name` (hidden)
- `app_label` (hidden)
- `start_field` (select)
- `end_field` (select)

Extra hidden fields:

- `main_url`
- `preserve_qs`

### Dynamic choice loading

In `__init__`:

- resolves model/app from data/initial/instance
- loads allowed date fields via:
  - `TimelineSpanBy(...).get_model_date_fields(user=...)`
- falls back to `[("", "---------")]` when no fields.

### Validation

`clean()` validates selected start/end through model `clean()` using a temp instance and current user context.

---

## `ColumnSelectionForm`

Used in list-column selector workflows.

Field:

- `visible_fields` (`MultipleChoiceField` with hidden-input widget)

### Initialization behavior

Accepts runtime kwargs:

- `model`, `app_label`, `path_context`, `user`, `model_name`, `url_name`

Build process:

1. derive model field candidates (`verbose`, `name`)
2. if model instance has `columns`, use those; else use model fields
3. load persisted visibility row from `ListColumnVisibility`
4. merge in custom/removed fields not in base candidates
5. sort choices by label
6. when bound data is present, read `visible_fields` from a local `form_data` copy (`getattr(self, "data", None)`), keep only names in the current choice set, write the sanitized list back, then assign `self.data = form_data`

Step 6 supports both `QueryDict` (`.getlist` / `.setlist`) and plain dict payloads. Invalid or stale field names submitted before choices are rebuilt are dropped so validation does not fail on removed columns.

This keeps the selector robust when columns evolve over time.

---

## `SaveFilterListForm`

Captures metadata when saving current filter state as named list.

Fields:

- `list_name` (required text)
- `model_name` (hidden)
- `main_url` (hidden optional)
- `saved_list_id` (hidden optional)
- `make_public` (checkbox)

Validation:

- `clean()` ensures `list_name` is non-empty after trim.

Used by helper views that create/update saved filter list definitions.

---

## `PasswordInputWithEye` (widget)

Custom password widget that adds built-in show/hide eye button.

Features:

- default CSS classes for consistent styling
- wraps password input in relative container
- injects toggle button + inline JS function `togglePassword(...)`
- swaps eye icon between visible/hidden states.

Useful for forms requiring password visibility toggle without extra template code.

---

## `HorillaHistoryForm`

Simple date filter form for history screens.

Field:

- `filter_date` (`DateField`, HTML date input)

Method:

- `apply_filter(history_by_date)` where input is iterable of `(date, entries)`

Behavior:

- if form invalid or date missing: returns original sequence
- else returns only rows matching selected date.

Designed for history tab/list date narrowing.

---

## `RowFieldWidget` + `RowField`

Reusable pair for rendering multiple logical subfields in one row.

### `RowFieldWidget` (`MultiWidget`)

- template: `forms/widgets/row_field_widget.html`
- built from `field_configs` list
- supports `select` and `text` subwidgets
- injects `field_configs` into template context.

### `RowField` (`MultiValueField`)

- builds corresponding subfields from same config
- sets `is_row_field = True`
- `compress()` returns raw `data_list` (no custom merge logic)

Useful when UI needs grouped controls that still post as one logical field.

---

## `CustomFileInput` (widget)

Enhanced file input widget:

- template: `forms/widgets/custom_file_input.html`
- adds `selected_filename` to context
- extracts filename from `FieldFile` or string path

Used by attachment forms for better file display UX.

---

## `PhoneWidget` + `PhoneField`

Reusable pair that adds a country-dial-code Select2 selector alongside a phone number text input, storing the combined result in the underlying `CharField` as `+XX NNNNNN`.

**No migration required** — the model field type is unchanged.

### `_build_phone_country_codes()`

Module-level helper that builds the dial-code choices list at import time using the `phonenumbers` library (Google libphonenumber dataset):

- iterates `phonenumbers.SUPPORTED_REGIONS`
- deduplicates codes (e.g. +1 covers US, CA, and several Caribbean territories)
- sorts numerically by dial code
- falls back to `[("", "+")]` if `phonenumbers` is not installed

Result is stored in `PHONE_COUNTRY_CODES` and shared by both `PhoneWidget` and `PhoneField`.

**Dependency:** `pip install phonenumbers`

### `PhoneWidget` (`MultiWidget`)

Renders a flex-row container with:

1. A `<select>` using `js-example-basic-single headselect` class (initialized as Select2)
2. A plain `<input type="text">` for the number

The `render()` method also injects a per-field inline `<script>` that:

- initializes Select2 on page load (via `DOMContentLoaded`)
- re-initializes on HTMX swaps (via `htmx:afterSwap`)
- guards against double-init using `$(el).data('select2')`
- uses a unique function name per widget instance (safe for multi-phone forms)

Layout is a `flex` container with `gap-2`, with the code selector in a `25%` div and the number input in a `75%` div.

**`decompress(value)`** splits a stored string like `"+91 9876543210"` back into `["+91", "9876543210"]`:

- matches longest known dial code first
- falls back to splitting on first space
- handles values stored without a code prefix

### `PhoneField` (`MultiValueField`)

- wraps `ChoiceField` (dial code) + `CharField` (number)
- both sub-fields are `required=False`
- **`compress(data_list)`**: combines `["+91", "9876543210"]` → `"+91 9876543210"`, returns empty string if both are blank

### Usage

`PhoneField` is applied automatically by `HorillaFormMixin._apply_phone_fields()` — see `form_class_mixin.md` for the auto-detection behavior and subclass override options.

Manual usage when needed:

```python
from horilla.contrib.generics.forms import PhoneField

class MyForm(HorillaModelForm):
    work_phone = PhoneField(label="Work Phone", required=False)
```

---

## `HorillaAttachmentForm`

Model form for `HorillaAttachment`.

Fields:

- `title`
- `file`
- `description`

Widget setup:

- `title`: styled text input
- `file`: `CustomFileInput` (hidden input style)
- `description`: `SummernoteInplaceWidget` with custom toolbar/style configuration

### Edit-mode description handling

In `__init__`:

- if editing and description exists, escapes `&lt;` and `&gt;` to double-escaped variants before setting initial.

Purpose:

- avoid unintended HTML interpretation/rendering issues in rich text editor load path.

---

## Thread-local request usage

Some forms (`KanbanGroupByForm`, `TimelineSpanByForm`) use:

- `horilla_utils.middlewares._thread_local`

to access current request/user in form init/validation for permission-aware choice generation and model clean behavior.

---

## Integration points in views

Common consumers:

- `views/helpers/kanban_groupby.py` -> `KanbanGroupByForm`
- `views/helpers/timeline_settings.py` -> `TimelineSpanByForm`
- `views/helpers/list_column.py` -> `ColumnSelectionForm`
- `views/helpers/filter_list.py` -> `SaveFilterListForm`
- history views/tabs -> `HorillaHistoryForm`
- attachment views -> `HorillaAttachmentForm`

---

## Caveats and notes

- Several forms depend on runtime kwargs/context; creating them without expected kwargs may produce empty choices.
- Inline JS in `PasswordInputWithEye.render()` can duplicate function definition if widget rendered multiple times on one page.
- `ColumnSelectionForm` mutates bound `self.data` to sanitize invalid `visible_fields` after choices are built; the read/copy/write path uses a local `form_data` variable. Useful for debugging posted payloads when columns change between requests.
- `HorillaAttachmentForm` description escaping is specific and may require revisiting if editor serialization strategy changes.
- `PhoneWidget` injects a `<script>` tag per field instance. Forms with multiple phone fields (e.g. Contact with `phone`, `secondary_phone`, `assistant_phone`) each get their own script with a unique function name — no collision.
- `PHONE_COUNTRY_CODES` is built once at module import time. If `phonenumbers` is not installed the list degrades to a single placeholder entry `("", "+")`.
- Stored phone values created before this widget was introduced (plain numbers without a country code) are handled gracefully — `decompress()` places the raw value in the number sub-field and leaves the code selector blank.

---

## Summary

`generics.py` is the form utility backbone for many Horilla generic view features. It combines configuration forms, selection/filter helpers, reusable widgets, and attachment/history utilities with runtime-aware initialization and validation tailored to dynamic HTMX-driven interfaces.
