# Split view (`horilla_generics/views/split_view.py`)

## Purpose

`HorillaSplitView` provides a two-panel layout:

- **left panel**: tile list (same queryset/filter/sort pipeline as `HorillaListView`)
- **right panel**: detail fragment loaded via HTMX when a tile is clicked

It is designed to reuse list logic while giving faster record browsing without full-page navigation.

---

## Class: `HorillaSplitView`

```python
class HorillaSplitView(HorillaListView):
```

Defaults tuned for split UI:

| Attribute | Default | Why |
|-----------|---------|-----|
| `template_name` | `split_view.html` | Split wrapper template. |
| `list_column_visibility` | `False` | Always use explicit split columns, not per-user list visibility config. |
| `bulk_select_option` | `False` | No checkbox selection in tile mode. |
| `table_class` | `False` | Simpler tile/table styling. |
| `table_width` | `False` | Flexible panel fit. |
| `paginate_by` | `50` | Left tile list page size. |
| `split_detail_target` | `#splitViewDetailPanel` | HTMX target for right panel detail content. |
| `split_layout_param` | `layout=split` | Query param that asks detail view for fragment template. |

---

## How it works

### 1) Reuses list pipeline

Because it inherits `HorillaListView`, split view gets:

- filterset filtering
- quick filters
- sorting
- owner filtration
- pagination

No duplicate queryset code is required unless subclass adds domain constraints.

### 2) Prepares tile navigation metadata

In `get_context_data`:

- each object gets:
  - `split_next_id`
  - `split_prev_id`

These are injected into tile links so right-panel detail can support next/prev navigation in current filtered scope.

### 3) Auto-loads first detail

If queryset is non-empty:

- checks first object for:
  - `get_detail_url()` (preferred), else
  - `get_detail_view_url()`
- builds `split_first_detail_url` with:
  - `layout=split`
  - optional `section` and `view_type`

`split_view.html` uses this URL with `hx-trigger="load"` to populate right panel automatically.

### 4) Injects split-specific `col_attrs`

`_get_split_col_attrs()` builds first-column attrs:

- `hx-get`: `{get_detail_url}?layout=split&next_id=...&prev_id=...`
- `hx-target`: right panel
- `hx-swap`: `innerHTML`
- permission keys from subclass:
  - `split_view_permission`
  - `split_view_own_permission`
  - `split_view_owner_field`

So tile clicks fetch only the detail fragment, not whole page content.

---

## `_get_split_col_attrs` detail

Placeholder selection:

- uses `{get_detail_url}` when model provides `get_detail_url`
- falls back to `{get_detail_view_url}`
- logs warning if neither exists

Query propagation:

- carries `section` and `view_type` from current request
- always appends `layout=split`
- appends `next_id` / `prev_id` from per-object attributes

This keeps right panel context aligned with left panel filters and navigation state.

---

## Render behavior (`render_to_response`)

`HorillaSplitView` handles HTMX differently than standard list view:

- HTMX + `page` param -> renders only `partials/split_view_tiles.html` (infinite/load-more tile fetch)
- HTMX without `page` -> renders full `split_view.html`
- non-HTMX -> falls back to parent non-HTMX response path

This enables efficient tile pagination without re-rendering the right panel.

---

## Template contract

### `split_view.html`

Responsibilities:

- wrapper + filter panel + quick filters
- left tile container (`split-view-tiles`) includes `partials/split_view_tiles.html`
- right detail panel (`#splitViewDetailPanel`)
  - auto-loads `split_first_detail_url` on first render if available
- no-record state with optional add button

### `partials/split_view_tiles.html`

Renders tile rows/cards using `columns`, `col_attrs`, and pagination metadata from context.

---

## Required model capabilities

For best split behavior, each row object should expose one of:

- `get_detail_url()`
- `get_detail_view_url()`

And the target detail view should support:

- `?layout=split` returning a fragment (e.g., `HorillaDetailView.get_template_names` supports this).

---

## Example 1: Lead split view (real pattern)

