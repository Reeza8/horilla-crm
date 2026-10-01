# History Registry (`history_registry.py`)

## Purpose

`horilla/registry/history_registry.py` lets apps change how the History tab
shows dates and times without the generics app importing them.

The History tab (`generics/templates/history_tab.html`) renders record
timestamps and date/datetime diff values through the `history_datetime`
filter (`horilla_tags/history_i18n.py`). By default that filter uses the
user/company datetime format. An app that needs a different display, for
example another calendar system, registers a formatter here.

## Core APIs

### `register_history_datetime_formatter(formatter, priority=50)`

Registers a callable:

```python
def formatter(value, *, user=None, company=None):
    ...
```

- `value` is what the template passed to the filter: a `date`, a `datetime`,
  or the display string auditlog stored for a diff value
- Return the formatted text to use it, or `None` to leave the value to the
  next formatter and finally to the default format
- Lower `priority` runs earlier; registering the same callable again is a
  no-op
- A formatter that raises is logged and skipped, so the History tab still
  renders

### `unregister_history_datetime_formatter(formatter)`

Removes a registered formatter.

### `get_history_datetime_formatters()`

Returns the registered formatters in the order `history_datetime` tries them.

## Practical Usage (in app `registration.py`)

`horilla_jalali` shows Shamsi dates on the History tab this way:

```python
from horilla.registry.history_registry import register_history_datetime_formatter
from horilla_jalali.history import format_history_datetime_as_jalali

register_history_datetime_formatter(format_history_datetime_as_jalali)
```

Its formatter returns `None` unless the Shamsi calendar is active, so other
languages and users who chose the Gregorian calendar keep the default format.

## Front-end hook: `horilla:content-loaded`

Core templates do not call extension JavaScript directly. When they insert
content whose inputs an extension may want to enhance outside the usual htmx
swap flow, they fire a bubbling `horilla:content-loaded` event on the
container:

```html
hx-on::after-swap="htmx.trigger('#filtermodalBox', 'horilla:content-loaded')"
```

Extensions listen on `document` and use `event.target` as the root:

```javascript
document.addEventListener("horilla:content-loaded", function (event) {
    initHorillaJalaliInputs(event.target);
});
```

The History tab's filter modal fires it once its form is loaded.
