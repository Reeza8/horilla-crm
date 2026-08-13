# Inline edit helpers (`horilla/contrib/generics/views/helpers/edit_field.py`)

## Purpose

This module provides HTMX endpoints for **single-field inline editing** in detail views.

It supports the three-step cycle:

1. open editable widget for one field (`EditFieldView`),
2. submit and save (`UpdateFieldView`),
3. cancel edit and restore display mode (`CancelEditView`).

Used directly by `details_tab.html` via `generics:edit_field`, `cancel_edit`, `update_field`.

All three inherit [`horilla.views.generic.View`](../../../../views/generic.md), so [`_inherit_view`](../../../../extension/view/inherit.md) extensions apply via `as_view()` / `resolve_view_class()`.

---

## Views overview

## 1) `EditFieldView`

```python
class EditFieldView(LoginRequiredMixin, View):
```

- HTMX-only (`@htmx_required`)
- template: `partials/edit_field.html`
- method: `GET`

Route params: `pk`, `field_name`, `app_label`, `model_name`.

Optional query: `pipeline_field` (passed through context).

### What it does

1. resolves model dynamically with `apps.get_model`.
2. fetches object by `pk`.
3. resolves target field from model metadata.
4. computes `field_info` via `get_field_info(...)`.
5. renders edit-widget fragment.

On failure: flashes message and returns reload script.

---

## 2) `UpdateFieldView`

```python
class UpdateFieldView(LoginRequiredMixin, View):
```

- HTMX-only
- template: `partials/field_display.html`
- method: `POST`

### What it does

1. resolves model/object/field.
2. parses submitted value(s) by field type (date/datetime via overridable parse hooks).
3. saves object or m2m relation update.
4. reuses `get_edit_field_view().get_field_info(...)` to build fresh display context.
5. returns display fragment (non-edit mode).

If parsing/update fails: re-renders the edit partial with an inline error.

### Parse hooks (calendar extensions)

```python
def parse_datetime_field_value(self, value, user=None): ...
def parse_date_field_value(self, value, user=None): ...
```

Gregorian defaults use `datetime.fromisoformat`. Override via `_inherit_view` on `UpdateFieldView`.

---

## 3) `CancelEditView`

Same pattern as update display path: `get_edit_field_view().get_field_info(...)` without saving.

---

## `get_edit_field_view()`

```python
from horilla.contrib.generics.views.helpers.edit_field import get_edit_field_view

edit_view = get_edit_field_view()  # resolve_view_class(EditFieldView)()
```

Use this (not bare `EditFieldView()`) from update/cancel/duplicates so `_inherit_view` mixins apply.

---

## Field metadata engine (`get_field_info`)

Common keys: `name`, `verbose_name`, `field_type`, `value`, `display_value`, `choices`, `use_select2`, `input_attrs`.

### Field-type mapping (highlights)

- M2M / FK / choices / boolean / phone / email / url / number as before.
- `DateTimeField` -> `datetime-local`; display via `format_datetime_value(..., convert_timezone=False)` (composed `DateTimeFormatter`).
- `DateField` -> `date`; same formatter for display.
- Extensions may set `input_attrs` (e.g. Jalali `data-jdp`) and change `field_type` to `text`.

`partials/edit_field.html` loops `field_info.input_attrs` onto the generic `<input>`.

---

## Date/time update rules

- `DateTimeField`: `parse_datetime_field_value`, then user-TZ → default TZ for storage.
- `DateField`: `parse_date_field_value`.

---

## Related

- [`_inherit_view`](../../../../extension/view/inherit.md)
- [`DateTimeFormatter`](../../formatting/datetime.md) / [`_inherit_formatter`](../../../../extension/formatting/inherit.md)
- [`horilla.views.generic.View`](../../../../views/generic.md)

---

## Summary

Inline-edit backend for detail tabs: dynamic widgets, extension-aware parse/display, timezone-aware datetimes, HTMX fragment swap for edit-save-cancel.
