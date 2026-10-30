# Detail field helpers (`horilla_generics/views/helpers/detail_field.py`)

## Purpose

This module handles **user-specific detail view field visibility**:

- open field-selector modal,
- compute defaults for header/details sections,
- save selected field order,
- reset to defaults.

It integrates with:

- `HorillaDetailView` registry,
- `HorillaDetailSectionView` defaults,
- `DetailFieldVisibility` persistence model,
- field-level permission filtering (`filter_hidden_fields`).

---

## Core data model used

`DetailFieldVisibility` stores per-user configuration by:

- `user`
- `app_label`
- `model_name`
- `url_name`

with JSON-like fields:

- `header_fields` -> `[[verbose_name, field_name], ...]`
- `details_fields` -> `[[verbose_name, field_name], ...]`

---

## Utility functions

## `_ensure_json_serializable(fields_list)`

Normalizes all values to plain `str`, avoiding lazy translation proxy objects in JSON serialization.

## `get_detail_field_defaults_no_request(model)`

Signal-safe wrapper to compute defaults when no request is available.

## `_get_detail_field_defaults(model, request)`

Main default resolver:

1. checks if model has registered `HorillaDetailView` subclass,
2. computes effective excluded fields:
   - base excludes
   - subclass `excluded_fields`
   - auto-exclude `pipeline_field`
3. builds default header from detail view `body`,
4. builds default details from:
   - section view `get_default_body()` if `details_section_url_name` available,
   - else model field fallback.

If no registered detail view, falls back to model fields excluding `HorillaDetailView.base_excluded_fields`.

---

## View: `DetailFieldSelectorView`

```python
class DetailFieldSelectorView(LoginRequiredMixin, View):
```

Template: `add_field_to_detail.html`

Route: `horilla_generics:detail_field_selector`

### Request expectations (`GET`)

Required params:

- `app_label`
- `model_name`
- `url_name`

Optional params:

- `details_section_url` (explicit detail-section URL name override)
- `pk` (passed by caller; not directly required for selector logic)

### Processing flow

1. validate params and resolve model via `apps.get_model`.
2. compute base excludes for selector.
3. inspect registered detail view class for:
   - `excluded_fields`
   - `pipeline_field` (auto-excluded)
   - `details_section_url_name` and section-view excludes/default body
   - optional `get_available_fields_for_selector(request, model)` hook (advanced override)
4. build full candidate model field list.
5. filter candidates by `filter_hidden_fields` (user permissions).
6. get defaults from `_get_detail_field_defaults(...)`.
7. load existing `DetailFieldVisibility` record (if any).
8. choose effective current values:
   - saved fields if present
   - otherwise defaults
9. resolve verbose names in current request language.
10. remove excluded and hidden fields again for safety.
11. compute available lists:
   - `header_available`
   - `details_available`
12. detect `has_custom_visibility` by comparing saved names vs default names.
13. render modal template with all lists + hidden inputs.

### Response behavior on invalid input

Returns inline HTML error snippets (status 200) for missing/invalid model parameters, so modal UX can still render message.

---

## View: `SaveDetailFieldsView`

```python
class SaveDetailFieldsView(LoginRequiredMixin, View):
```

Route: `horilla_generics:save_detail_fields`

Method: `POST`

### Expected POST

- `app_label`
- `model_name`
- `url_name`
- repeated `header_fields` values (ordered)
- repeated `details_fields` values (ordered)

### Flow

1. validate and resolve model.
2. normalize `model_name` (strip dotted model path suffix).
3. filter submitted names through `filter_hidden_fields`.
4. map field names to verbose labels.
5. compute defaults via `_get_detail_field_defaults(...)`.
6. `get_or_create` visibility row with defaults.
7. store submitted lists after `_ensure_json_serializable`.
8. save row.
9. return `ScriptResponse(extra="closeContentModal();", reload=True)`.

---

## View: `ResetDetailFieldsView`

