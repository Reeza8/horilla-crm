# Horilla Custom Fields — deep dive (`custom_fields`)

## What this app does

Lets an admin add arbitrary extra fields (`cf_1`, `cf_2`, ...) to any opted-in model — text, number, choice, multi-choice — and have them show up everywhere that model's data appears: create/edit forms (single-step and multi-step wizards), list views (columns, column picker), filters, detail views (header + tabs, field selector), and exports. No CRM model is ever imported by name here; every touch point is model-agnostic and driven entirely by a feature registry.

Every one of those touch points is a real `horilla.extension.*` registration (`FormExtension`, `FilterExtension`, `DetailExtension`, `DetailSectionExtension`, `ListExtension`, `ViewExtension`, `MixinExtension`) — see [extension index](../horilla/extension/inherit.md). None of it is monkey-patched.

---

## App startup (`apps.py`)

`CustomFieldsConfig`:

| Setting | Value |
|---------|-------|
| `url_prefix` | `custom-fields/` |
| `url_namespace` | `custom_fields` |
| `auto_import_modules` | `menu`, `view_extensions`, `registration`, `extensions`, `detail_extensions`, `filter_extensions`, `mixin_extensions`, `list_extensions` |

No `ready()` override — every extension self-registers at import time via `__init_subclass__`, the same way any other `_inherit_*` extension does.

---

## Feature registration (`registration.py`)

```python
register_feature("custom_fields", "custom_fields_models", auto_register_all=False)
```

Any app opts a model in with a plain call from its own `registration.py`:

```python
register_model_for_feature("leads", "Lead", features=["custom_fields_models"])
```

No form/view class is registered by name anywhere in `custom_fields` — `extensions.py`, `filter_extensions.py`, and `detail_extensions.py` each discover which models are opted in from `FEATURE_REGISTRY.get("custom_fields_models", ...)` at runtime and generate the real extension registrations dynamically.

---

## Models (`models.py`)

- **`CustomFieldDefinition`** — one row per custom field: `field_type` (`small_text`, `large_text`, `number`, `choice`), label, choices (for `choice` fields), which model it applies to.
- **`CustomFieldValue`** — one row per (definition, object) pair holding the actual stored value.

Both extend `HorillaCoreModel` (company-scoped, like every other Horilla model).

---

## Discovery pattern (dynamic, per-model registration)

Three files register real extensions **per opted-in model**, discovered at runtime rather than declared statically:

| File | Extension type | Discovers via |
|------|-----------------|----------------|
| `extensions.py` | `FormExtension` | `HorillaMultiStepForm`/`HorillaModelForm` subclasses whose `Meta.model` opted in |
| `filter_extensions.py` | `FilterExtension` | `HorillaFilterSet` subclasses whose `Meta.model` opted in |
| `detail_extensions.py` | `DetailExtension` + `DetailSectionExtension` | `HorillaDetailView`/`HorillaDetailSectionView` subclasses via Horilla's own `_view_registry` |

