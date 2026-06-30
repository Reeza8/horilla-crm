# Delete toolkit mixins (`horilla_generics/views/toolkit/delete_mixins.py`)

## Purpose

This module provides the dependency-analysis and dependency-resolution primitives used by `HorillaSingleDeleteView`.

It is split into:

- reusable helper functions (model exclusion, FK metadata, context builder),
- `DeleteDependencyMixin` (detect dependencies + paginate related rows),
- `DeleteReassignMixin` (resolve dependencies by reassign/set-null/delete, then delete main record).

The goal is controlled deletion with explicit user choices instead of blind cascade deletion.

---

## Architecture at a glance

Operational flow in delete view (high level):

1. detect whether target object has blocking dependencies,
2. show dependency modal with options (bulk reassign, individual actions, bulk related delete),
3. apply selected dependency actions,
4. re-check dependencies,
5. delete main object only when state is acceptable (or by explicit bulk delete path).

`delete_mixins.py` implements core steps 1, 3, and utility pieces used to render step 2.

---

## Top-level helpers

## `DEFAULT_EXCLUDED_DEPENDENCY_MODEL_LABELS`

A curated list of model labels ignored during dependency checks and deletes, e.g.:

- `RecycleBin`
- `TimelineSpanBy`
- `PinnedView`
- `SavedFilterList`
- other user/session/state artifacts

Why exclusion exists:

- prevents irrelevant operational metadata from blocking business-object deletion,
- avoids deleting framework/user-preference records unintentionally.

---

## `get_excluded_models(excluded_model_labels=None)`

Resolves model names to concrete model classes by scanning all app configs.

Behavior:

- takes custom labels or defaults above,
- finds first matching model class per label,
- logs warning for unresolved labels,
- returns class list used for membership checks (`if related_model in excluded_models`).

This lets each delete view override `excluded_dependency_model_labels` safely by label rather than hardcoding imports.

---

## `is_field_nullable(related_model, main_model)`

Determines if FK from `related_model` to `main_model` allows `NULL`.

Usage impact:

- enables/disables `set_null` option in individual dependency actions.

If FK cannot be inferred, returns `False`.

---

## `get_fk_field_name(related_model, main_model)`

Finds FK field name in dependent model that points to main model.

Used by reassignment logic:

- `setattr(dep_record, fk_field_name, new_target)`

Returns `None` if relation is not found.

---

## `build_dependency_context(...)`

Centralized context builder for delete dependency templates/modals.

Important keys produced:

- blocker/safe lists: `cannot_delete`, `can_delete`
- counts: `cannot_delete_count`, `can_delete_count`
- dependency record payload: `dependent_records`, `related_model`
- form controls: `available_targets`, `is_nullable`, `delete_mode`
- UI behavior: `view_id`, `hx_target`, visibility flags

This keeps template payload shape consistent across delete actions.

---

## `DeleteDependencyMixin`

Primary responsibility: compute dependency state and provide paginated related-record slices for modal UIs.

### `_get_excluded_models()`

- reads `self.excluded_dependency_model_labels` if set on view,
- otherwise uses module defaults,
- delegates class resolution to `get_excluded_models(...)`.

### `_is_field_nullable(related_model)`

- wrapper over helper, bound to `self.model`.

---

### `_check_dependencies(record_id, get_all=False)` (core engine)

This is the blocker classification method used before delete decisions.

Algorithm:

1. load main object from `self.model.all_objects` by ID,
2. gather reverse relations from `self.model._meta.related_objects`,
3. skip excluded related models,
4. for each relation:
   - fetch dependent queryset (`all_objects` if available, else reverse manager),
   - compute total count,
   - fetch preview rows (first 10 unless `get_all=True`),
5. accumulate dependency descriptors.

Output triple:

- `cannot_delete`: list with dependency-rich entries
- `can_delete`: list with safe entries
- `dependency_details`: mapping by object ID

`cannot_delete` item shape:

- `id`, `name`
- `dependencies`: list of relation summaries:
  - `model_name`
  - `count` (full count)
  - `records` (string preview)
  - `related_model`, `related_name`, `related_records`
  - `has_more`
- `total_individual_records`

Notable behavior:

- record can be in `can_delete` only when *no* non-excluded relation has dependent rows.
- all errors are logged and method degrades to empty outputs (no hard crash).

---

### `_get_paginated_dependencies(record_id, related_name, page=1, per_page=8)`

Used for infinite-scroll expansion of one dependency relation.

Returns:

- `records`, `total_count`, `has_more`, `next_page`, `related_model`

Returns empty payload when relation not found or on error.

---

### `_get_paginated_individual_records(record_id, page=1, per_page=8)`

Builds a flattened list of all dependency records across relations for individual-action UI.

Returns:

- paginated `records`
- `available_targets` (other main objects for reassignment)
- `is_nullable` (derived from relation metadata)
- pagination info

Important nuance:

- it aggregates related rows across relations into one list; ordering depends on relation traversal sequence.

---

### `_dependent_records_from_cannot_delete(cannot_delete, limit=8)`

Convenience adapter that extracts:

