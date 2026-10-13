# Horilla Chart View (`horilla_generics/views/chart.py`)

## 🎯 Purpose

`HorillaChartView` renders filtered model data as interactive charts (ECharts) while reusing `HorillaListView` query/filter logic.

It supports:
- group-by dimension selection (FK / choice / boolean / date-like buckets)
- chart type selection (column, line, pie, bar, stacked, heatmap, sankey, radar, etc.)
- optional Y-axis aggregation on numeric fields (`sum`, `avg`, `min`, `max`) or default record count
- stacked/two-dimension charts for supported chart types
- click-to-drill into list view URLs
- optional “Add to Dashboard” action for allowed users

---

## 📦 Files involved

```text
horilla_generics/views/chart.py
horilla_generics/templates/chart_view.html
```

`chart_view.html` consumes many context keys produced by `HorillaChartView.get_context_data()`.

---

## 🔁 Main class

### 📍 Definition

```python
class HorillaChartView(HorillaListView):
    template_name = "chart_view.html"
    bulk_select_option = False
    table_class = False
    paginate_by = None
    default_chart_type = "column"
```

### Key configurable attributes

| Attribute | Default | Meaning |
|---|---|---|
| `default_chart_type` | `"column"` | fallback chart type |
| `allowed_chart_types` | all keys from `CHART_TYPE_CHOICES` | accepted chart_type GET values |
| `chart_group_by_param` | `"chart_group_by"` | query key for X-axis dimension |
| `chart_stack_by_param` | `"chart_stack_by"` | query key for second dimension in stacked charts |
| `chart_value_field_param` | `"chart_y_field"` | query key for Y-axis metric field |
| `chart_stack_by_single` | `"__single__"` | sentinel used by radar for single-dimension mode |
| `STACKED_CHART_TYPES` | tuple | chart types that support/need stacked payload |

---

## 📊 Supported chart options

From `CHART_TYPE_CHOICES`:

- `column`
- `line`
- `pie`
- `funnel`
- `bar`
- `donut`
- `stacked_vertical`
- `stacked_horizontal`
- `scatter`
- `treemap`
- `area`
- `heatmap`
- `sankey`
- `radar`

Y-axis metric choices (`CHART_METRIC_CHOICES`):
- `sum`
- `avg`
- `min`
- `max`

---

## 🧠 Data selection logic

### 1) Dimension choices (X-axis)

`get_chart_dimension_choices()` includes fields that pass `_field_is_chart_dimension()`:
- always allowed: `ForeignKey`, `DateField`, `DateTimeField`
- also allowed: editable booleans and fields with choices
- excludes m2m/non-concrete fields
- applies `exclude_kanban_fields` / `include_kanban_fields`
- filters hidden fields by user permission

### 2) Numeric choices (Y-axis)

`get_chart_numeric_choices()` includes editable numeric fields:
- Integer / BigInteger / PositiveInteger / SmallInteger / Decimal / Float
- also permission-filtered (hidden fields removed)

### 3) Group-by field resolution

`get_group_by_field()` chooses in order:
1. valid request value from `chart_group_by_param`
2. saved `KanbanGroupBy` preference (`view_type="group_by"`) if valid
3. first legacy allowed group_by field
4. first visible dimension choice

### 4) Value field + metric

Parsed from GET key `chart_y_field`:
- empty -> count records
- `sum__amount` / `avg__amount` / `min__amount` / `max__amount` -> aggregate numeric field
- bare numeric field name also works and defaults metric to `sum`

---

## ⚙️ Payload builders

### `build_chart_payload(queryset, group_by, value_field=None, value_metric=None)`

Returns:
- `{"labels": [...], "data": [...], "urls": [...]}`

Notes:
- if dimension is date/datetime, buckets by month (`TruncMonth`)
- drill-down URLs are skipped for date-bucketed dimensions
- unsupported dimension -> returns error

### `build_stacked_payload(queryset, primary, secondary, value_field=None, value_metric=None)`

Returns:
- payload containing `stackedData`:
  - `categories` (primary axis labels)
  - `series` (secondary groups)
- plus totals (`labels`, `data`, `urls`) for parent config

Used when `chart_type` is in `STACKED_CHART_TYPES`.

---

## 🌐 URLs and drill-down behavior

### `_list_drill_url(filter_field, filter_value)`
Builds list URL applying one exact filter:
- `layout=list`
- `apply_filter=true`
- `field`, `operator=exact`, `value`
- preserves `search` and `view_type`
- optionally includes `section` from `get_section_info_for_model(...)`

