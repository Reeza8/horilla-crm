# Kanban & GroupBy helpers (`horilla_generics/views/helpers/kanban_groupby.py`)

## Purpose

This helper module provides three HTMX endpoints:

1. **settings modal** for choosing group-by field (`HorillaKanbanGroupByView`),
2. **Kanban load-more** proxy (`KanbanLoadMoreView`),
3. **GroupBy load-more** proxy (`GroupByLoadMoreView`).

It connects navbar actions and templates to the actual `HorillaKanbanView` / `HorillaGroupByView` subclass instances registered per model.

---

## 1) `HorillaKanbanGroupByView`

```python
class HorillaKanbanGroupByView(FormView):
```

- HTMX-only (`@htmx_required`)
- template: `kanban_settings_form.html`
- form: `KanbanGroupByForm`
- route: `horilla_generics:create_kanban_group`

### What it configures

Per-user group-by preference in `KanbanGroupBy` for a model and `view_type`:

- `view_type="kanban"` for kanban columns
- `view_type="group_by"` for grouped table sections

### `get_form_kwargs` behavior

Reads request params:

- `model`
- `app_label`
- `view_type`
- optional `exclude_fields` CSV
- optional `include_fields` CSV

Builds form `instance=KanbanGroupBy(...)` so save targets current user+model+view type.

### `get_context_data`

Adds:

- `group_by_view_type`
- `settings_title`:
  - `"Group By Settings"` when `view_type=group_by`
  - `"Kanban Settings"` otherwise

### `form_valid`

1. sets `form.instance.user` server-side
2. sets `form.instance.view_type`
3. saves preference
4. returns script:
   - group_by -> `closeModal(); $('#groupByBtn').click();`
   - kanban -> `closeModal(); $('#kanbanBtn').click();`

This refreshes the correct layout after preference change.

---

## 2) `KanbanLoadMoreView`

```python
class KanbanLoadMoreView(LoginRequiredMixin, View):
```

- HTMX-only
- route: `horilla_generics:kanban_load_more`
- URL pattern: `kanban-load-more/<app_label>/<model_name>/`

### Flow

1. resolves model with `apps.get_model(app_label, model_name)`.
2. gets model-specific kanban view class from `HorillaKanbanView._view_registry`.
3. instantiates that view class, injects:
   - `request`
   - `model`
   - `kwargs`
4. delegates to `view.load_more_items(request)`.

If class not registered or errors occur, returns reload script with flash message.

---

## 3) `GroupByLoadMoreView`

```python
class GroupByLoadMoreView(LoginRequiredMixin, View):
```

- route: `horilla_generics:group_by_load_more`
- URL pattern: `group-by-load-more/<app_label>/<model_name>/`

Same pattern as kanban loader, but uses:

- `HorillaGroupByView._view_registry`
- `view.load_more_items(request)` from groupby view.

---

## Grouping by a field that isn't a model column

`KanbanGroupBy.get_model_groupby_fields()` lists only model fields and `KanbanGroupBy.save()` validates the name against them, so a field that isn't a model column can't go through the settings form. An `_inherit_view` extension on `HorillaKanbanGroupByView` adds the choice in `get_form` and stores it directly in `post` (delete the user's existing row, create the new one). The views that read the preference then resolve it through `get_group_field` — see [list.md](../list.md#extension-hooks-for-fields-that-arent-model-columns).

---

## Why proxy helper views exist

Kanban/GroupBy subclasses live in app modules (`leads`, `contacts`, etc.), but load-more routes are centralized under `horilla_generics`.

These helper views act as dynamic dispatchers:

- identify model from URL,
- find proper registered subclass,
- call subclass logic with current request filters/search params.

This avoids duplicating load-more URLs for every app.

---

## Integration points

### Navbar actions

`horilla_generics/views/navbar.py` builds settings actions like:

- `...create_kanban_group?...&view_type=kanban`
- `...create_kanban_group?...&view_type=group_by`

### Settings template

`kanban_settings_form.html` posts to `create_kanban_group` and shows a `field_name` dropdown from form choices.

### Load-more templates

- kanban cards: `partials/kanban_items.html`
  - calls `kanban_load_more` with `column_key`, `page`, and current query params
- group-by rows: `partials/list_view_rows.html` / `partials/group_by_load_more_rows.html`
  - calls `group_by_load_more` with `group_key`, `page`.

---

## Example 1: open Kanban settings modal

```html
<button
  hx-get="{% url 'horilla_generics:create_kanban_group' %}?model=Lead&app_label=leads&exclude_fields=lead_owner&view_type=kanban"
  hx-target="#modalBox"
  hx-swap="innerHTML"
  onclick="openModal()">
  Kanban Settings
</button>
```

On save, modal closes and triggers `#kanbanBtn` click to refresh board with new group field.

---

## Example 2: open GroupBy settings modal

```html
<button
  hx-get="{% url 'horilla_generics:create_kanban_group' %}?model=Lead&app_label=leads&exclude_fields=lead_owner&view_type=group_by"
  hx-target="#modalBox"
  hx-swap="innerHTML"
  onclick="openModal()">
  Group By Settings
</button>
```

On save, triggers `#groupByBtn` refresh.

---

## Example 3: Kanban load more request

From card template:

```text
/generics/kanban-load-more/leads/Lead/?column_key=3&page=2&search=abc&view_type=all
```

Helper resolves `Lead` -> `LeadKanbanView` via registry and returns next card fragment.

---

## Example 4: GroupBy load more request

```text
/generics/group-by-load-more/leads/Lead/?group_key=5&page=3&search=abc
```

Helper resolves `Lead` -> `LeadGroupByView` and returns additional table rows.

---

## Error behavior

- model lookup failure / missing view class / runtime error:
  - flashes `messages.error(...)`
  - returns script response that triggers reload button.

This keeps the UI from staying in a broken partial state.

---

## Summary

`kanban_groupby.py` is the dispatch-and-settings bridge between generic routes and model-specific kanban/group-by views. It centralizes group-by preference saving and incremental load-more plumbing while preserving each app’s subclass behavior through registry-based delegation.
