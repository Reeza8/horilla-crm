# Horilla `_inherit_tab` — Tab View Extension Guide

Extend concrete subclasses of [`HorillaTabView`](../../contrib/generics/views.md) **without** editing those view classes. Third-party apps append settings/shell tabs (for example on `CompanyInformationTabView`) by overriding `get_tabs` on a composed subclass.

**Related:** [Extension system index](../inherit.md) · [View `_inherit_view`](../view/inherit.md) · [Detail `_inherit_detail`](../detail/inherit.md)

**Reference implementation:** `horilla/extension/tab/` · **Resolution hook:** `HorillaTabView.as_view`

---

## Quick start

```python
# myapp/tabs.py
from horilla.urls import reverse_lazy
from horilla.utils.translation import gettext_lazy as _
from horilla.extension.tab import TabExtension
from horilla.contrib.core.views.branches import CompanyInformationTabView


class MyCompanyInfoTab(TabExtension):
    _inherit_tab = (
        "horilla.contrib.core.views.branches.CompanyInformationTabView"
    )
    _inherit_tab_priority = 100

    def get_tabs(self):
        # Call the target class explicitly — zero-arg super() breaks on composed mixins.
        tabs = list(CompanyInformationTabView.get_tabs(self))
        if self.request.user.has_perm("myapp.view_thing"):
            tabs.append(
                {
                    "title": _("My Tab"),
                    "url": reverse_lazy("myapp:my_tab"),
                    "target": "my-tab-content",
                    "id": "my-tab-view",
                }
            )
        return tabs
```

```python
# apps.py
auto_import_modules = [..., "tabs"]
```

Register your tab content URL in the extension app as usual. Keep using
`CompanyInformationTabView.as_view()` in core URLs — the base `as_view`
wrapper resolves the composed class on each request.

---

## Rules

| Topic | Rule |
|-------|------|
| Base class | `TabExtension` (`horilla.extension.tab`) — do **not** instantiate |
| `_inherit_tab` | `"<module>.<ClassName>"` — concrete `HorillaTabView` subclass path |
| Target | Must go through `HorillaTabView.as_view` (not bare Django `TemplateView`) |
| Overrides | Prefer `get_tabs`; any instance methods on the target are composed |
| `super()` | Do **not** use zero-arg `super()`; call `TargetClass.get_tabs(self)` |
| Direct `Target()` | Misses extensions — use `resolve_tab_view_class(Target)` |

### What belongs where

| Need | Mechanism |
|------|-----------|
| Add a settings shell tab (Company Information, etc.) | `_inherit_tab` on that `HorillaTabView` subclass |
| Add a **record** detail tab (Lead/Opportunity) | Cadence/duplicates-style inject on `HorillaDetailTabView`, or own detail URLs |
| Extend generic `View` methods | [`_inherit_view`](../view/inherit.md) |

---

## Composition and MRO

```text
CompanyInformationTabViewExtended
 → MyCompanyInfoTabMixin
 → CompanyInformationTabView
 → HorillaTabView
 → ...
```

Markers on composed classes:

```python
__horilla_tab_composed__ = True
__horilla_tab_path__ = "....CompanyInformationTabView"
__wrapped_tab_view__ = CompanyInformationTabView
```

---

## Bootstrap and resolution

| Hook | Location | Purpose |
|------|----------|---------|
| `bootstrap_extensions()` | `horilla/extension/bootstrap.py` | Calls `apply_tab_extensions(force=True)` |
| `apply_tab_extensions()` | `horilla/extension/tab/bootstrap.py` | Builds `TAB_COMPOSED_MAP` |
| `resolve_tab_view_class()` | `horilla/extension/tab/resolve.py` | Returns composed class |
| `HorillaTabView.as_view()` | `horilla/contrib/generics/views/core.py` | Per-request resolve |

```python
from horilla.extension.tab import resolve_tab_view_class
from horilla.contrib.core.views.branches import CompanyInformationTabView

Resolved = resolve_tab_view_class(CompanyInformationTabView)
```

---

## Package layout

```text
horilla/extension/tab/
├── __init__.py       # TabExtension, resolve_tab_view_class, …
├── cache.py
├── registry.py       # TAB_EXTENSION_REGISTRY, TabExtensionSpec
├── metaclass.py      # TabExtension registration
├── compose.py
├── resolve.py
├── bootstrap.py      # apply_tab_extensions()
└── tests.py
```

Public API:

```python
from horilla.extension.tab import (
    TabExtension,
    apply_tab_extensions,
    resolve_tab_view_class,
    clear_tab_extension_cache,
)
```

---

## Notes

- Override **`get_tabs`**, not a `@cached_property tabs`. `HorillaTabView.get_context_data` calls `get_tabs()`.
- Views that assign `self.tabs` in `setup` / `_prepare_detail_tabs` still work: default `get_tabs()` reads instance `tabs` first.
- Permission checks for injected tabs belong in the extension’s `get_tabs`.