- `dependent_records`
- `related_model` (last iterated dependency model)
- `is_nullable` (based on last iterated model FK)
- `has_more`

Often used right after `_check_dependencies(...)` to prepare initial modal payload quickly.

---

## `DeleteReassignMixin`

Primary responsibility: mutate dependency records according to user-selected strategy, then support main-object deletion.

### `_perform_bulk_reassign(record_id, new_target_id)`

Reassigns **all** dependent rows (across non-excluded relations) from source main object to new target main object.

Flow:

1. fetch source and target from `self.model.all_objects`,
2. iterate reverse relations except excluded ones,
3. get relation FK field name with `get_fk_field_name(...)`,
4. set FK to new target for each dependent row and save.

Returns reassigned row count.

Raises `ValueError` when target does not exist (`raise ValueError(...) from exc` after `ObjectDoesNotExist`).

---

### `_perform_individual_action(record_id, actions, delete_mode=None)`

Processes per-dependent-row actions.

Input `actions` contract:

```python
{
  "123": {"action": "reassign", "new_target_id": "9"},
  "124": {"action": "set_null", "new_target_id": None},
  "125": {"action": "delete", "new_target_id": None},
}
```

Supported actions:

- `reassign`
- `set_null` (only if FK nullable)
- `delete`

Soft consistency rule:

- if `delete_mode == "main_soft"`, dependent `delete` action first archives record in `RecycleBin`.

Returns count of processed dependent rows.

Raises `ValueError` for invalid target in action payload (chained from `ObjectDoesNotExist` where applicable).

---

### `_delete_main_object(delete_mode, user=None)`

Deletes the main object itself:

- if `delete_mode == "main_soft"`: archive main object to `RecycleBin` first,
- always calls `self.object.delete()`.

This keeps main-record behavior aligned with user-selected mode.

---

### `_bulk_delete_related()`

Deletes all dependent rows across all non-excluded relations for `self.object`.

Important:

- this method does **not** delete main object.
- caller (delete view) should call `_delete_main_object(...)` afterward.

---

### `_find_related_record_by_id(record_id_to_find)`

Searches related models (excluding excluded ones) for a dependent row with given ID.

Returns record or `None`.

Used by delete view actions like:

- soft delete single dependency row,
- hard delete single dependency row.

---

## How `delete.py` uses these mixins

`HorillaSingleDeleteView` composes:

- `DeleteDependencyMixin`
- `DeleteReassignMixin`

Common action wiring:

- `check_dependencies_with_mode` -> `_check_dependencies` + context build
- `bulk_reassign` -> `_perform_bulk_reassign` + `_delete_main_object`
- `individual_action` -> `_perform_individual_action` + re-check + maybe main delete
- `bulk_delete` -> `_bulk_delete_related` + `_delete_main_object`
- `soft_delete_record` / `delete_single_record` -> `_find_related_record_by_id`

This separation keeps action controller logic in `delete.py` and mutation primitives in `delete_mixins.py`.

---

## Transaction and safety considerations

- mixin methods generally do not open transactions themselves.
- delete view wraps critical action branches in `transaction.atomic()`; `delete.py` imports `transaction` from `horilla.db` in the **First party imports (Horilla)** section (see [coding_rule.md](../../../../../coding_rule.md#import-order-and-section-comments)).
- exclusion list prevents accidental operations on system/helper models.
- many queries use `all_objects` when available, ensuring soft-deleted rows are considered where intended.

---

## Practical extension points

## 1) Custom exclusion set

Set on delete view:

```python
excluded_dependency_model_labels = [
    "RecycleBin",
    "AuditLog",
    "MyCustomSystemModel",
]
```

## 2) Change per-page sizes in UI calls

Pass different `per_page` to pagination helpers from your modal load-more endpoints.

## 3) Restrict reassign targets

Override usage around `available_targets` (or wrap helper results) to enforce business rules such as same company/department.

---

## Example: using helpers in a custom delete view

```python
from horilla_generics.views.delete import HorillaSingleDeleteView


class LeadDeleteView(HorillaSingleDeleteView):
    excluded_dependency_model_labels = ["RecycleBin", "TimelineSpanBy", "LogEntry"]
    reassign_all_visibility = True
    reassign_individual_visibility = True
```

The mixins automatically use these flags/labels through `build_dependency_context` and `_get_excluded_models`.

---

## Caveats and nuanced behavior

- `_dependent_records_from_cannot_delete` returns `related_model`/`is_nullable` based on the last dependency iterated, which may not represent mixed-model lists perfectly.
- `_perform_individual_action` resolves related rows using `related_model.objects.filter(...)` in one branch; model manager behavior can differ from `all_objects` expectations depending on app setup.
- relation matching and FK discovery rely on Django model metadata; unusual relation patterns may need overrides.

---

## Summary

`delete_mixins.py` is the core dependency-resolution toolkit behind single-record deletion flows.
It combines dependency introspection, pagination helpers, reassignment/nullification/delete operations, and soft-delete integration with `RecycleBin`, enabling safe and interactive deletion workflows in Horilla generic views.
