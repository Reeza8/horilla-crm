# Saved filter helpers (`horilla_generics/views/helpers/filter_list.py`)

## Purpose

This module manages reusable list filters and pinned view modes.

It provides HTMX endpoints for:

1. creating/updating saved filter lists,
2. pinning/unpinning a selected `view_type`,
3. deleting a saved filter list and restoring a valid active view mode.

These helpers work with list/card/navbar UIs and `HorillaListView` view-type logic.

---

## Main entities used

- `SaveFilterListForm` (input validation for list name/model/main URL/public flag)
- `request.user.saved_filter_lists` relation (user-owned saved filter lists)
- `PinnedView` model (one pinned `view_type` per user+model)

---

## 1) `SaveFilterListView`

```python
class SaveFilterListView(LoginRequiredMixin, FormView):
```

- HTMX-only (`@htmx_required`)
- template: `save_filter_form.html`
- form: `SaveFilterListForm`
- route: `horilla_generics:save_filter_list`

### GET usage

Loads modal/form for:

- new save (`saved_list_id` absent), or
- edit existing saved list (`saved_list_id` present).

### `get_initial` behavior

If `saved_list_id` resolves to user-owned list:

- prefill:
  - `saved_list_id`
  - `list_name`
  - `model_name`
  - `main_url`
  - `make_public`

If ID invalid:

- best-effort keeps numeric id in initial (for later validation path).

Also fills missing `model_name`/`main_url` from request params.

### `get_context_data` behavior

When editing:

- `query_params` from stored `saved_list.filter_params`
- `is_edit=True`

When creating:

- `query_params` from current request keys:
  - `field`, `operator`, `value`, `start_value`, `end_value`, `logic`, `search`
- `is_edit=False`

Always sets `main_url` in context.

### `form_valid` behavior

Builds `filter_params` from POST lists:

- `field`, `operator`, `value`, `start_value`, `end_value`, `logic`
- plus `search` from POST (or GET fallback)

#### Edit path (`saved_list_id` present)

1. ensure list belongs to current user,
2. update name/filter/public flag,
3. redirect to `main_url` with:
   - `view_type=saved_list_<id>`
   - existing GET params except `view_type` and `search`.

#### Create path

1. reject when no filter criteria present (`At least one filter is required.`),
2. `update_or_create` by `(name, model_name)` under user relation,
3. redirect to `main_url` with `view_type=saved_list_<id>`.

#### Validation/error handling

- duplicate name/model integrity -> field error on `list_name`
- invalid edit target -> non-field error + form re-render.

---

## 2) `PinView`

```python
class PinView(LoginRequiredMixin, View):
```

- HTMX-only
- method: `POST`
- route: `horilla_generics:pin_view`

Inputs:

- `view_type`
- `model_name`
- optional `unpin` (POST or GET)

### Behavior

#### Unpin

- deletes `PinnedView` for user+model
- returns rendered `navbar.html` with:
  - `all_view_types=True`
  - current `view_type`

#### Pin/update

- `update_or_create` pinned row (`user`, `model_name`) -> set `view_type`
- returns refreshed `navbar.html` context with pinned marker.

Errors -> 400 for missing inputs, 500 for unexpected exception.

---

## 3) `DeleteSavedListView`

```python
class DeleteSavedListView(LoginRequiredMixin, View):
```

- HTMX-only
- method: `POST`
- route: `horilla_generics:delete_saved_list`

Inputs:

- `saved_list_id`
- `main_url`
- `model_name`

### Flow

1. validate id presence; if missing -> error message + redirect.
2. ensure saved list belongs to current user.
3. if this saved list is currently pinned, delete matching `PinnedView`.
4. delete saved list row.
5. set success/failure flash message.
6. compute fallback `view_type`:
   - pinned view’s type if exists,
   - else `"all"`.
7. redirect to `main_url` with updated query params and `view_type`.
8. sets `HX-Push-Url: true` so browser URL updates in HTMX flow.

---

## How UI integrates

Templates calling these endpoints include:

- `filterpanel.html` -> open save form modal (`save_filter_list`)
- `save_filter_form.html` -> submit save/update
- `navbar.html` -> pin/unpin buttons (`pin_view`)
- `list_view.html` / `card_view.html` -> edit/delete saved list actions

This creates the full saved-list lifecycle from list toolbar controls.

---

## Example 1: Save current filters as reusable list

1. User applies filters in list screen.
2. Clicks "Save filter" -> opens `save_filter_form.html` via HTMX GET.
3. Submits list name + optional public flag.
4. `SaveFilterListView` stores params and redirects to:

```text
<main_url>?view_type=saved_list_<id>&...
```

Now list runs in saved-list mode and can be pinned.

---

## Example 2: Edit an existing saved list

Open form with:

```text
/generics/save-filter-list/?saved_list_id=12&main_url=...&model_name=Lead
```

View loads existing saved params, allows renaming and changing filter criteria, then redirects back with same `view_type=saved_list_12`.

---

## Example 3: Pin and unpin view type

Pin request:

```text
POST /generics/pin-views/
view_type=saved_list_12
model_name=Lead
```

Unpin request:

```text
POST /generics/pin-views/
view_type=saved_list_12
model_name=Lead
unpin=true
```

Both return updated navbar fragment.

---

## Example 4: Delete saved list safely

Delete request:

```text
POST /generics/delete-saved-list/
saved_list_id=12
main_url=/leads/leads-view/
model_name=Lead
```

If list was pinned, pin is removed too.
User is redirected to main URL with a valid replacement `view_type` (`pinned` or `all`).

---

## Notes

- Saved-list edit/delete operations are scoped to current user’s `saved_filter_lists`.
- `view_type` naming convention (`saved_list_<id>`) is tightly coupled with `HorillaListView.get_queryset`.
- Redirect URLs preserve most existing GET state while preventing stale `view_type`/`search` conflicts.

---

## Summary

`filter_list.py` is the persistence/control layer for reusable filters: it saves list criteria, manages pinned defaults, and ensures the UI always returns to a valid `view_type` after edits/deletions in HTMX-first list workflows.
