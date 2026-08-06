# Horilla text utilities (`horilla.utils.text`)

## Purpose

`horilla/utils/text.py` is a thin wrapper around Django’s `django.utils.text` helpers.

It exists so app code can keep one standard import path:

- instead of `from django.utils.text import slugify, …`
- use `from horilla.utils.text import slugify, …`

This matches the pattern used by `horilla.utils.translation`, `horilla.utils.timezone`, and `horilla.utils.html`.

---

## Module layout

```text
horilla/utils/
└── text.py   # re-exports django.utils.text functions
```

This page is `docs/horilla/utils/text.md`.

---

## What it re-exports

`horilla.utils.text` re-exports these names from `django.utils.text`:

- `Truncator`
- `camel_case_to_spaces`
- `capfirst`
- `compress_sequence`
- `compress_string`
- `get_text_list`
- `get_valid_filename`
- `normalize_newlines`
- `phone2numeric`
- `slugify`
- `smart_split`
- `unescape_string_literal`
- `wrap`

---

## Common usage

```python
from horilla.utils.text import slugify, Truncator, capfirst

name = slugify("My Report Title")  # "my-report-title"
```

Used across import/export, upload path generation, charts, and group-by views.

---

## Coding rule

If Horilla re-exports the symbol, import from `horilla.utils.text` — not `django.utils.text`.

See [coding_rule.md](../../coding_rule.md) and the package overview in [utils.md](./utils.md).
