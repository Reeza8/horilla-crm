# Field/template utility filters (`horilla_generics/templatetags/horilla_tags/field_filters.py`)
## Purpose
`field_filters.py` is the largest utility tag module in `horilla_tags`.
It bundles many small, reusable template helpers for:
- dynamic field lookup and display
- action button rendering
- dictionary/list/query helpers
- model metadata helpers
- form field rendering for dynamic condition rows
- permission value lookup helpers
It acts as a toolbox for many generic templates in Horilla.
---
## Architectural overview
The module has:
- one internal formatter helper (`_format_string`)
- multiple `@register.filter` utilities
- a few `@register.simple_tag` helpers for richer HTML output and dynamic field rendering
Common integrations:
- `_shared` helpers for date/time + FK display
- Horilla HTML safety utilities from `horilla.utils.html` (`format_html`, `escape`; `mark_safe` remains from Django when needed)
- model metadata introspection (`_meta`)
---
## Core internal helper
## `_format_string(string, instance)`
Replaces placeholders like `{field}` or `{rel__name}` using object attributes.
Behavior:
- finds `{...}` tokens via regex
- traverses nested attributes by `__`
- executes callables when encountered
- converts values to string
- applies Python `str.format(**context)`
Used by action/button helper to interpolate object values into attribute templates.
---
## Group 1: Field value retrieval/display
## `get_field(obj, field_path)`
General-purpose nested accessor with formatting behavior.
Supports:
- `__` path traversal
- callable values
- `Manager/QuerySet` path segments (uses `.first()`)
- currency display for model-declared `CURRENCY_FIELDS`
- date/time formatting via `_shared.format_datetime_value(..., convert_timezone=False)`
- boolean localization (`Yes`/`No`)
- choice display via `get_<field>_display()`
Returns empty string on errors.
Usage:
```django
{{ obj|get_field:"employee__department__name" }}
```
---
## `get_field_value(obj, field_name)`
Type-aware display helper for direct model fields.
Formatting rules:
- M2M -> comma-joined labels
- FK -> related object string
- choices -> choice label (`get_FOO_display` if available)
- boolean -> `Yes` / `No` / empty
- datetime -> `%Y-%m-%d %H:%M`
- date -> `%Y-%m-%d`
- decimal -> `"{:.2f}"`
- fallback -> string conversion
---
## `get_field_display_value(obj, field_name)`
Alias for `get_field_value` (backward compatibility).
---
## `get_field_display(obj, field_name)` (simple_tag)
Another display helper focused on readonly rendering:
- choice labels
- FK via `display_fk(...)`
- datetime `%d/%m/%Y %H:%M`
- date `%d/%m/%Y`
- fallback string
Useful where day-first formatting is desired in readonly contexts.
---
## Group 2: Generic dictionary/list/query helpers
- `get_item(dictionary, key)` -> dictionary lookup using stringified key
- `get_item_form(dictionary, key)` -> strict dict lookup
- `lookup(dictionary, key)` -> returns value or `{}` default
- `join_comma(value)` -> join list with commas
- `get_steps(dictionary, key)` -> reads `step<key>` title
- `has_value(query_dict, key)` -> boolean non-empty check
- `get_range(value)` -> `range(1, value+1)`
- `json(value)` -> `json.dumps(...)`
- `to_json(value)` -> `json.dumps(..., ensure_ascii=False)`
- `getter(obj, attr)` / `getattribute(obj, attr)` -> safe attr access
- `get_user_pk(obj)` -> returns `obj.pk` or value
- `wrap_in_list(value)` -> dict -> `[dict]` helper for permission tag reuse
These utilities reduce template complexity for common manipulations.
---
## Group 3: Form/step helpers
## `get_fields_for_step(form, step)`
Returns fields for multi-step form rendering.
Resolution:
1. if form has `get_fields_for_step(step)` -> use it
2. elif form has `step_fields[step]` -> map names to bound fields
3. else -> `form.visible_fields()`
Validates form instance (`BaseForm`) first.
---
## `render_field_with_name(context, form, field_name, row_id=None, selected_value=None)` (simple_tag, takes context)
Advanced renderer for dynamic condition rows.
Key behaviors:
- for `value` field with row id:
  - prefers pre-rendered HTML from context key `value_widget_html_<row_id>`
  - fallback to default text input when field missing
