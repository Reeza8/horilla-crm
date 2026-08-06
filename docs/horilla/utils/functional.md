# Horilla functional utilities (`horilla.utils.functional`)

## Purpose

`horilla/utils/functional.py` is a thin wrapper around Django’s `django.utils.functional` helpers.

It exists so app code can keep one standard import path:

- instead of `from django.utils.functional import cached_property, lazy, …`
- use `from horilla.utils.functional import cached_property, lazy, …`

This matches the pattern used by `horilla.utils.translation`, `horilla.utils.html`, and `horilla.utils.text`.

---

## Module layout

```text
horilla/utils/
└── functional.py   # re-exports django.utils.functional helpers
```

This page is `docs/horilla/utils/functional.md`.

---

## What it re-exports

`horilla.utils.functional` re-exports these names from `django.utils.functional`:

- `LazyObject`
- `Promise`
- `SimpleLazyObject`
- `cached_property`
- `classproperty`
- `empty`
- `keep_lazy`
- `keep_lazy_text`
- `lazy`
- `lazystr`
- `partition`

---

## Common usage

```python
from horilla.utils.functional import cached_property, lazy, Promise

class MyView:
    @cached_property
    def related_list_config(self):
        return {...}
```

`cached_property` is widely used on Horilla list/detail views for computed config. See also [coding_rule.md](../../coding_rule.md) guidance on `@cached_property` on views.

---

## Coding rule

If Horilla re-exports the symbol, import from `horilla.utils.functional` — not `django.utils.functional`.

See [coding_rule.md](../../coding_rule.md) and the package overview in [utils.md](./utils.md).