Each registers a **pre-compose hook** (`horilla.extension._pre_compose_hooks.register_pre_compose_hook`) so discovery re-runs every time Horilla is about to compose that extension type — covering a model opted in *after* `custom_fields` itself has already loaded (a CRM app's `registration.py` may run later in `INSTALLED_APPS` order). This is a real registration call, not a reassignment of Horilla's own bootstrap functions.

---

## Bare mixins and functions (`mixin_extensions.py`)

Some targets are never dispatched via `as_view()`/`get_*_class()` at all — a bare mixin only ever reached through ordinary Python inheritance, or a plain module-level function. `MixinExtension` (`_inherit_mixin`, see [mixin/inherit.md](../horilla/extension/mixin/inherit.md)) patches these directly at startup, once, since there is no per-request resolution point to hook into:

| Extension | Target |
|-----------|--------|
| `CustomFieldFilterFieldsExtension` | `HorillaListFilterFieldsMixin._get_model_fields` (Filter Records field dropdown) |
| `CustomFieldBulkExportExtension` | `HorillaBulkExportMixin.handle_export` (export-file writer) |
| `CustomFieldExportCellExtension` | `get_export_cell_value` (bare module function, one export cell) |
| `CustomFieldDetailRenderExtension` | `detail_field.render` (Change Detail View Fields selector) |
| `CustomFieldDetailDefaultsExtension` | `detail_field._get_detail_field_defaults` |
| `CustomFieldDetailEnsureSerializableExtension` | `detail_field._ensure_json_serializable` |
| `CustomFieldColumnSelectionFormExtension` | `ColumnSelectionForm.__init__` (a plain `django.forms.Form`, not a `HorillaModelForm`, so `FormExtension` can't reach it) |

`CustomFieldBulkExportExtension.handle_export` is the one place with a genuine (documented, scoped) exception: Horilla's real `handle_export` reads its queryset with a bare `for obj in queryset:` loop, not a method call, so there is no hook to override — it temporarily swaps `QuerySet.__iter__` for the duration of that one call, restored in `finally`.

---

## Shared base classes (`list_extensions.py`, `view_extensions.py`)

Two targets are shared base classes every concrete subclass across every app inherits — there is no single concrete class to name:

| Extension | Target (base class) | Effect |
|-----------|---------------------|--------|
| `CustomFieldListContextExtension` (`list_extensions.py`) | `HorillaListView` | Attaches `cf_*` values to list rows, excludes them from sortable columns |
| `CustomFieldMultiStepFormKwargsExtension` (`view_extensions.py`) | `HorillaMultiStepFormView` | Keeps every selected Multiple Choice `cf_*` value across wizard steps |

`resolve_list_view_class()`/`resolve_view_class()`'s base-class MRO fallback (see [extension index — Targeting a shared base class](../horilla/extension/inherit.md#targeting-a-shared-base-class)) is what makes a registration directly on `HorillaListView`/`HorillaMultiStepFormView` apply to every concrete list view/wizard automatically, instead of requiring one registration per concrete class.

`view_extensions.py` also registers plain concrete-class `ViewExtension`s: `EditFieldView`/`UpdateFieldView`/`CancelEditView` (inline edit of a `cf_*` field), `ExportView` (Select Columns to Export modal + export writer), and `ListColumnSelectFormView` (Add Column to List modal).

---

## Multi-step wizard field placement (`integration.py`)

`apply_multi_step_custom_fields()` adds `cf_*` fields to a wizard form's `fields` and also appends them to `form.step_fields[last_step]` explicitly. This matters because `HorillaMultiStepForm.__init__` auto-assigns any field not already listed in `step_fields` to the last step — but only for real model fields (it silently skips anything raising `FieldDoesNotExist`, which every `cf_*` name does, since they're synthetic form fields, not DB columns). Since `cf_*` fields are added *after* that auto-assignment already ran (via `setup_form_extension_fields()`, called after `FormExtension`'s composed `__init__`), they must be added to `step_fields` explicitly or the wizard never renders them.

`step_fields` is written as a fresh per-instance dict (`{**form.step_fields, ...}`), not mutated in place — it's a class-level attribute shared across every instance/company using that form.

---

## Typical flows

1. Admin defines a custom field (`Description`, type `small_text`) for `Lead`.
2. User opens the Lead create wizard → `CustomFieldFilterFieldsExtension`'s sibling `FormExtension` adds `cf_1` to the last step, pre-filled if editing.
3. User views the Lead list → `CustomFieldListContextExtension` attaches saved `cf_1` values to each row; the column picker (`ListColumnSelectFormView`) lets the user add it as a column.
4. User filters Leads by `cf_1` → `FilterExtension`'s `_build_row_q` builds a real `Q()` against `CustomFieldValue`.
5. User opens a Lead's detail page → `DetailExtension`/`DetailSectionExtension` merge `cf_1` into the header/Details tab; the field selector (`detail_field.render`) lets the user reposition it.
6. User exports Leads → `ExportView`'s `ViewExtension` adds `cf_1` to the column picker; `CustomFieldBulkExportExtension` attaches values before the writer runs.

---

## Related documentation

- [Extension system index](../horilla/extension/inherit.md) — every `_inherit_*` mechanism used above
- [_inherit_mixin guide](../horilla/extension/mixin/inherit.md) — bare mixins/functions
- [_inherit_form guide](../horilla/extension/forms/inherit.md), [_inherit_filter guide](../horilla/extension/filter/inherit.md), [_inherit_list guide](../horilla/extension/list/inherit.md), [_inherit_view guide](../horilla/extension/view/inherit.md)
- `horilla.contrib.duplicates`, `horilla.contrib.cadences` — other apps using the same `_inherit_view` base-class-targeting pattern
</content>