- for real form fields:
  - rewrites `name` to `<field>_<row_id>`
  - rewrites `id` to `id_<field>_<row_id>`
  - applies `selected` option for selects when `selected_value` provided
  - injects value attribute for inputs
- returns safe HTML
This is central to condition-row dynamic UIs where each row needs unique input names.
---
## Group 4: Action/button rendering helpers
## `render_action_button(action, obj)`
Builds action button HTML from action config.
Supports three modes:
1. image action (`src`)
2. icon action (`icon`)
3. text/class fallback
Important details:
- interpolates action attrs with `_format_string(...)`
- translates tooltip text
- uses `format_html` (from `horilla.utils.html`) + escaping for safety
- retains flexible attrs payload via `mark_safe(attrs)`
Designed for reusable action-cell rendering in list tables.
---
## Group 5: Model metadata / naming helpers
- `get_class_name(instance)` -> full class path (`module.Class`)
- `model_name(obj)` -> class name
- `model_verbose_name(obj)` -> `_meta.verbose_name`
- `model_verbose_name_plural(obj)` -> `_meta.verbose_name_plural`
- `verbose_name(obj, field_name)` -> field verbose name or humanized fallback
- `humanize_field_name(value)` -> `"first_name"` -> `"First Name"`
- `sanitize_id(value)` -> HTML id-safe slug-like token
These are used for dynamic headers, labels, IDs, and metadata display.
---
## Group 6: Related object/list helpers
- `get_related_objects(obj, field_name)` -> returns related manager `.all()` or empty list
- `join_attr(manager_or_queryset, attr_name)` -> joins attribute from all related objects
Example:
```django
{{ instance.department_set|join_attr:"department_name" }}
```
---
## Group 7: Related-list URL/action helpers
- `can_add_related(related_list, obj)` -> reads `related_list["can_add"]` default `True`
- `get_add_url(obj, related_list)`:
  - resolves named URL when possible
  - appends query `?<model_name>=<pk>`
- `get_view_all_url(obj, related_list)`:
  - same pattern for "view all" links
These support related-list cards/actions in detail templates.
---
## Group 8: Misc helpers
- `is_image_file(filename)` -> checks common image extensions
- `get_field_permission(field_permissions, field_name)` -> returns permission string or `readwrite`
- `get_field_verbose_name(component_or_condition, model_name_or_field_name)`:
  - resolves verbose name via dynamic model lookup
  - falls back to humanized field name on errors
  - currently uses placeholder app label `"your_app_name"` in lookup logic (important caveat)
---
## Safety and escaping model
The module mixes strong escaping with controlled safe output:
- `format_html` and `escape` (from `horilla.utils.html`) used for structured HTML generation
- `mark_safe` used where prebuilt attrs/HTML fragments are intentionally trusted
When reusing helpers, ensure upstream strings passed into safe channels are controlled.
---
## Practical template examples
### Nested field display
```django
{{ employee|get_field:"department__manager__full_name" }}
```
### Render dynamic action button
```django
{{ action|render_action_button:obj }}
```
### Step fields loop
```django
{% for field in form|get_fields_for_step:current_step %}
  {{ field }}
{% endfor %}
```
### Render condition-row input with row-scoped name/id
```django
{% render_field_with_name form "value" row_id selected_value %}
```
---
## Caveats and implementation notes
- many filters catch broad exceptions and return empty/fallback values to avoid template crashes.
- there is overlap among display helpers (`get_field`, `get_field_value`, `get_field_display`); choose one consistently per UI context.
- `json` and `to_json` differ mainly by `ensure_ascii`; use `to_json` for unicode-friendly output.
- `get_field_verbose_name` relies on hardcoded app placeholder in lookup path; likely intended for project-specific override/fix.
- `render_field_with_name` performs regex/string HTML rewrites; ensure generated form widgets follow expected markup patterns.
---
## Summary
`field_filters.py` is the multi-purpose template helper toolbox for Horilla generic UIs. It provides nested field access, type-aware display formatting, dynamic form-row rendering, action button HTML generation, and metadata helpers, enabling highly dynamic templates with minimal inline logic.
