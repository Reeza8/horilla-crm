# Shared template-tag helpers (`horilla_generics/templatetags/horilla_tags/_shared.py`)
## Purpose
`_shared.py` provides common utility functions used by multiple `horilla_tags` modules.
It intentionally **does not** define template tags directly and does not use `register`.
Instead, it centralizes reusable formatting and context helpers to avoid duplication across:
- `datetime_filters.py`
- `display_tags.py`
- `field_filters.py`
---
## Why this module exists
Many tag/filter modules need consistent date/time formatting and context fallback behavior (user/company/timezone).
If each module implemented this independently, behavior would drift over time.
`_shared.py` gives one canonical implementation for:
- resolving request/user/company context from thread-local
- formatting date/datetime/time values with preference fallback (via composed `DateTimeFormatter`)
- consistent FK display conversion
---
## Function reference
## `_get_request_user_company()`
Returns:
- `request`
- authenticated `user` (or `None`)
- active `company` (or fallback `user.company`, else `None`)
Source:
- thread-local request: `horilla_utils.middlewares._thread_local`
Resolution order for company:
1. `request.active_company`
2. `user.company` (if user exists)
Used by tag filters that need formatting preferences without explicitly receiving user/company in every call.
---
## `format_datetime_value(value, user=None, company=None, convert_timezone=True)`
Delegates to the composed `DateTimeFormatter` (Gregorian by default; Jalali or other calendars when an extension registers `_inherit_formatter`).

```python
from horilla.extension.formatting import get_datetime_formatter

return get_datetime_formatter().format(
    value, user=user, company=company, convert_timezone=convert_timezone
)
```

See [DateTimeFormatter](../../formatting/datetime.md) for timezone conversion, format/parse hooks, and override points. Template filters do not implement calendar logic themselves.
---
## `display_fk(value)`
Returns string representation of FK-like object:
- if object has `__str__`: `str(value)`
- else returns raw value
Simple helper used by field-display filters for consistent FK rendering.
---
## Consumers in this package
Known imports of `_shared`:
- `datetime_filters.py`:
  - `_get_request_user_company`
  - `format_datetime_value`
- `display_tags.py`:
  - `_get_request_user_company`
  - `format_datetime_value`
- `field_filters.py`:
  - `_get_request_user_company`
  - `format_datetime_value`
  - `display_fk`
This confirms `_shared.py` is a utility backbone, not a tag entrypoint.
---
## Usage patterns
Typical pattern inside a template filter:
```python
request, user, company = _get_request_user_company()
return format_datetime_value(value, user=user, company=company)
```
This enables consistent preference-aware formatting even when only `value` is passed to filter.
---
## Design notes
- Thread-local access keeps filter signatures small, but still allows explicit `user/company` overrides when available.
- Formatter behavior is fault-tolerant:
  - catches timezone/format exceptions
  - falls back to stable defaults
- Returning `""` for `None` values is template-friendly and avoids noisy `"None"` rendering.
---
## Caveats
- Thread-local request must be correctly set by middleware for context fallback to work.
- Timezone conversion relies on valid timezone strings in user/company settings.
- Returning `None` for unsupported value types means callers should guard or normalize before display in some contexts.
---
## Summary
`_shared.py` is the shared formatting/context utility module for Horilla template tags. Date/time display goes through `get_datetime_formatter()` so calendar extensions can override Gregorian `strftime` without forking this helper.
