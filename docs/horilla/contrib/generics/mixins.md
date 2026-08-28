# Generic mixins (`horilla_generics/mixins.py`)
## Purpose
`horilla_generics/mixins.py` contains reusable mixins used by list/detail-style generic views.
Main areas covered:
- recently viewed tracking
- list column resolution + persistence + caching
- filter field metadata generation (for dynamic filter UI and bulk-update/export support)
- filter remove/clear handlers
- one composite list-view mixin that combines all list helpers
---
## Module structure
Key classes:
- `RecentlyViewedMixin`
- `HorillaListColumnMixin`
- `HorillaListFilterFieldsMixin`
- `HorillaListFilterHandlersMixin`
- `HorillaListViewMixin` (composed mixin)
Also uses shared utilities/models:
- `ListColumnVisibility` (per-user saved column choices)
- `RecentlyViewed` (viewed history)
- `filter_hidden_fields(...)` (field-level visibility enforcement)
- `get_allowed_users_queryset_for_model(...)` (safe user list for FK choices)
---
## `RecentlyViewedMixin`
Simple post-dispatch tracker for authenticated users.
Flow:
1. call `super().dispatch(...)`,
2. if view has `self.object` and user is authenticated,
3. record item via:
   - `RecentlyViewed.objects.add_viewed_item(request.user, self.object)`
Use case:
- detail-like views that resolve a concrete object and want automatic recent-history logging.
---
## `HorillaListColumnMixin`
Handles all list-column determination logic, including:
- company column toggle by session flag,
- hidden-field filtering by permission,
- cache-first column retrieval,
- fallback to DB persisted visibility,
- fallback to configured `self.columns`,
- final fallback to auto model field detection.
### `_add_company_column_if_needed(columns)`
Reads:
- `request.session["show_all_companies"]`
Behavior:
- when false: removes `company`/`company__name` columns
- when true: appends company column if model has `company` field and it is not already present
This supports multi-company list UX without duplicating logic in each view.
---
### `_get_columns()` full resolution order
1. **Column-visibility feature off** (`self.list_column_visibility=False`)
   - start from `self.columns`
   - filter with `filter_hidden_fields(...)`
   - apply company-column logic
2. **Cache hit path**
   - cache key includes user/model/context/url-name
   - sanitize cached shape
   - re-apply hidden-field filtering
   - apply company-column logic
3. **Persisted visibility path** (`ListColumnVisibility`)
   - load saved `visible_fields`
   - rebuild `[verbose, field]` structure
   - support legacy/variant formats
   - apply hidden-field filtering
   - apply company-column logic
   - cache result
4. **Configured columns initialization path** (`self.columns`)
   - normalize to serializable `[label, key]` with English translation override
   - apply hidden-field filtering
   - create initial `ListColumnVisibility` row
   - apply company-column logic
   - cache result
5. **Auto model fields fallback**
   - include model fields except `id`, auto-created, and `self.exclude_columns`
   - apply hidden-field filtering
   - apply company-column logic
### Context key strategy for visibility rows
Context is derived from referrer path (`HTTP_REFERER`) and current resolved URL name.
This lets the same model have different saved column sets per page context.
---
## `HorillaListFilterFieldsMixin`
Provides:
- `_get_model_fields(...)`
- `handle_field_change(...)`
- `handle_operator_change(...)`
Used to power dynamic filter row UI (field/operator/value widgets), bulk update forms, and export metadata.
### `_get_model_fields(include_properties=False, for_export=False)`
Returns a metadata list for model fields with type + choices + operators.
Per field metadata example:
```python
{
  "name": "owner",
  "type": "foreignkey",
  "verbose_name": "Owner",
  "choices": [{"value": "1", "label": "Admin"}],
  "operators": [...],
  "model": "User",
  "app_label": "auth",
}
```
#### Important behaviors
- caches result on `self` (`_model_fields_cache_<flags>`)
- excludes filterset `Meta.exclude` fields (non-export path)
- excludes `histories`/`full_histories` in export mode (+ optional `self.export_exclude`)
- maps field classes to generic types using `FIELD_TYPE_MAP`
- boolean fields receive Yes/No choices
- foreign key choices are built carefully:
  - user fields use `get_allowed_users_queryset_for_model(...)`
  - filterset-aware queryset if available
  - otherwise related model `.objects.all()`
  - paginated 10 choices by default
  - full static choices for specific bulk-update user-field trigger path
  - ensures currently selected value is included even if not in first page
