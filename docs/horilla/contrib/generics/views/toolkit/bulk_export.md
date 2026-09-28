# Bulk export toolkit (`horilla_generics/views/toolkit/bulk_export.py`)

## Purpose

`HorillaBulkExportMixin` is the export engine used by generic list views to produce downloadable files from selected records.

It supports:

- `csv`
- `xlsx`
- `pdf`

and centralizes field resolution, value normalization, user-specific date/time formatting, and file response generation.

---

## Why this mixin exists

`HorillaListView` handles many responsibilities (querying, filtering, sorting, rendering, actions).
Export logic is heavy and format-specific, so this mixin isolates:

- parsing export payload (`record_ids`, `columns`, `export_format`)
- selecting exportable fields
- converting object values into display-ready strings
- writing bytes for each target format

This keeps list-view code smaller while preserving feature parity.

---

## Core

## `handle_bulk_export_post(self, record_ids, columns, export_format)`

Entrypoint called from list view POST handler.

Behavior contract:

- returns `None` when export is not requested (missing IDs or format)
- returns `HttpResponse` download on success
- returns error `HttpResponse` (400/500) on invalid payload or runtime failure

Internal steps:

1. validate minimal inputs (`record_ids` and `export_format`)
2. decode `record_ids` from JSON
3. delegate to `handle_export(...)`

If `record_ids` JSON is malformed:

- returns `400` with `"Invalid JSON data for record_ids"`.

---

## `handle_export(self, record_ids, columns, export_format)`

This is the full export pipeline.

High-level stages:

1. fetch target queryset
2. build candidate fields (`model_fields`)
3. compute final export columns
4. build matrix data row-by-row
5. serialize to requested format
6. return downloadable response

---

## Stage 1: Queryset and field catalog

### Queryset

```python
queryset = self.model.objects.filter(id__in=record_ids)
```

Important note: this method uses `self.model.objects` directly, not `self.get_queryset()`.
So selection scope should already be validated by caller/UI flow.

Rows are built by iterating `self.get_export_objects(queryset)` (default: the
queryset itself). Override via [`MixinExtension`](../../../../extension/mixin/inherit.md)
to materialize the queryset and attach in-memory attributes (e.g. Custom Fields
`CustomFieldBulkExportExtension`) instead of a global QuerySet monkey-patch.

### Base field list

`model_fields` begins with concrete model fields:

- tuple shape: `(verbose_label, field_name, field_object)`

Example:

- `("Lead Name", "name", <CharField>)`
- `("Created By", "created_by", <ForeignKey>)`

---

## Stage 2: Add property/callable export fields

The mixin optionally includes model properties/callables from `PROPERTY_LABELS`.

Flow:

1. read `property_labels = getattr(self.model, "PROPERTY_LABELS", None)`
2. for each `(name, label)`:
   - resolve member on model
   - include if property or callable
   - normalize `get_foo` to key `foo` for filtering
   - skip `histories` and `full_histories`
3. append to `model_fields` with marker `field=None`

This allows export of computed values without adding DB columns.

---

## Stage 3: Choice display-method augmentation

For each model field with `choices`, the mixin appends a synthetic export field:

- header: field verbose name
- accessor: `get_<field>_display`
- marker: `"method"`

Why:

- exported files should show human-readable labels instead of raw choice keys (e.g. `role`, `country` on `User`, via `get_<field>_display`).

---

## Stage 4: Column selection logic

The mixin resolves export columns from two sources:

- explicit `columns` argument (user-selected fields)
- fallback table columns from `self._get_columns()`

### Common exclusion rule

Always excludes:

- `histories`
- `full_histories`

### If `columns` provided

- keeps only requested columns minus excluded names
- derives `column_headers`/`selected_fields` from `model_fields`

### If `columns` not provided

- uses list table columns (`_get_columns`) as default export schema
- maps table field names to entries in `model_fields`
- if no table columns exist, returns `400` (`"No table columns defined for export"`)

This makes export schema align with visible list structure unless user overrides.

---

## Stage 5: Data extraction and normalization

For each object and selected field, the mixin applies layered value resolution.

## Resolution order (important)

1. try display method `get_<field_name>_display` on object
2. else `getattr(obj, field_name, "")`
3. if field marker is `"method"` or value callable: execute callable
4. if field marker is `None` (property/callable): execute if callable
5. if value contains HTML-like tags, strip with regex
6. type-specific conversions (`ForeignKey`, `ManyToManyField`)
7. datetime/date formatting with user preferences
8. fallback to string or empty value

### ForeignKey handling

If field object is `ForeignKey`:

- if related object has `username`, use that
- otherwise use `str(related_obj)`

### ManyToMany handling

If field object is `ManyToManyField`:

- join related objects with comma:
  - `"tag1, tag2, tag3"`

### HTML stripping

For property/callable outputs containing markup:

- strips tags using `re.sub(r"<[^>]+>", "", value)`

Goal: keep exports clean text (especially for rich-display properties).

---

## Stage 6: User-aware date and datetime formatting

The mixin reads user preferences from `self.request.user`.

### Datetime values

