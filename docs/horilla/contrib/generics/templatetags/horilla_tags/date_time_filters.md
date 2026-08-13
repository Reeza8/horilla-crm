# Date/time template filters (`horilla_generics/templatetags/horilla_tags/datetime_filters.py`)
## Purpose
`datetime_filters.py` provides template filters that format date/time values according to:
- current request user preferences (first priority),
- active company preferences (fallback),
- safe default formats (final fallback).
It ensures date/time display is consistent with user settings across templates, including history/audit values.
---
## Provided filters
This module registers two filters:
- `user_datetime_format`
- `user_datetime_format_display`
Both rely on shared helpers from `_shared.py`:
- `_get_request_user_company()`
- `format_datetime_value(...)` — delegates to composed `DateTimeFormatter` ([datetime.md](../../formatting/datetime.md), [`_inherit_formatter`](../../../../extension/formatting/inherit.md))
---
## `user_datetime_format`
Usage:
```django
{{ value|user_datetime_format }}
```
Behavior:
1. gets `(request, user, company)` from thread-local context helper,
2. calls:
   - `format_datetime_value(value, user=user, company=company, convert_timezone=True)`
3. if formatter returns non-`None`, returns formatted string,
4. otherwise returns original value unchanged.
Best for:
- normal model fields (`date`, `datetime`, `time`) rendered in templates.
---
## `user_datetime_format_display`
Usage:
```django
{{ value|user_datetime_format_display }}
```
Purpose:
- same as `user_datetime_format`, plus support for preformatted string values (common in audit/history logs).
Primary path:
- tries `format_datetime_value(...)` directly first.
Fallback string-parse path:
1. if value is a non-empty string and not placeholder (`"--"`, `"None"`, `"none"`),
2. parse with `dateutil.parser.parse(...)`,
3. if parsed datetime is naive:
   - make aware using Django default timezone,
4. re-format through `format_datetime_value(...)` with timezone conversion enabled,
5. on parse failures (`ValueError`, `TypeError`, `OverflowError`), silently keep original string.
Best for:
- history/change-display sections where datetime values may already be stringified.
---
## Timezone and format behavior
Because both filters call `format_datetime_value(..., convert_timezone=True)`, they inherit shared rules:
- timezone source priority:
  1. `user.time_zone`
  2. `company.time_zone`
- datetime format priority:
  1. `user.date_time_format`
  2. `company.date_time_format`
  3. `%Y-%m-%d %H:%M:%S`
- date format priority:
  1. `user.date_format`
  2. `company.date_format`
  3. `%Y-%m-%d`
- time format priority:
  1. `user.time_format`
  2. `company.time_format`
  3. `%I:%M:%S %p`
Calendar extensions override `DateTimeFormatter.format_*` / `parse_*` rather than these filters.
---
## Difference between the two filters
- `user_datetime_format`:
  - formats native date/time objects; non-date values pass through unchanged.
- `user_datetime_format_display`:
  - same native behavior,
  - additionally attempts to parse and normalize date-like strings before pass-through.
Use `user_datetime_format_display` when input may already be a human string from logs/history payloads.
---
## Template examples
### Standard object field
```django
{{ employee.joining_date|user_datetime_format }}
{{ activity.created_at|user_datetime_format }}
```
### Audit/history value rendering
```django
{{ change.new_value|user_datetime_format_display }}
```
### Safe fallback behavior
If value is not parseable/formatable date-time:
```django
{{ value|user_datetime_format_display }}
```
returns original value as-is, avoiding template errors.
---
## Error handling and resilience
- formatter and parser failures are swallowed intentionally,
- filter returns original value when formatting cannot be applied,
- this prioritizes robust template rendering over strict conversion.
---
## Caveats
- relies on thread-local request middleware; without request context, only explicit value formatting behavior applies.
- string parsing is permissive (`dateutil`), so ambiguous date strings can parse unexpectedly depending on content.
- placeholder strings (`"--"`, `"None"`, `"none"`) are intentionally not parsed.
---
## Summary
`datetime_filters.py` provides user/company-aware date/time template filters with timezone conversion and robust fallbacks. `user_datetime_format` is for native date/time values, while `user_datetime_format_display` adds parsing support for preformatted strings commonly found in history/audit displays.
