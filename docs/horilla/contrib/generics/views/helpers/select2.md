# Select2 data helper (`horilla_generics/views/helpers/select2.py`)

## Purpose

`HorillaSelect2DataView` is the generic AJAX backend for Select2 dropdowns.

It provides:

- remote search (`q`) on text fields,
- pagination (`page`, 10 per page),
- preloading by IDs (`ids`),
- optional dependency filtering (`dependency_*`),
- queryset scoping from filter classes/forms (including owner-aware querysets),
- a form class method `get_select2_queryset(request, model, field_name)` that replaces the field queryset when it returns a queryset (Activity's related-object picker uses this),
- company scoping when model has `company` field,
- safe import-path checks for request-driven class resolution.

Route:

- `horilla_generics:model_select2`
- URL: `/<app_label>/<model_name>/select2/`

---

## Security helper: `_is_allowed_import_module_path`

Because this view can import classes from request params (`filter_class`, `form_class`), it whitelists import paths:

- allowed only if module equals an installed app path or submodule of one,
- rejects traversal/dangerous patterns (`..`, leading dot).

This prevents arbitrary module import from untrusted query strings.

---

## Main view: `HorillaSelect2DataView`

```python
class HorillaSelect2DataView(LoginRequiredMixin, View):
```

### Request guard

Requires AJAX header:

- `x-requested-with=XMLHttpRequest`

If not present -> renders `405.html`.

---

## Input parameters

Core params:

- `q` -> search term
- `page` -> page number (default 1)
- `ids` -> comma-separated IDs to return exact selected options
- `field_name` -> target form/filter field (used for queryset extraction)

Dependency params:

- `dependency_value`
- `dependency_model` (`app_label.ModelName`)
- `dependency_field` (FK field on target model)

Class resolution params:

- `filter_class` (`module.Class`) optional
- `form_class` (`module.Class` or DynamicForm marker) optional
- `parent_model` (`app_label.ModelName`) for DynamicForm resolution
- `object_id` for edit-mode form instance resolution

---

## Queryset resolution order

The view picks queryset in this order:

1. **FilterSet field queryset** (preferred)
2. **Form field queryset**
3. fallback `model.objects.all()`

### 1) FilterSet-based queryset (`_get_filter_class_from_request`)

Two discovery modes:

- explicit `filter_class` import from request (whitelisted),
- auto-discover `filters` module for app and find `django_filters.FilterSet` whose `Meta.model` matches target model.

If `field_name` exists in filterset and filter field has queryset, that queryset is used.

### 2) Form-based queryset (`_get_form_class_from_request`)

Handles:

- normal importable forms via `form_class`,
- dynamic form case (`DynamicForm`) via `get_dynamic_form_for_model(parent_model)`.

If `object_id` is supplied, tries to load form instance so owner-aware form mixins use change/change_own permissions in edit mode.

If `field_name` exists and has queryset, it overrides fallback queryset.

---

## Additional queryset filters

After initial queryset selection:

### Company filter

If `request.active_company` exists and target model has `company` field:

- applies `queryset.filter(company=active_company)`.

### Dependency filter

If `dependency_value`, `dependency_model`, `dependency_field` are present:

1. resolves dependency model from `dependency_model`,
2. ensures `dependency_field` on target model points to that model,
3. filters by `dependency_field__pk=dependency_value`,
4. on mismatch/lookup failure -> `queryset.none()`.

---

## `ids` fast path

If `ids` param provided:

- parses integer IDs,
- filters queryset by `pk__in`,
- returns all matched options immediately (no pagination/search path),
- `pagination.more = false`.

Used for pre-populating selected values in Select2 widgets.

---

## Search and pagination behavior

When no `ids`:

- if `q` exists:
  - discovers all `CharField`/`TextField` fields (except id),
  - OR-filters `icontains` across those fields.
- if no search term:
  - orders by `pk`.

Then paginates:

- `per_page = 10`,
- response includes:
  - `results: [{id, text}, ...]`
  - `pagination: {more: <bool>}`.

---

## JSON response contract

Standard shape:

```json
{
  "results": [
    {"id": 1, "text": "Label 1"},
    {"id": 2, "text": "Label 2"}
  ],
  "pagination": {"more": true}
}
```

`text` comes from `str(obj)`; fallback string uses model name and pk.

---

## Examples

## Example 1: basic search

```text
GET /generics/leads/Lead/select2/?q=acme&page=1
x-requested-with: XMLHttpRequest
```

Returns first 10 matching leads from text fields.

---

## Example 2: preload selected IDs

```text
GET /generics/leads/Lead/select2/?ids=3,8,21
```

Returns exactly those options for initial Select2 selected values.

---

## Example 3: dependent dropdown

```text
GET /generics/opportunities/Opportunity/select2/
  ?q=
  &dependency_value=5
  &dependency_model=accounts.Account
  &dependency_field=account
```

Returns opportunities linked to account id 5.

---

## Example 4: use filter class queryset

```text
GET /generics/leads/Lead/select2/
  ?field_name=lead_owner
  &filter_class=horilla_crm.leads.filters.LeadFilter
```

If filter defines queryset constraints for `lead_owner`, those are respected.

---

## Example 5: dynamic form resolution

```text
GET /generics/leads/Lead/select2/
  ?field_name=lead_status
  &form_class=...DynamicForm
  &parent_model=leads.Lead
  &object_id=42
```

Resolves generated form class and uses its field queryset in edit context.

---

## Integration points in project

Used by:

- form widgets with class `select2-pagination`,
- single/multi-step generic forms,
- condition field forms,
- inline edit helpers (`edit_field.py`) for FK/M2M dropdowns.

Front-end initialization is in `static/assets/js/global.js`.

---

## Notes

- No text-searchable fields -> returns empty queryset when `q` is present.
- Dependency mismatch intentionally returns empty result set (safer than leaking unrelated rows).
- Path whitelist for imports is critical; keep it strict when extending request-driven class resolution.

---

## Summary

`select2.py` is the generic, secure Select2 data service for Horilla forms: it combines model lookup, owner-aware queryset sourcing from filter/form classes, optional dependency/company constraints, and efficient search/pagination JSON output.
