# Horilla HTML utilities (`horilla.utils.html`)

## Purpose

`horilla/utils/html.py` is a thin wrapper around Django’s `django.utils.html` helpers.

It exists so app code can keep one standard import path:

- instead of `from django.utils.html import format_html, escape, …`
- use `from horilla.utils.html import format_html, escape, …`

This matches the pattern used by `horilla.utils.translation` and `horilla.utils.timezone`.

---

## Module layout

```text
horilla/utils/
└── html.py   # re-exports django.utils.html functions
```

This page is `docs/horilla/utils/html.md`.

---

## What it re-exports

`horilla.utils.html` re-exports these names from `django.utils.html`:

- `avoid_wrapping`
- `conditional_escape`
- `escape`
- `escapejs`
- `format_html`
- `format_html_join`
- `html_safe`
- `json_script`
- `linebreaks`
- `strip_spaces_between_tags`
- `strip_tags`
- `urlize`

---

## Common usage

```python
from horilla.utils.html import format_html, format_html_join, escape

html = format_html('<span class="badge">{}</span>', label)

joined = format_html_join(
    " ",
    "{}",
    ((chip,) for chip in chips),
)
```

Use `format_html` / `format_html_join` when building Safe HTML in models, views, or templatetags (for example user chips in `display_tags.py`, `get_avatar_with_name()` on `HorillaUser`).

---

## Coding rule

If Horilla re-exports the symbol, import from `horilla.utils.html` — not `django.utils.html`.

See [coding_rule.md](../../coding_rule.md) and the package overview in [utils.md](./utils.md).