- operator options come from `filterset_class.get_operators_for_field(...)`
- optional property/callable fields are appended when `include_properties=True` and model declares `PROPERTY_LABELS`
This method is a central metadata provider for multiple UI features.
---
### `handle_field_change(request, field_name, row_id)`
When field changes in filter UI:
- resolves field metadata from `_get_model_fields()`
- computes valid operators for field type
- renders `partials/operator_select.html`
Returns 404 if field is unknown.
### `handle_operator_change(request, field_name, operator, row_id)`
When operator changes:
- resolves field metadata,
- includes `filter_class_path` + `parent_model_path` when filterset exists,
- renders `partials/value_field.html` (value widget fragment)
Returns 404 for unknown fields.
---
## `HorillaListFilterHandlersMixin`
Implements query-param manipulation for:
- removing one filter/search token
- clearing all filters
### `handle_remove_filter(request)`
Supports two remove modes:
- remove search (`remove_filter=search`)
- remove one indexed filter row (`remove_filter=<index>`)
Flow:
1. read current query params,
2. rebuild field/operator/value/start/end arrays excluding target entry,
3. preserve unrelated params,
4. rebuild URL with updated params,
5. response behavior:
   - HTMX request -> `HX-Redirect`
   - non-HTMX -> normal redirect
This keeps URL state canonical after removing a filter row.
---
### `handle_clear_all_filters(request)`
Removes all filtering/search keys while preserving non-filter params.
Flow:
1. build cleaned `QueryDict` without filter keys,
2. temporarily patch `request.GET` and `QUERY_STRING`,
3. recompute list queryset/context,
4. render current template with clean context,
5. restore original request state,
6. set URL-push headers:
   - `HX-Push-Url` / `HX-Replace-Url` when enabled
   - `HX-Push-Url=false` otherwise
7. set no-cache response headers.
This branch re-renders content directly (not redirect), optimized for HTMX partial updates.
---
## `HorillaListViewMixin`
Composite mixin:
- `HorillaListColumnMixin`
- `HorillaListFilterFieldsMixin`
- `HorillaListFilterHandlersMixin`
Used by `HorillaListView` as one integration surface for column + filter UI behavior.
---
## Child class usage examples
### Example 1: basic list with custom columns
```python
from horilla_generics.mixins import HorillaListViewMixin
from horilla.views.generic import ListView
from leads.models import Lead
class LeadListView(HorillaListViewMixin, ListView):
    model = Lead
    columns = [["Name", "name"], ["Stage", "stage"], ["Owner", "owner"]]
    exclude_columns = ["internal_notes"]
    list_column_visibility = True
```
### Example 2: disable per-user column persistence
```python
class LeadListView(HorillaListViewMixin, ListView):
    model = Lead
    columns = [["Name", "name"], ["Email", "email"]]
    list_column_visibility = False
```
### Example 3: recently viewed support on detail view
```python
from horilla_generics.mixins import RecentlyViewedMixin
from horilla.views.generic import DetailView
class LeadDetailView(RecentlyViewedMixin, DetailView):
    model = Lead
```
---
## Operational caveats
- `_get_columns` caches per computed context; if context derivation differs from expectation (referrer/path), users may see different saved sets.
- `handle_clear_all_filters` mutates request GET temporarily; safe in request scope but important to keep restore logic intact.
- `_get_model_fields` has multiple trigger-sensitive branches (bulk update/operator/filter form); behavior differs by request headers/params.
- property-field inclusion depends on `PROPERTY_LABELS`; undocumented callables won’t appear.
---
## Summary
`horilla_generics/mixins.py` is the infrastructure layer for list UX in Horilla generics. It unifies per-user column persistence, field-aware filter metadata generation, dynamic filter fragment handlers, and filter-state URL management, while also providing a reusable recently-viewed tracking mixin for object views.
