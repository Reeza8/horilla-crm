# List column helpers (`horilla_generics/views/helpers/list_column.py`)

## Purpose

This module manages **per-user list column visibility and ordering**.

It provides:

1. utility to resolve default columns from the view class by URL name,
2. modal form view to select visible columns,
3. endpoint to save column selection,
4. endpoint to reset columns to defaults.

Persistence is handled with `ListColumnVisibility` scoped by user/model/context/url.

---

## Data model and scope

`ListColumnVisibility` entries are keyed by:

- `user`
- `app_label`
- `model_name`
- `context` (derived from referrer path)
- `url_name`

Stored fields used here:

- `visible_fields` (ordered `[[verbose, field], ...]`)
- `removed_custom_fields` (preserves removed non-model/custom fields)

This allows the same model to have different visible columns on different pages/routes.

---

## Utility: `get_default_columns_from_view(...)`

```python
get_default_columns_from_view(url_name, app_label, model_name, request)
```

### What it does

1. resolves URL pattern by `url_name` (supports `app:name` and bare names),
2. extracts view class from callback,
3. verifies it is a `HorillaListView` subclass,
4. reads class `columns`,
5. returns ordered field names (tuple/list second item or raw string entries).

Returns `None` when URL/view cannot be resolved.

### Why used

Used to compare current selected columns against view defaults so UI can detect `has_custom_visibility` (including custom order changes).

---

## View: `ListColumnSelectFormView`

```python
class ListColumnSelectFormView(LoginRequiredMixin, FormView):
```

- HTMX-only (`@htmx_required`)
- template: `add_column_to_list.html`
- form: `ColumnSelectionForm`
- route: `horilla_generics:column_selector`

### `get_form_kwargs`

Reads:

- `app_label`
- `model_name` (normalizes dotted names)
- `url_name`
- referrer-derived `path_context`
- current user

Passes these into `ColumnSelectionForm`, which also sanitizes any bound `visible_fields` POST data against the rebuilt choice list before the modal is rendered.

### `get_context_data` (main selector builder)

Builds two lists:

- `visible_fields`
- `available_fields`

Flow highlights:

1. resolve model, collect model fields (`instance.columns` if present, else model fields).
2. map choice fields to `get_<name>_display`.
3. filter hidden fields via `filter_hidden_fields`.
4. load `ListColumnVisibility` row for user/model/context/url.
5. filter stored `visible_fields` and `removed_custom_fields` by current permissions.
6. store current visible field names in session key:
   - `visible_fields_<app>_<model>_<context>_<url_name>`
7. prevent duplicate appearance by treating raw and display variants (`field` + `get_field_display`) as equivalent.
8. handle related-field parent hiding for `__` paths.
9. apply explicit `exclude` query param and sensitive-field exclusions (`id`, `additional_info`) for available list.
10. compute `has_custom_visibility` by comparing current set/order against view defaults from `get_default_columns_from_view`.

Context also includes `app_label`, `model_name`, `url_name`, `exclude_fields`, and any `form_error`.

---

## Saving: `form_valid`

Triggered by POST to `column_selector`.

### Input

- `app_label`
- `model_name`
- `url_name`
- repeated `visible_fields` (ordered)

### Processing

1. validate model identifiers.
2. normalize `model_name`.
3. filter submitted field names through `filter_hidden_fields`.
4. rebuild all/verbose maps from model columns.
5. include prior custom fields from existing visibility row.
6. build final ordered `visible_fields` payload as `[[verbose, field], ...]`.
7. maintain `removed_custom_fields`:
   - add removed non-model custom fields,
   - remove entries that user added back.
8. update session key with plain visible field names.
9. delete old visibility row and create new one (same key scope).
10. clear cache key:
   - `visible_columns_<user>_<app>_<model>_<context>_<url_name>`
11. return script response:
   - click `#reloadButton`
   - close modal.

### Error responses

- missing app/model -> JSON error payload
- invalid model -> JSON error payload

---

## Reset: `ResetColumnToDefaultView`

```python
class ResetColumnToDefaultView(LoginRequiredMixin, View):
```

- HTMX-only
- route: `horilla_generics:reset_columns_to_default`
- method: `POST`

### Behavior

1. validates `app_label` + `model_name` (+ optional `url_name`).
2. computes same `path_context` from referrer.
3. deletes matching `ListColumnVisibility` row.
4. removes matching session key.
5. clears cache key.
6. returns reload + close modal script.

On exception: returns 500 with inline error HTML.

---

## Context path scoping (`path_context`)

`path_context` is derived from `HTTP_REFERER` path:

- strips leading/trailing `/`
- replaces `/` with `_`
- removes trailing numeric suffix (`_\d+`)

This prevents collisions where the same model appears in different screens (or object-specific URLs).

---

## Interaction with list rendering

`HorillaListView`/mixins read visibility data from:

- `ListColumnVisibility`,
- session/cache keys created by this helper.

So after save/reset, triggering `#reloadButton` causes list view to re-render using updated column visibility/order.

---

## Example 1: Open column selector modal

```html
<button
  hx-get="{% url 'horilla_generics:column_selector' %}?app_label=leads&model_name=Lead&url_name=leads_list"
  hx-target="#modalBox"
  hx-swap="innerHTML"
  onclick="openModal()">
  Add Column to List
</button>
```

---

## Example 2: Save selected visible columns

POST payload shape (core `User` list example):

```text
app_label=core
model_name=User
url_name=user_list_view
visible_fields=get_avatar_with_name
visible_fields=email
visible_fields=role
visible_fields=get_role_display
```

For choice fields, the column picker may store the raw field name (e.g. `role`) while `all_fields` uses `get_<field>_display`; both are treated as visible so the field does not appear in both panels.

Result:

- new `ListColumnVisibility` row persisted for current context,
- list reloads with this order.

---

## Example 3: Reset to view defaults

POST:

```text
app_label=leads
model_name=Lead
url_name=leads_list
```

Result:

- custom visibility row deleted,
- session/cache invalidated,
- list reloads with default columns from view class (or fallback model columns).

---

## Example 4: Exclude specific fields from selector

Caller can pass:

```text
.../column-selector/?app_label=leads&model_name=Lead&url_name=leads_list&exclude=message_id,is_convert
```

Those fields remain unavailable even if visible by permissions.

---

## Notes

- Hidden field permissions are enforced in both visible and available panels.
- Choice display methods are handled specially to avoid duplicates (`field` vs `get_field_display`).
- Custom/non-model columns are preserved through `removed_custom_fields` so users can remove/re-add them without losing labels.

---

## Summary

`list_column.py` is the column-visibility control layer for list UIs: it computes defaults from real view classes, tracks per-user context-specific selections, and safely persists/resets column order while respecting field permissions and cache/session consistency.