```python
class ResetDetailFieldsView(LoginRequiredMixin, View):
```

Route: `horilla_generics:reset_detail_fields`

Method: `POST`

### Expected POST

- `app_label`
- `model_name`
- `url_name`

### Flow

Deletes matching `DetailFieldVisibility` rows for user+model+url and returns the same close-and-reload `ScriptResponse`.

Effect: next selector/open/render uses computed defaults.

---

## View: `SplitColumnSelectorView`

```python
class SplitColumnSelectorView(LoginRequiredMixin, View):
```

Template: `add_column_to_split.html` · Route: `generics:split_column_selector` · HTMX-only

Per-user selection and order of the fields shown in the **split view's detail
panel**. Stored in the same `DetailFieldVisibility` table (only
`details_fields` is used) under the fixed `url_name` `SPLIT_VISIBILITY_URL_NAME`
(from `views/details.py`).

- `GET` (`app_label`, `model_name`): lists selectable model fields (editable,
  minus base/`excluded_fields`/`split_excluded_fields`/`pipeline_field` of the
  registered detail view, minus fields hidden by `filter_hidden_fields`, plus
  custom-field definitions when `field_management` is installed). Shows the saved
  list, or all fields when nothing is saved. Bad model returns an inline error.
- `POST`: saves the posted `visible_fields` (order kept, unknown names dropped)
  and returns `ScriptResponse(extra="closeModal();", reload=True)`. With `reset`
  it deletes the row and closes/reloads. Bad model returns `400`.

---

## Integration with detail page

`HorillaDetailView.get_context_data` builds:

```text
change_fields_url = /generics/detail-field-selector/?app_label=...&model_name=...&url_name=...&pk=...
```

and optionally appends `details_section_url` inferred from tab config.

This URL opens selector modal and controls both:

- top header field set
- details section field set

for the specific detail URL context (`url_name` scoped visibility).

---

## Template workflow (`add_field_to_detail.html`)

The selector modal:

- posts to `save_detail_fields`,
- keeps hidden ordered inputs for selected header/details fields,
- supports moving fields between available/visible columns and reordering,
- has reset button posting to `reset_detail_fields`.

Response scripts close modal and trigger page content reload.

---

## Example 1: open selector from detail view

Detail context provides:

```text
.../generics/detail-field-selector/?app_label=leads&model_name=lead&url_name=leads_detail&pk=42
```

HTMX button pattern:

```html
<button
  hx-get="{{ change_fields_url }}"
  hx-target="#contentModalBox"
  hx-swap="innerHTML"
  onclick="openContentModal()">
  Change Fields
</button>
```

---

## Example 2: save selected field order

Selector form submits:

```text
app_label=leads
model_name=lead
url_name=leads_detail
header_fields=title
header_fields=lead_owner
details_fields=first_name
details_fields=last_name
details_fields=email
```

Server stores ordered pairs in `DetailFieldVisibility` for current user and reloads detail content.

---

## Example 3: reset to defaults

POST:

```text
app_label=leads
model_name=lead
url_name=leads_detail
```

Result:

- custom row deleted,
- detail fields revert to computed defaults from detail/section view settings and model excludes.

---

## Advanced customization hook

A detail view class can implement:

```python
@classmethod
def get_available_fields_for_selector(request, model):
    return default_header, default_details, allowed_field_names
```

If provided, selector respects `allowed_field_names` to constrain what users can choose.

---

## Notes

- `pipeline_field` is auto-excluded from both header and details selector to prevent duplication with pipeline UI.
- Visibility is scoped by `url_name`, so the same model can have different field layouts on different detail routes.
- Hidden field permissions are enforced in both selector population and save stage.

---

## Summary

`detail_field.py` is the field-layout customization layer for detail pages: it computes smart defaults from detail view classes, persists per-user field order by URL context, and exposes HTMX endpoints to save/reset layouts safely under permission constraints.
