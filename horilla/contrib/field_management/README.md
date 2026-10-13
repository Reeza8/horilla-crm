# Field Management (`horilla.contrib.field_management`)

**Package:** `horilla.contrib.field_management` (installed as `"horilla.contrib.field_management"`)
**Current version:** see [`__version__.py`](__version__.py)
**Settings URL prefix:** `/field-management/` · namespace `field_management`

One app for three per-company field settings: **custom fields**, **field
requirements** and **form layouts** (see
[`field_requirements.md`](../../../docs/horilla/contrib/field_management/field_requirements.md)
and [`form_layouts.md`](../../../docs/horilla/contrib/field_management/form_layouts.md)
for the last two). This document covers **custom fields**.

Custom fields let an administrator define extra fields (`cf_1`, `cf_2`, …) on any
**opted-in** model — small text, large text, number, single choice, multiple
choice, date, or date and time — and surface them wherever that model's data
appears. Values are stored in `CustomFieldValue` rows, **not** as model columns,
so a field can be created, renamed or deleted at runtime without a migration.

Everything is wired through the extension framework in `horilla/extension/`
(`ListExtension`, `KanbanExtension`, `ViewExtension`, `FormExtension`, …). No
Horilla class is monkey-patched, and `horilla.contrib.core`, `generics`,
`reports`, `dashboard` and the CRM apps never import this app.

---

## Why custom fields need hooks

A field added with a **model extension** (`_inherit_model`) is a real column:
Django lists it in `Model._meta`, so every place that reads `_meta` (mail
templates, field permissions, reports, exports, conditions…) shows it with no
extra work.

A custom field is not a column — it has no `_meta` entry. Each place that reads
`_meta` therefore exposes a small, generic hook, and this app overrides it with
an extension. The hooks carry no custom-field wording; any app can use them for
fields that aren't model columns.

---

## Surfaces and how each plugs in

| Surface | Extension | Core hook it overrides |
|---------|-----------|------------------------|
| Create / edit forms (single-step & wizard) | `FormExtension` (`custom_fields_forms.py`) | `setup_form_extension_fields` |
| List columns, column picker, row values | `ListExtension` / `ViewExtension` (`custom_fields_list.py`, `custom_fields_view.py`) | `HorillaListView.get_context_data`, `ListColumnSelectFormView` |
| Filter Records panel | `FilterExtension` + mixin (`custom_fields_filter.py`, `custom_fields_mixin.py`) | filter composition |
| Detail header / Details tab, inline edit, Edit Details | `DetailExtension`, `DetailSectionExtension`, `ViewExtension` (`custom_fields_detail.py`, `custom_fields_view.py`) | `ExtraFieldsProvider` |
| Export (modal, writer) | `ViewExtension` (`custom_fields_view.py`) | `ExportView.get_available_models` / `export_model_data` |
| Scheduled export (modal + emailed file) | `ViewExtension` on `ScheduleExportProvider` (`custom_fields_view.py`) | `get_extra_fields`, `export_model_data` |
| Import → Download Template | `ViewExtension` (`custom_fields_import.py`) | `get_model_fields` on the import views |
| Quick filters | `ListExtension` (`custom_fields_quick_filter.py`) | `get_extra_quick_filter_fields`, `get_extra_quick_filter_choices`, `apply_extra_quick_filter` |
| Kanban, Group By, Chart (Single Choice) | `ListExtension` + one `KanbanExtension` per kanban view (`custom_fields_group_by.py`) | `get_group_field`, `persist_group_value` |
| Kanban / Group By settings | `ViewExtension` (`custom_fields_group_by.py`) | settings view `get_form` / `post` |
| Reports (columns, filters, groupings, detail table, export) | `ViewExtension` on `ReportFieldProvider` (`custom_fields_report.py`) | `get_virtual_fields` |
| Dashboard components (pickers, table, chart, KPI) | `ViewExtension` + `FormExtension` (`custom_fields_dashboard.py`) | `get_extra_choices(model, purpose)` |
| Condition dropdowns | `ViewExtension` / `FormExtension` (`custom_fields_conditions.py`) | `get_extra_field_choices(model)`, `_get_model_field_choices` |
| Condition checks (approvals, reviews, workflow, automations, cadences, duplicates, scoring, forecast, calendar, dashboard) | `ViewExtension` on `ConditionFieldProvider` (`custom_fields_condition_field.py`) | `owns`, `get_value`, `build_condition_q`, … |
| Mail / notification template "Insert Fields" | `ViewExtension` (`custom_fields_view.py`) | `get_context_data` (`model_fields`) |
| Field permissions modal | `ViewExtension` (`custom_fields_view.py`) | `get_extra_permission_fields` |