```python
@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(["leads.view_lead", "leads.view_own_lead"]),
    name="dispatch",
)
class LeadSplitView(LoginRequiredMixin, HorillaSplitView):
    model = Lead
    view_id = "leads-split"
    filterset_class = LeadFilter
    search_url = reverse_lazy("leads:leads_list")
    main_url = reverse_lazy("leads:leads_view")
    enable_quick_filters = True
    split_view_permission = "leads.view_lead"
    split_view_own_permission = "leads.view_own_lead"
    split_view_owner_field = "lead_owner"
    columns = ["title", "lead_status"]
    no_record_add_button = LeadListView.no_record_add_button
    actions = LeadListView.actions

    def get_queryset(self):
        queryset = super().get_queryset()
        view_type = self.request.GET.get("view_type") or self.get_default_view_type()
        if view_type == "converted_lead":
            queryset = queryset.filter(is_convert=True)
            self.actions = None
            self.no_record_add_button = False
            self.bulk_update_option = False
        else:
            queryset = queryset.filter(is_convert=False)
        return queryset
```

Route:

```python
path("leads-layout-split/", views.LeadSplitView.as_view(), name="leads_split_view")
```

---

## Example 2: Opportunity split view (minimal)

```python
class OpportunitySplitView(LoginRequiredMixin, HorillaSplitView):
    model = Opportunity
    view_id = "opportunity-split"
    filterset_class = OpportunityFilter
    search_url = reverse_lazy("opportunities:opportunities_list")
    main_url = reverse_lazy("opportunities:opportunities_view")
    split_view_permission = "opportunities.view_opportunity"
    split_view_own_permission = "opportunities.view_own_opportunity"
    split_view_owner_field = "owner"
    columns = ["name", "amount"]
    no_record_add_button = OpportunityListView.no_record_add_button
```

Route:

```python
path(
    "opportunities-layout-split/",
    views.OpportunitySplitView.as_view(),
    name="opportunities_split_view",
)
```

---

## Example 3: Custom target/param override

Use this when your right panel container ID differs:

```python
class TicketSplitView(HorillaSplitView):
    model = Ticket
    split_detail_target = "#ticketDetailPane"
    split_layout_param = "layout=split&from=tickets"
    columns = ["subject", "status"]
```

Make sure your template has `id="ticketDetailPane"` and your detail view understands the custom query params.

---

## Add Column to Split View

The split panel's fields are per user, the same idea as the detail field
selector. `SplitColumnSelectorView` (`views/helpers/detail_field.py`, template
`add_column_to_split.html`) adds, removes and reorders the fields shown in the
right-hand panel. The navbar action is **Add Column to Split View**.

A missing `app_label` or `model_name` returns no model (the selector does not
guess). Selectable fields follow the detail view's excludes
(`base_excluded_fields`, `excluded_fields`, `split_excluded_fields`,
`pipeline_field`) and drop fields the user cannot see. Custom fields (`cf_*`)
are appended when Field Management is installed.

---

## Common subclass customization patterns

### Pattern A: share list behavior

Reuse list settings:

- `actions = SomeListView.actions`
- `no_record_add_button = SomeListView.no_record_add_button`
- same `filterset_class`

### Pattern B: reduce split columns

Use 1-3 concise columns for fast scanning in left panel.

### Pattern C: custom queryset by view type

Override `get_queryset` but start with `super().get_queryset()` to keep base filters/permissions.

### Pattern D: explicit split permissions

Set `split_view_permission`, `split_view_own_permission`, `split_view_owner_field` so tile click behavior respects ownership policy.

---

## Troubleshooting

- **Right panel not loading**: model likely lacks `get_detail_url` and `get_detail_view_url`.
- **Full page detail loads instead of fragment**: detail view may not honor `layout=split`.
- **Tile click forbidden unexpectedly**: verify `split_view_*` permission attributes and owner field name.
- **Filter state lost in right panel**: ensure `section`/`view_type` propagation remains in request and not stripped in custom attrs.

---

## Summary

`HorillaSplitView` is a thin but powerful adapter over `HorillaListView`: it keeps list filtering/sorting/permissions intact while converting first-column interactions into HTMX detail-panel loads. Most implementation effort in subclasses is just choosing columns, permissions, and any domain-specific queryset tweaks.