1. if user has `time_zone`, attempts conversion via `zoneinfo.ZoneInfo`
2. if datetime is naive, first makes it aware with default timezone
3. applies user format:
   - `user.date_time_format` or fallback `%Y-%m-%d %H:%M:%S`

### Date values

- uses `user.date_format` or fallback `%Y-%m-%d`

All formatting failures have safe fallback formats.

This is a critical UX detail: exported timestamps match user locale/settings, not raw DB UTC output.

---

## Output formats in detail

## CSV (`export_format == "csv"`)

Implementation:

- content-type: `text/csv`
- filename: `exported_<model_verbose_plural>.csv` (spaces -> `_`)
- writer: Python `csv.writer`
- first row: headers
- subsequent rows: normalized data

Best for:

- lightweight exports
- spreadsheet compatibility
- pipelines/integrations

---

## XLSX (`export_format == "xlsx"`)

Implementation uses `openpyxl`.

Workbook styling:

- bold header font
- centered header alignment
- yellow-ish header fill (`eafb5b`)
- fixed width per column (`25`)
- fixed row height (`15`)

Response:

- content-type: XLSX MIME
- bytes written from `BytesIO` buffer
- attachment filename `.xlsx`

Best for:

- richer tabular export with basic visual formatting.

---

## PDF (`export_format == "pdf"`)

Implementation uses `reportlab`.

Layout strategy:

- landscape page (`letter` rotated)
- centered title: `"Exported <Model Verbose Plural>"`
- paginates both:
  - rows (`max_rows_per_page = 7`)
  - columns (`max_cols_per_page = 6`)
- wraps header/data text to avoid overflow
- truncates long strings per cell segment

Key constants controlling layout:

- `start_x = 50`
- `start_y = height - 100`
- `min_col_width = 120`
- `extra_row_spacing = 10`

This branch is optimized for readability over density, not full spreadsheet-scale tabulation.

---

## HTTP response and filename behavior

Model-based filename stem:

```text
exported_<verbose_name_plural_lower_with_underscores>.<ext>
```

Examples:

- `Exported Leads` -> `exported_leads.csv`
- `Exported Sales Opportunities` -> `exported_sales_opportunities.pdf`

Document title (PDF metadata/title line):

- `Exported <Model Verbose Name Plural>`

---

## Error handling model

### Input errors

- invalid `record_ids` JSON => `400`
- invalid `export_format` => `400`
- missing table columns in fallback mode => `400`

### Runtime errors

- any exception in export pipeline => logs error and returns `500` with generic message

### Field-level extraction errors

When one field fails for one row:

- logs field-specific error
- inserts empty string for that cell
- continues export (does not fail whole file)

This fault-tolerance keeps exports usable even with occasional problematic properties.

---

## Security and scope considerations

`handle_export` filters by IDs directly on `self.model.objects`.
It does not independently enforce permission filtering via `get_queryset()`.

Practical implication:

- caller must ensure incoming IDs are already authorized/visible for current user.

In normal Horilla list flow this is generally true because selected IDs originate from rendered/filtered list rows.

---

## Extension points and customization strategy

If you need custom behavior, common override points are:

- `handle_bulk_export_post(...)` for payload validation/routing
- `handle_export(...)` for:
  - stricter queryset scoping (`self.get_queryset().filter(id__in=...)`)
  - custom field exclusion
  - custom format branch
  - localized header naming

Typical project-specific extensions:

- add JSON export branch
- custom value serializers per field type (currency, decimals)
- stronger HTML sanitization
- dynamic PDF page sizing

---

## Practical request payload examples

### Example 1: CSV export with default table columns

```text
POST /your-list-url/
record_ids=[4,8,15,16]
export_format=csv
```

Result:

- downloads CSV using table columns from `_get_columns()`.

### Example 2: XLSX export with user-selected columns

```text
POST /your-list-url/
record_ids=[4,8,15,16]
export_format=xlsx
columns=["name","email","status","created_at"]
```

Result:

- downloads XLSX with only requested columns (except excluded ones).

### Example 3: PDF export

```text
POST /your-list-url/
record_ids=[4,8,15,16]
export_format=pdf
columns=["name","owner","stage","source","created_at","next_action"]
```

Result:

- paginated landscape PDF table with wrapped text.

---

## End-to-end flow (operational view)

1. UI collects selected row IDs.
2. POST sends IDs + target format (+ optional selected columns).
3. mixin decodes IDs and resolves export fields.
4. mixin computes each cell value with type-aware normalization.
5. format serializer writes file bytes.
6. response returns attachment headers; browser downloads file.

---

## Caveats and implementation notes

- `ManyToManyField` check uses concrete model field info; if a projected callable returns M2M-like data, it is treated as generic value path.
- HTML stripping is regex-based and basic; complex HTML entities/structures are not fully sanitized.
- PDF generation uses fixed limits (`max_rows_per_page`, `max_cols_per_page`) that may require tuning for large schemas.
- Field ordering follows selected columns/table column order as resolved in this method.

---

## Summary

`bulk_export.py` is a full export subsystem that transforms selected model rows into CSV/XLSX/PDF with field-aware rendering, user-aware time formatting, and resilient fallback behavior. It is designed to be reusable by generic list views while remaining extensible for project-specific export requirements.