Details for each core hook are in the docs linked under
[Related documentation](#related-documentation).

---

## Field permissions

Field permissions (`hidden` / `readonly`) apply to custom fields like any other
field, keyed by `cf_<id>`:

- **hidden** — `get_custom_field_definitions(model)` drops the definition for
  that user, so the field disappears from forms, detail, list columns, the column
  picker, bulk edit, export, quick filters, grouping, reports and dashboards.
- **readonly** — the form field is disabled and not required, the bulk-edit
  entry is not editable, and inline edit is refused.

The Settings → Roles / Users field-permission modal lists custom fields so the
permission can be set (`CustomFieldPermissionFieldsExtension`).

---

## Reports and dashboards

The reports engine resolves computed **virtual fields** (values added with
`queryset.annotate()`) for column pickers, filters, row/column groups, previews,
the detail table and exports. `ReportFieldProvider` is its seam for fields that
come from the current request.

`CustomFieldReportFieldProviderExtension.get_virtual_fields(model)` returns each
visible custom field as a `VirtualField` named `cf_<id>`:

- annotation = a `Subquery` on `CustomFieldValue` (text and choices are shown
  without the JSON list markup, numbers/dates keep their typed column)
- `choices` set for Single Choice, so it can be grouped
- `show_in_detail=True`, so it is a column in the report detail table

It is resolved per request (and cached on the request), so created / renamed /
deleted fields, company scoping and field permissions apply immediately in every
worker process — there is no process-wide registry to refresh.

Dashboard components reuse the same virtual fields: the dashboard pickers list
custom fields through `get_extra_choices`, and the component code annotates the
queryset with `annotate_component_virtual_fields` before grouping, aggregating
or listing.

Limits: reports treat every virtual field as numeric in the Y-axis list, so text
and choice custom fields also appear under "Sum of …" there; the report detail
table cannot sort by a custom-field column.

---

## Condition fields

`ConditionFieldProvider` is the seam for condition fields that aren't model
columns. `CustomFieldConditionProviderExtension` supplies:

| Method | Custom-field behaviour |
|--------|------------------------|
| `owns(field_name)` | `True` for `cf_<id>` |
| `get_choices(model)` | `("cf_<id>", label)` for the model's definitions |
| `get_label` / `get_widget_info` | label and a widget matching the field type (a `select` with the configured options for choice types, date pickers for dates) |
| `get_value(field_name, instance)` | stored value as text (dates/datetimes as ISO strings, multi-choice joined by `,`) |
| `build_condition_q(model, field_name, operator, value)` | `Q(pk__in=…)` built from `CustomFieldValue` for queryset-based engines |

Rule engines call the generic helpers in `generics/forms/condition_fields.py`
(`evaluate_extension_condition`, `get_extension_condition_q`), so one
implementation covers every engine. Single Choice values are stored as a JSON
list (`["a"]`); the matcher in `hooks/filter.py` parses them, so *equals* works.

Condition checks compare values **as text** with each engine's own operators.
Date and Number custom fields therefore support equals / contains but not
date-aware or numeric comparison, except in Lead assignment rules, which add
date-aware evaluation (`evaluate_date_criterion`).

---

## Mail and notification templates

The "Insert Fields" modal lists custom fields and inserts

```django
{{ instance|extension_field:"cf_1" }}
```

`extension_field` is a generic template filter (`horilla_tags`, available in all
templates as a builtin) that asks the condition-field provider for the value, so
it works wherever templates render with an `instance` — mail, notification,
automations and workflow.

---

## Kanban, Group By and Chart

Only **Single Choice** fields can group (a Multiple Choice value belongs to
several groups at once).

These views call `get_group_field(name)` instead of `Model._meta.get_field()`.
The extension answers it for `cf_*` names with a stand-in field that has the
choices, annotates the queryset with the selected choice (so `filter(cf_1=…)`
and `values("cf_1")` work), and implements `persist_group_value()` so moving a
Kanban card saves the new value. Kanban cannot be extended through a shared base
class, so `register_kanban_extensions()` registers one `KanbanExtension` per
concrete kanban view, from a pre-compose hook, after all views are imported.

`KanbanGroupBy.save()` only accepts real fields, so the settings
`ViewExtension` stores a `cf_*` choice directly.

---

## App startup (`apps.py`)

`FieldSettingsConfig` (`AppLauncher`):

| Setting | Value |
|---------|--------|
| `name` | `horilla.contrib.field_management` |
| `label` | `field_management` |
| `url_prefix` | `field-management/` |
| `url_namespace` | `field_management` |
| `auto_import_modules` | `menu`, `registration`, `extensions` |

`extensions/__init__.py` imports every extension module; each registers itself
at import time through `__init_subclass__`, like all `_inherit_*` extensions.

---

## Feature registration (`registration.py`)

```python
register_feature(
    "custom_fields",
    "custom_fields_models",
    auto_register_all=False,
)
```

`auto_register_all=False` is required. Many CRM models call
`register_model_for_feature(..., all=True)`; without this gate every such model
would become custom-field-configurable.

### Opt a model in (consuming app)

From the **consuming** app's `registration.py` (e.g. `horilla_crm/leads/`):

```python
from horilla.registry.feature import register_model_for_feature

register_model_for_feature(
    app_label="leads",
    model_name="Lead",
    features=["custom_fields_models"],
)
```

`custom_fields_forms.py`, `custom_fields_filter.py` and `custom_fields_detail.py`
read `FEATURE_REGISTRY["custom_fields_models"]` at compose time and register
per-model / per-form extensions dynamically. No form or view class is hard-coded
by import path inside this app.

---

## Models (`models.py`)

Both extend `HorillaCoreModel` (company-scoped).

### `CustomFieldDefinition`

One row per custom field on a content type:

| Field | Role |
|-------|------|
| `content_type` | Target model (`HorillaContentType`) |
| `name` | Admin-facing label |
| `field_type` | `small_text`, `large_text`, `number`, `choice` (multi), `single_choice`, `date`, `datetime` |
| `is_required` | Form required flag |
| `choices` | Comma-separated options (choice types) |
| `order` | Display order |
| `is_full_width` | Span both columns of the form |

Synthetic form/list keys are `cf_<pk>` (see `utils.custom_fields.is_custom_field_name`).

### `CustomFieldValue`

One row per `(definition, object)` holding the stored value (text / JSON list for
choices via `parse_choice_values` / `serialize_choice_values`).

Each type has its own typed column so filters and rule engines compare real
values: `value_text` (text and choices), `value_number`, `value_date`, and
`value_datetime` (timezone-aware, stored in UTC). `set_value` writes the column
for the definition's type and clears the rest.

**Date and Date and Time** render as `<input type="date">` /
`<input type="datetime-local">`, like Horilla's own date fields. With the
`horilla_jalali` app installed and Shamsi selected, the same inputs open the
Jalali picker, which submits Gregorian ISO values — the database always holds
Gregorian dates. Display (detail, list, export, Edit Details) goes through the
composed `DateTimeFormatter`, so each viewer sees their own date format,
timezone and calendar.

---

## Bare mixins / functions (`extensions/custom_fields_mixin.py`)

Targets that never go through `as_view()` / `resolve_*_class()` use
`MixinExtension` (`_inherit_mixin` — see
[mixin/inherit.md](../../../docs/horilla/extension/mixin/inherit.md)):

| Extension | Target |
|-----------|--------|
| `CustomFieldFilterFieldsExtension` | `HorillaListFilterFieldsMixin._get_model_fields` |
| `CustomFieldBulkExportExtension` | `HorillaBulkExportMixin.handle_export` |
| `CustomFieldExportCellExtension` | `get_export_cell_value` (module function) |
| `CustomFieldDetailRenderExtension` | `detail_field.render` |
| `CustomFieldDetailDefaultsExtension` | `detail_field._get_detail_field_defaults` |
| `CustomFieldDetailEnsureSerializableExtension` | `detail_field._ensure_json_serializable` |
| `CustomFieldColumnSelectionFormExtension` | `ColumnSelectionForm.__init__` (plain Django form) |

New behaviour should prefer the provider / view / list hooks above; these remain
for targets that have none.

---

## Multi-step wizard placement (`custom_fields_integration.py`)

`apply_multi_step_custom_fields()`:

1. Adds `cf_*` widgets to `form.fields`
2. Appends those names to `form.step_fields[last_step]` **explicitly**

Why: `HorillaMultiStepForm.__init__` auto-assigns unlisted fields to the last step
only for real model fields. Synthetic `cf_*` names raise `FieldDoesNotExist` and
are skipped. Because custom fields are injected *after* that auto-assignment (via
`setup_form_extension_fields()` on the composed form), they must be added to
`step_fields` or the wizard never renders them.

`step_fields` is copied per instance (`{**form.step_fields, ...}`) — never mutated
in place — because it is a class-level attribute shared across companies/forms.

---

## Package layout

```text
field_management/
├── apps.py                          # AppLauncher config
├── registration.py                  # register_feature(...)
├── models.py                        # Definition, Value, FieldRequirement, FormLayoutField
├── menu.py / urls.py / views/ / forms.py / filters.py
├── custom_fields_integration.py     # apply_* / clean / save helpers for forms
├── extensions/
│   ├── custom_fields_forms.py            # FormExtension (create / edit)
│   ├── custom_fields_list.py             # ListExtension (rows, columns)
│   ├── custom_fields_view.py             # ViewExtension (export, schedule, bulk edit, inline edit, Insert Fields, permissions)
│   ├── custom_fields_detail.py           # Detail / DetailSection extensions
│   ├── custom_fields_filter.py           # FilterExtension
│   ├── custom_fields_mixin.py            # MixinExtension (bare mixins / functions)
│   ├── custom_fields_quick_filter.py     # quick filter hooks
│   ├── custom_fields_group_by.py         # Kanban / Group By / Chart + settings
│   ├── custom_fields_import.py           # import wizard + template download
│   ├── custom_fields_conditions.py       # condition dropdowns
│   ├── custom_fields_condition_field.py  # ConditionFieldProvider
│   ├── custom_fields_report.py           # ReportFieldProvider
│   ├── custom_fields_dashboard.py        # dashboard pickers
│   ├── field_requirements.py / form_layouts.py
├── hooks/                           # detail / export / filter / form / list helpers
├── utils/                           # cf_* naming, definitions, permissions helpers
├── registry/ · templates/ · templatetags/ · static/ · locale/ · migrations/
└── tests/
```

Helper modules under `hooks/` and `utils/` support the registrations in
`extensions/`.

---

## Not supported yet

- **Import**: the template lists custom fields, but import steps 1–4 only map
  and save model columns; a custom-field column in an uploaded file is ignored.
- **Reports / dashboards**: custom-field columns cannot be sorted in the report
  detail table; reports list text/choice fields under numeric Y-axis choices.
- **Grouping**: Multiple Choice fields cannot group Kanban, Group By or Chart.
- **Condition checks** compare as text (see above).

---

## Related documentation

| Topic | Doc |
|-------|-----|
| Extension system index | [`docs/horilla/extension/inherit.md`](../../../docs/horilla/extension/inherit.md) |
| `_inherit_mixin` | [`docs/horilla/extension/mixin/inherit.md`](../../../docs/horilla/extension/mixin/inherit.md) |
| `_inherit_form` / filter / list / kanban / view | [`forms`](../../../docs/horilla/extension/forms/inherit.md) · [`filter`](../../../docs/horilla/extension/filter/inherit.md) · [`list`](../../../docs/horilla/extension/list/inherit.md) · [`kanban`](../../../docs/horilla/extension/kanban/inherit.md) · [`view`](../../../docs/horilla/extension/view/inherit.md) |
| Grouping hooks (`get_group_field`, `persist_group_value`) | [`list.md`](../../../docs/horilla/contrib/generics/views/list.md) · [`kanban.md`](../../../docs/horilla/contrib/generics/views/kanban.md) · [`groupby.md`](../../../docs/horilla/contrib/generics/views/groupby.md) · [`chart.md`](../../../docs/horilla/contrib/generics/views/chart.md) |
| Quick filter hooks | [`quick_filter.md`](../../../docs/horilla/contrib/generics/views/toolkit/quick_filter.md) |
| Condition fields | [`condition_fields.md`](../../../docs/horilla/contrib/generics/forms/condition_fields.md) · [`condition_widget.md`](../../../docs/horilla/contrib/generics/views/helpers/condition_widget.md) |
| Reports / dashboards | [`reports.md`](../../../docs/horilla/contrib/reports/reports.md) · [`dashboard.md`](../../../docs/horilla/contrib/dashboard/dashboard.md) |
| Feature registry | [`docs/horilla/registry/feature.md`](../../../docs/horilla/registry/feature.md) |
| Versioning | [`docs/versioning.md`](../../../docs/versioning.md) |
