# Group-by view (`horilla_generics/views/groupby.py`)

## Purpose

`HorillaGroupByView` is the generic grouped-list view used for HTMX list pages where rows are split into collapsible sections by one field.

It extends `HorillaListView` and adds:

- per-user group field preference via `KanbanGroupBy` (`view_type="group_by"`);
- permission-aware fallback when the preferred group field is hidden;
- grouping for **choice fields** and **foreign keys**;
- per-group pagination with "load more" AJAX rows;
- integration with `group_by_view.html` and `partials/group_by_load_more_rows.html`.

---

## Class: `HorillaGroupByView`

Decorators and base:

- `@method_decorator(htmx_required, name="dispatch")`
- `class HorillaGroupByView(HorillaListView)`

### Key attributes

| Attribute | Default | Meaning |
|-----------|---------|---------|
| `template_name` | `group_by_view.html` | Main grouped layout template. |
| `group_by_field` | `None` | Fallback group field if no saved user preference. |
| `filterset_module` | `filters` | Inherited filtering convention from list view setup. |
| `bulk_select_option` | `False` | Group tables do not show bulk checkbox by default. |
| `table_class` | `True` | Uses styled table header classes in template. |
| `table_height_as_class` | `h-[calc(_100vh_-_320px_)]` | Scroll height for each group table body. |
| `paginate_by` | `20` | Rows per group page. |

### Registry for load-more routing

`__init_subclass__` auto-registers each subclass by model into:

- `HorillaGroupByView._view_registry[model] = subclass`

This is used by `GroupByLoadMoreView` helper to instantiate the right group-by subclass from URL `app_label/model_name`.

---

## Group field selection flow

### 1) Allowed field list

`_get_allowed_group_by_fields()` asks `KanbanGroupBy.get_model_groupby_fields(...)` using optional class attrs:

- `exclude_kanban_fields` (CSV string)
- `include_kanban_fields` (list/iterable)

It returns only field names that can appear in settings for this view.

### 2) Visibility check

`_is_field_visible_for_group_by(field_name)` uses:

- `get_user_field_permission(user, model, field_name) != "hidden"`

So hidden fields are never used for grouping.

### 3) Effective field (`get_group_by_field`)

Priority:

1. user preference from `KanbanGroupBy` (`view_type="group_by"`);
2. class fallback `self.group_by_field`;
3. first allowed+visible field.

If none are visible/allowed, returns `None` and the UI shows an error in context.

---

## Building grouped context (`get_context_data`)

High-level behavior:

1. Resolve queryset (`self.object_list` or `get_queryset()`).
2. Resolve effective group field.
3. Validate field type: must be a **choice field** or **ForeignKey**.
4. Build ordered groups with per-group paginator.
5. Add grouped metadata used by templates.

### ChoiceField grouping

- Initializes groups from declared `field.choices` (preserves defined order).
- Adds dynamic `Unknown (<value>)` groups for values present in DB but not in choices.
- Each group includes:
  - `label`
  - `items` (current page row set)
  - `total_count`
  - `has_next` / `next_page`
  - `load_more_url` (`horilla_generics:group_by_load_more` with query params)
  - `data_container_id` (`{view_id}-{slugified_group_key}`)

### ForeignKey grouping

- Prefetches FK field.
- Builds groups from related model rows:
  - order by `order` when that field exists on the related model,
  - else order by `pk`.
- Adds `None` group when FK is nullable and null rows exist.
- Per-group pagination metadata is built the same as choice mode.

### Context keys

| Key | Meaning |
|-----|---------|
| `grouped_items` | Ordered dict-like mapping for template sections. |
| `group_by_field` | Field name currently used for grouping. |
| `group_by_label` | Field verbose name for header text. |
| `queryset` | Base queryset for current request. |
| `total_records_count` | Total row count before group page slicing. |
| `error` | User-facing error string when grouping fails or invalid field. |

---

## Load more endpoint (`load_more_items`)

Used by helper route:

- `horilla_generics:group_by_load_more`
- URL: `group-by-load-more/<str:app_label>/<str:model_name>/`

Required GET params:

- `group_key` (choice value, FK id, or `"None"`)
- `page`

Flow:

1. Resolve current group field with `get_group_by_field()`.
2. Cast `group_key` to correct type (`None` / `int` for FK).
3. Re-run filtered queryset via `get_queryset()`.
4. Slice requested group page with `Paginator`.
5. Render rows only:
   - template: `partials/group_by_load_more_rows.html`
   - returns HTML fragment (`tr` rows and optional load-more row).

On invalid params: `400`; on exhausted pages: empty response; on exception: `500` and logged error.

---

## Response behavior (`render_to_response`)

- Adds `request_params` to context.
- For HTMX requests (`HX-Request: true`) renders `group_by_view.html` directly with `render(...)`.
- Otherwise falls back to parent `HorillaListView` response behavior.

---

## Templates used

- `horilla_generics/templates/group_by_view.html`
- `horilla_generics/templates/partials/group_by_load_more_rows.html`
- plus shared list partials included by group template (`partials/list_view_rows.html`, filter panel, quick filters, etc.).

---

## Real subclass example (Leads)

```python
@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(["leads.view_lead", "leads.view_own_lead"]),
    name="dispatch",
)
class LeadGroupByView(LoginRequiredMixin, HorillaGroupByView):
    model = Lead
    view_id = "leads-group-by"
    filterset_class = LeadFilter
    search_url = reverse_lazy("leads:leads_list")
    main_url = reverse_lazy("leads:leads_view")
    group_by_field = "lead_status"
    exclude_kanban_fields = "lead_owner"
    columns = ["first_name", "last_name", "title", "email", "lead_status"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # When group_by == lead_status: one bulk LeadStatus.is_final query,
        # drop those keys from grouped_items (CRM-only; not in HorillaGroupByView)
        return context
```

When grouping by `lead_status`, **`LeadGroupByView`** drops final stages (`LeadStatus.is_final=True`) with a **single** `filter(pk__in=..., is_final=True)` instead of per-key `get()`. Kanban uses the same product rule via **`related_obj`** on each column — see [kanban.md](kanban.md#related_obj-generic-contract) and [lead stages](../../../../horilla_crm/leads/lead_stages.md#kanban--detail-pipeline).

Route in `leads/urls.py`:

```python
path("leads-group-by/", views.LeadGroupByView.as_view(), name="leads_group_by")
```

When a group has more than `paginate_by` rows, the generated load-more URLs call:

```text
/horilla-generics/group-by-load-more/leads/Lead/?group_key=<...>&page=<...>
```

and the helper `GroupByLoadMoreView` resolves model + subclass from `_view_registry` and delegates to `load_more_items`.

---

## Notes

- Grouping is intentionally limited to **choice/FK** fields for predictable section labels.
- Hidden field permissions are enforced for group-by selection, preventing accidental exposure via saved preferences.
- This view shares "group-by preference" storage with Kanban infrastructure (`KanbanGroupBy`) but isolates it using `view_type="group_by"`.
