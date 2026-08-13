# DateTimeFormatter (`horilla.contrib.generics.formatting`)

Gregorian date/time **formatting and parsing** used by template tags and views. Calendar extension apps override methods via [`_inherit_formatter`](../../extension/formatting/inherit.md).

---

## Package

```text
horilla/contrib/generics/formatting/
├── __init__.py       # re-exports DateTimeFormatter
└── datetime.py       # DateTimeFormatter
```

```python
from horilla.contrib.generics.formatting import DateTimeFormatter
```

Do not instantiate this class in app code for display/parse. Use the composed instance:

```python
from horilla.extension.formatting import get_datetime_formatter

formatter = get_datetime_formatter()
formatter.format(value, user=user, company=company)
formatter.parse_date(raw, user=user)
formatter.parse_datetime(raw, user=user)
```

---

## `DateTimeFormatter.format(value, user=None, company=None, convert_timezone=True)`

| Input | Result |
|-------|--------|
| `None` | `""` |
| `datetime` | timezone convert (optional), then `format_datetime` |
| `date` | `format_date` |
| `time` | `format_time` |
| other | `None` |

Format string priority (datetime / date / time):

1. matching field on `user`
2. matching field on `company`
3. `"%Y-%m-%d %H:%M:%S"` / `"%Y-%m-%d"` / `"%I:%M:%S %p"`

Timezone for datetimes: `user.time_zone`, else `company.time_zone`. Naive values are made aware with Django’s default timezone before conversion. If `convert_timezone=False` and the value is aware, it is normalized with `timezone.localtime`.

---

## Override hooks — format

| Method | Default |
|--------|---------|
| `format_datetime(value, fmt, *, user=None)` | `value.strftime(fmt)` |
| `format_date(value, fmt, *, user=None)` | `value.strftime(fmt)` |
| `format_time(value, fmt, *, user=None)` | `value.strftime(fmt)` |

On `strftime` errors, each method falls back to the default format for that type.

---

## Override hooks — parse

| Method | Default |
|--------|---------|
| `parse_date(value, *, user=None)` | Django `parse_date` |
| `parse_datetime(value, *, user=None)` | Django `parse_datetime`, then `%Y-%m-%dT%H:%M` |

Returns `None` when the string cannot be parsed. Calendar extensions (e.g. Jalali) override these so Shamsi input works when the user calendar is active.

`user` is passed through so extensions can read a per-user date system without changing call-site signatures.

---

## Consumers

| Consumer | Usage |
|----------|--------|
| `format_datetime_value()` in [`_shared.py`](../templatetags/horilla_tags/_shared.md) | `get_datetime_formatter().format(...)` |
| Inline edit display | `format_datetime_value(...)` after timezone conversion |
| List filter row rebuild | `HorillaListView.parse_filter_date_value` / `parse_filter_datetime_value` → formatter `parse_*` |
| Bulk update coercion | `HorillaBulkUpdateMixin.parse_bulk_date_value` / `parse_bulk_datetime_value` → formatter `parse_*` |

Filters `user_datetime_format` and `user_datetime_format_display` pick up composed formatters automatically. List and bulk-update do **not** import Jalali helpers or couple to each other for calendar logic.