### `_list_drill_url_two(field1, value1, field2, value2)`
Same pattern but applies two filter triplets (for stacked clicks).

---

## 🧩 Context variables set for `chart_view.html`

Important keys produced in `get_context_data()`:

| Context key | Example |
|---|---|
| `chart_dimension_choices` | `[("status", "Status"), ("owner", "Owner")]` |
| `chart_numeric_field_choices` | `[("", "Record count"), ("sum__amount", "Sum of Amount"), ...]` |
| `chart_group_by_param` | `"chart_group_by"` |
| `chart_stack_by_param` | `"chart_stack_by"` |
| `chart_value_field_param` | `"chart_y_field"` |
| `chart_stack_by_single` | `"__single__"` |
| `group_by_field` | `"status"` |
| `chart_y_axis_value` | `"sum__amount"` |
| `value_field` | `"amount"` (or `None`) |
| `stack_dimension_choices` | `[("owner", "Owner"), ("source", "Source")]` |
| `stack_by_field` | `"owner"` or `None` |
| `chart_config_json` | JSON for EChartsConfig |
| `chart_type` | `"stacked_vertical"` |
| `chart_type_choices` | chart dropdown options |
| `chart_error` | localized error text or `None` |
| `chart_dom_id` | `"chart-view-leads-chart"` |
| `chart_export_filename` | `"leads-by-status"` |
| `chart_add_to_dashboard_url` | `"/dashboard/chart-view-to-dashboard/?module_id=...&grouping_field=status&chart_type=column"` |
| `chart_show_add_to_dashboard` | `True/False` |
| `chart_htmx_url` | base chart endpoint without chart-only params |
| `chart_push_url` | canonical main URL with `layout=chart` |
| `chart_push_url_json` | JSON-safe string or `"null"` |

---

## 🔄 HTMX URL behavior

- Dropdowns in `chart_view.html` call `hx-get="{{ chart_htmx_url }}"`.
- Selected values are included through `hx-include`.
- `render_to_response()` sets `HX-Push-Url` to `chart_push_url` on HTMX requests so browser URL becomes the canonical main page URL with `layout=chart`, not the chart endpoint itself.

---

## 🧪 Example subclass

```python
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator

from horilla.urls import reverse_lazy
from horilla.utils.decorators import htmx_required, permission_required_or_denied
from horilla_generics.views.chart import HorillaChartView
from horilla_crm.leads.models import Lead
from horilla_crm.leads.filters import LeadFilter


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(["leads.view_lead", "leads.view_own_lead"]),
    name="dispatch",
)
class LeadChartView(LoginRequiredMixin, HorillaChartView):
    model = Lead
    view_id = "leads-chart"
    filterset_class = LeadFilter

    # Main list/search endpoints used for drill-down + push URL
    search_url = reverse_lazy("leads:leads_list")
    main_url = reverse_lazy("leads:leads_view")

    # Optional field controls inherited from kanban/group-by conventions
    exclude_kanban_fields = "lead_owner"
    include_kanban_fields = None

    # Chart defaults
    default_chart_type = "column"
```

### Example request

```text
/leads/leads_chart/?chart_group_by=lead_status&chart_type=stacked_vertical&chart_stack_by=lead_source&chart_y_field=sum__annual_revenue
```

What happens:
- queryset is filtered by `LeadFilter` and any active query params
- grouped by `lead_status`
- stacked by `lead_source`
- y-axis aggregates `annual_revenue` using `SUM`
- template receives `chart_config_json`, and frontend renders through `EChartsConfig.getChartOption(config)`

---

## 🧩 Dimensions that aren't model columns

`build_chart_payload`, `build_stacked_payload` and `get_context_data` resolve the group-by and stack-by fields through `self.get_group_field(name)` (see [list.md](list.md#extension-hooks-for-fields-that-arent-model-columns)). An extension can add a Choice-style field to `get_chart_dimension_choices()`, annotate the queryset with its values and answer `get_group_field()`; drill-down URLs use the same field name in `apply_filter`.

---

## 📌 Summary

- `HorillaChartView` is the chart equivalent of `HorillaListView`.
- It keeps the same filtering/search semantics and builds chart payloads on top.
- Use `chart_group_by`, `chart_stack_by`, and `chart_y_field` query params to drive chart output.
- `chart_view.html` is fully HTMX-compatible and keeps URL state in sync via `chart_push_url`.
