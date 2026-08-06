# Display template tags (`horilla_generics/templatetags/horilla_tags/display_tags.py`)

## Purpose

`display_tags.py` provides template utilities for rendering values in a user-friendly way, with built-in support for:

- currency fields
- datetime/date/time formatting with user/company preferences
- relation display (M2M lists)
- choice label rendering
- permission-gated **User** FK chips (avatar, name, detail link)

It helps templates avoid repetitive value-formatting logic.

---

## Registered tags/filters

This module registers:

- simple tag: `display_field_value`
- filter: `format_currency`
- filter: `shortname`

Both tags/filters are exposed through `{% load horilla_tags %}` (also registered as a Django template builtin in Horilla settings).

---

## `display_field_value` (simple_tag)

Signature:

- `display_field_value(obj, field_name, user)`

Template usage:

```django
{% load horilla_tags %}
{% display_field_value obj field_name request.user %}
```

This tag applies a prioritized formatting pipeline.

---

## Value resolution order

### 1) Model-declared currency fields

If model class defines `CURRENCY_FIELDS` and current field is listed:

- delegates to `get_currency_display_value(obj, field_name, user)`

This ensures model-specific currency formatting logic is respected.

---

### 2) Model custom display hook

If object exposes `get_field_display(field_name, user)`, the tag returns that value directly.

This is an extension point for model-specific display customization.

---

### 3) Raw attribute fetch

`value = getattr(obj, field_name, None)`

If value is `None`:

- returns empty string `""`.

---

### 4) JSONField formatting

If the model field is a `JSONField`, parses string JSON/literal when needed and returns a compact string for lists/dicts.

---

### 5) Date/time formatting

Calls:

- `_get_request_user_company()` (to resolve company context)
- `format_datetime_value(value, user=user, company=company, convert_timezone=True)`

If formatter returns non-`None`, returns formatted string.

This covers `datetime`, `date`, and `time` types with timezone/format preference fallback.

---

### 6) M2M / related manager formatting

If value behaves like related manager (`hasattr(value, "all")`):

- fetches related objects
- if **all** related objects are `isinstance(item, User)` (`horilla.auth.models.User`) → space-joined **user chips** via `render_user_chip` (same permission rule as below)
- otherwise returns comma-joined labels when non-empty
- returns empty string when empty

Example output (non-user):

- `"Tag A, Tag B, Tag C"`

---

### 7) Choice label fallback

Attempts model field metadata lookup:

- `field = obj._meta.get_field(field_name)`
- if field has `choices`, maps stored value to display label:
  - `dict(field.choices).get(value, value)`

This provides human labels without requiring explicit `get_FOO_display()` calls in template.

---

### 8) User FK chip

If `isinstance(value, User)` (`from horilla.auth.models import User`):

- delegates to `render_user_chip(value, user)`
- **With permission** `"{app_label}.view_{model_name}"` on the user model (same gate as `UserDetailView`):
  - returns Safe HTML chip from `user_chip.html` (avatar via `get_avatar()`, full name, arrow icon, link to `get_detail_view_url()`)
- **Without permission**:
  - returns plain `str(value)` (unchanged text display)

Render this output in HTML contexts (spans/divs), e.g. detail body fields — not inside an `<input value="...">` attribute (escaped attribute values break the chip markup).

---

### 9) String conversion fallback

If value has `__str__`:

- returns `str(value)`

Otherwise returns raw value.

---

## `render_user_chip` (Python helper)

Not a template tag; used by `display_field_value`.

Signature:

- `render_user_chip(target_user, viewer)`

Behavior:

1. If `target_user` is not a `User` instance → `str(target_user)` (or `""` if `None`)
2. If `viewer` is missing, unauthenticated, or lacks `view_<user>` → `str(target_user)`
3. Otherwise renders `user_chip.html` via `render_to_string` with:
   - `detail_url` from `get_detail_view_url()`
   - `avatar_url` from `get_avatar()` (profile image when set, else ui-avatars)
   - `full_name` from `get_full_name()` (fallback username / `str`)

M2M of users is joined with `format_html_join` from **`horilla.utils.html`** (not `django.utils.html`).

Chip template: [`user_chip.html`](../../../../../../horilla/contrib/generics/templates/user_chip.html) (avatar, name, `assets/img/arrow-up-right.svg`).

---

## `format_currency` (filter)

Signature:

- `format_currency(value, user)`

Usage:

```django
{{ amount|format_currency:request.user }}
```

Behavior:

1. if value is falsy → returns `""`
2. resolves user currency: `MultipleCurrency.get_user_currency(user)`
3. if found: `user_currency.display_with_symbol(value)`
4. else fallback to `str(value)`

This filter is a generic currency formatter independent of model field metadata.

---

## Difference between currency mechanisms

- `display_field_value`:
  - field-aware and model-aware
  - auto-detects currency fields via `CURRENCY_FIELDS`
  - good for rendering arbitrary model fields in dynamic tables/details
- `format_currency`:
  - value-only formatting
  - good for direct numeric variables in templates.

---

## Practical template examples

### Dynamic table cell rendering

```django
{% for col in columns %}
  <td>{% display_field_value row col.1 request.user %}</td>
{% endfor %}
```

### Detail header / body (HTML-safe span)

```django
<span class="ps-3 font-medium">{% display_field_value obj col.1 request.user %}</span>
```

### Details tab (HTML-safe div)

```django
<div class="...">
  {% display_field_value obj field_name request.user %}
</div>
```

### Direct amount formatting

```django
{{ invoice.total|format_currency:request.user }}
```

### Model-specific custom hook

If model implements `get_field_display(...)`, templates automatically use that logic:

```django
{% display_field_value employee "status" request.user %}
```

---

## Error handling behavior

- choice metadata lookup errors are caught and ignored
- fallback pipeline continues without breaking template render
- `None` values normalize to empty string for clean UI output

The tag is designed for resilient rendering in heterogeneous model schemas.

---

## Caveats

- `format_currency` treats falsy values as empty (`0` will render as empty string); use model-specific rendering if zero must be shown.
- M2M handling assumes `value` supports `.all()`.
- for complex choice structures (grouped choices), simple `dict(field.choices)` behavior may be insufficient in edge cases.
- User chip HTML must only be rendered into HTML contexts (spans/divs), never into attribute values.

---

## Summary

`display_tags.py` is the generic value-display layer for Horilla templates. It combines model-aware currency handling, user/company-aware date/time formatting, relation rendering, choice-label conversion, and permission-gated user chips (`render_user_chip` + `user_chip.html`) into reusable template helpers that keep UI rendering consistent and concise.
