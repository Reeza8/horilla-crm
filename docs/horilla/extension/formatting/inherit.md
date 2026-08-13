# Horilla `_inherit_formatter` — DateTimeFormatter Extension Guide

Extend Gregorian date/time **display and parsing** **without** editing `DateTimeFormatter` or template-tag helpers. Calendar apps (for example Jalali) override `format_*` / `parse_*` on a composed subclass.

**Related:** [Extension system index](../inherit.md) · [Form `_inherit_form`](../forms/inherit.md) · [View `_inherit_view`](../view/inherit.md) · [DateTimeFormatter](../../contrib/generics/formatting/datetime.md)

**Reference implementation:** `horilla/extension/formatting/` · **Target class:** `horilla.contrib.generics.formatting.datetime.DateTimeFormatter`

---

## Quick start

```python
# my_calendar_extensions/formatters.py  (or formatting.py)
from horilla.contrib.generics.formatting import DateTimeFormatter
from horilla.extension.formatting import DateTimeFormatterExtension


class JalaliDateTimeFormatterExtension(DateTimeFormatterExtension):
    _inherit_formatter = (
        "horilla.contrib.generics.formatting.datetime.DateTimeFormatter"
    )

    def format_date(self, value, fmt, *, user=None):
        # Call the target class explicitly — zero-arg super() breaks on composed mixins.
        if not _should_use_jalali(user):
            return DateTimeFormatter.format_date(self, value, fmt, user=user)
        return _to_jalali_date(value, fmt)

    def parse_date(self, value, *, user=None):
        parsed = _from_jalali_date(value, user=user)
        if parsed is not None:
            return parsed
        return DateTimeFormatter.parse_date(self, value, user=user)
```

```python
# my_calendar_extensions/apps.py
auto_import_modules = ["formatters"]  # or "formatting"
```

```python
# local_settings.py — client-owned
INSTALLED_APPS += ["my_calendar_extensions"]
```

Restart the dev server after changing extensions.

Template tags keep calling `format_datetime_value()`; that helper delegates to `get_datetime_formatter().format(...)`. List filters and bulk update call `get_datetime_formatter().parse_*(...)`.

---

## Rules

| Topic | Rule |
|-------|------|
| Base class | `DateTimeFormatterExtension` (`horilla.extension.formatting`) — do **not** instantiate |
| `_inherit_formatter` | `"<module>.<ClassName>"` — normally `DateTimeFormatter` |
| Overrides | `format`, `format_datetime`, `format_date`, `format_time`, `parse_date`, `parse_datetime` |
| `super()` | Do **not** use zero-arg `super()`; call `DateTimeFormatter.format_date(self, ...)` |
| App order | Extension app after generics is OK; `bootstrap_extensions()` + `get_datetime_formatter()` still resolve |

### `_inherit_formatter` validation

| Rule | Result |
|------|--------|
| Path not `"module.ClassName"` | `ValueError` at class definition |
| Target import fails | Startup error when composing |

---

## Why not patch helpers in `_shared.py` / `list.py`?

`format_datetime_value` and list/bulk date coercion used to inline Gregorian `strftime` / `parse_date`. Calendar apps would have to fork those call sites. `DateTimeFormatter` is the single override point for **format and parse**; template tags, history display, list filters, and bulk update all go through `get_datetime_formatter()`.

View-specific UI (inline edit widgets / attrs) uses [`_inherit_view`](../view/inherit.md), not formatter overrides.

---

## Composition and MRO

```text
DateTimeFormatterExtended
 → JalaliDateTimeFormatterExtensionMixin
 → DateTimeFormatter
```

Markers on composed classes:

```python
__horilla_formatter_composed__ = True
__horilla_formatter_path__ = "horilla.contrib.generics.formatting.datetime.DateTimeFormatter"
__wrapped_formatter__ = DateTimeFormatter
```

The original target class is never modified.

---

## Bootstrap and resolution

| Hook | Location | Purpose |
|------|----------|---------|
| `bootstrap_extensions()` | `horilla/extension/bootstrap.py` | Calls `apply_formatter_extensions(force=True)` after apps load |
| `apply_formatter_extensions()` | `horilla/extension/formatting/bootstrap.py` | Builds `FORMATTER_COMPOSED_MAP` |
| `resolve_datetime_formatter_class()` | `horilla/extension/formatting/resolve.py` | Returns composed class |
| `get_datetime_formatter()` | same | Cached instance used by template tags, list, bulk update |

```python
from horilla.extension.formatting import get_datetime_formatter

formatter = get_datetime_formatter()
formatter.format(value, user=user, company=company)
formatter.parse_date("1403-01-01", user=user)
```

Default target path when `formatter_class` is omitted:

```text
horilla.contrib.generics.formatting.datetime.DateTimeFormatter
```

---

## Package layout

```text
horilla/extension/formatting/
├── __init__.py       # DateTimeFormatterExtension, get_datetime_formatter, …
├── cache.py          # RESOLVER_CACHE, INSTANCE_CACHE, bootstrap flag helpers
├── registry.py       # FORMATTER_EXTENSION_REGISTRY, FormatterExtensionSpec
├── metaclass.py      # DateTimeFormatterExtension registration
├── compose.py        # mixin MRO composition
├── resolve.py        # resolve_datetime_formatter_class(), get_datetime_formatter()
└── bootstrap.py      # apply_formatter_extensions()
```

Public API:

```python
from horilla.extension.formatting import (
    DateTimeFormatterExtension,
    apply_formatter_extensions,
    resolve_datetime_formatter_class,
    get_datetime_formatter,
    clear_formatter_extension_cache,
)
```

---

## Non-goals

- Changing stored values (DB remains Gregorian)
- Per-field calendar widgets alone (combine with `_inherit_form` / `_inherit_view` as needed)
- Runtime hot-reload (restart required)

---

## Related display and form hooks

| Need | Mechanism |
|------|-----------|
| Format / parse dates in templates, lists, bulk update | `_inherit_formatter` on `DateTimeFormatter` |
| Inline edit field widget / attrs | [`_inherit_view`](../view/inherit.md) on `EditFieldView` / `UpdateFieldView` |
| Add a date-system field on My Settings | `_inherit_form` + `fieldsets_insert` on `RegionalFormattingForm` |
| Render extra fields without forking HTML | `HorillaModelForm.get_fieldsets()` (see [forms inherit](../forms/inherit.md#layout-hooks)) |
