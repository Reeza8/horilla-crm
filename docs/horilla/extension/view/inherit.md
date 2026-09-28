# Horilla `_inherit_view` — View Extension Guide

Extend concrete subclasses of [`horilla.views.generic.View`](../../views/generic.md) **without** editing those view classes. Calendar apps (for example Jalali) override parse hooks on composed subclasses of `FieldInfoResolver` for the bulk **Edit Details** save.

**Related:** [Extension system index](../inherit.md) · [Formatter `_inherit_formatter`](../formatting/inherit.md) · [Generic View](../../views/generic.md) · [Edit Details helpers](../../contrib/generics/views/helpers/edit_field.md)

**Reference implementation:** `horilla/extension/view/` · **Resolution hook:** `horilla.views.generic.View.as_view`

---

## Quick start

```python
# horilla_jalali/views.py
from horilla.extension.view import ViewExtension
from horilla.contrib.generics.views.helpers.edit_field import FieldInfoResolver


class JalaliFieldInfoResolverExtension(ViewExtension):
    _inherit_view = (
        "horilla.contrib.generics.views.helpers.edit_field.FieldInfoResolver"
    )

    def parse_date_field_value(self, value, user=None):
        # Zero-arg super() works: rebind_namespace_supers() (compose.py) gives
        # each copied method a __class__ cell bound to the generated mixin,
        # so this correctly chains to the next extension or the target view.
        return FieldInfoResolver.parse_date_field_value(self, value, user=user)

    def parse_datetime_field_value(self, value, user=None):
        return FieldInfoResolver.parse_datetime_field_value(
            self, value, user=user
        )
```

```python
# apps.py
auto_import_modules = [..., "views"]
```

Register URLs with the usual `SomeView.as_view()` — the base `View.as_view` wrapper resolves the composed class on each request.

For **direct instantiation** (Edit Details context build, ExtraFieldsProvider):

```python
from horilla.contrib.generics.views.helpers.edit_field import (
    get_field_info_resolver,
    get_edit_all_fields_view,
    get_extra_fields_provider,
)

resolver = get_field_info_resolver()  # resolve_view_class(FieldInfoResolver)()
```

---

## Rules

| Topic | Rule |
|-------|------|
| Base class | `ViewExtension` (`horilla.extension.view`) — do **not** instantiate |
| `_inherit_view` | `"<module>.<ClassName>"` — concrete view path (e.g. `FieldInfoResolver`) |
| Target | A concrete Django `View` subclass, or a shared **base** class (e.g. `HorillaMultiStepFormView`, `HorillaDetailTabView`, `UpdateAllFieldsView`) to apply to every subclass at once — see [Targeting a shared base class](#targeting-a-shared-base-class); composition is applied through Horilla `View.as_view` |
| Overrides | Any instance methods on the target (captured from the extension class `__dict__`) |
| `super()` | Zero-arg `super()` works — `rebind_namespace_supers()` (`compose.py`) rebinds each copied method's `__class__` cell to the generated mixin, so it correctly chains to the next extension or the target view, regardless of how many extensions are stacked |
| Direct `Target()` | Misses extensions — use `resolve_view_class(Target)` / `get_field_info_resolver()` |

### What belongs where

| Need | Mechanism |
|------|-----------|
| Display / parse dates everywhere | [`_inherit_formatter`](../formatting/inherit.md) on `DateTimeFormatter` |
| Edit Details widget / attrs / parse hooks | `_inherit_view` on `FieldInfoResolver` (or `UpdateAllFieldsView` for save seams) |
| List columns / bulk field lists | [`_inherit_list`](../list/inherit.md) |

Do **not** couple `HorillaListView` to `HorillaBulkUpdateMixin` for calendar parsing — both call `get_datetime_formatter().parse_*`.

---

## Composition and MRO

```text
FieldInfoResolverExtended
 → JalaliFieldInfoResolverExtensionMixin
 → FieldInfoResolver
 → ...
 → horilla.views.generic.View
```

Markers on composed classes:

```python
__horilla_view_composed__ = True
__horilla_view_path__ = "....FieldInfoResolver"
__wrapped_view__ = FieldInfoResolver
```

---

## Targeting a shared base class

`_inherit_view = "....FieldInfoResolver"` covers exactly one concrete view. Some views are themselves shared **base** classes every concrete subclass across every app inherits — e.g. `HorillaSingleFormView`, `HorillaMultiStepFormView`, `HorillaDetailTabView`, `UpdateAllFieldsView`. Target the base directly to reach every subclass, present and future, without registering against each one by name:

```python
class DuplicateCheckMultiStepFormExtension(ViewExtension):
    _inherit_view = "horilla.contrib.generics.views.multi_form.HorillaMultiStepFormView"

    def form_valid(self, form):
        # super() reaches the concrete wizard view's own form_valid, whatever
        # app it belongs to.
        ...
        return super().form_valid(form)
```

`resolve_view_class(view_class)` (called from `View.as_view()`'s per-request wrapper) checks an **exact match** for `view_class` first; if none is registered, it walks `view_class.__mro__` and composes onto the first ancestor with a registration (`_resolve_via_base_class()` in `horilla/extension/view/resolve.py`). A concrete-class registration always wins over a base-class one. The result is cached per concrete class (`VIEW_BASE_COMPOSED_MAP`), so the MRO walk only happens once per view class, not per request.

Multiple extensions can target the same base class and stack normally — each composed mixin's `super()` chains to the next, same as any other `_inherit_view` registration. See `horilla/contrib/duplicates/view_extensions.py` and `horilla/contrib/cadences/view_extensions.py` for real base-class registrations (both targeting `HorillaDetailTabView`, verified to compose together correctly), and `docs/horilla/extension/inherit.md`'s "Targeting a shared base class" for the platform-wide note (also covers `_inherit_list`).

---

## Bootstrap and resolution

| Hook | Location | Purpose |
|------|----------|---------|
| `bootstrap_extensions()` | `horilla/extension/bootstrap.py` | Calls `apply_view_extensions(force=True)` |
| `apply_view_extensions()` | `horilla/extension/view/bootstrap.py` | Builds `VIEW_COMPOSED_MAP` |
| `resolve_view_class()` | `horilla/extension/view/resolve.py` | Returns composed class |
| `View.as_view()` | `horilla/views/generic/base.py` | Per-request resolve (like list/card) |

```python
from horilla.extension.view import resolve_view_class
from horilla.contrib.generics.views.helpers.edit_field import FieldInfoResolver

Resolved = resolve_view_class(FieldInfoResolver)
```

---

## Package layout

```text
horilla/extension/view/
├── __init__.py       # ViewExtension, resolve_view_class, …
├── cache.py
├── registry.py       # VIEW_EXTENSION_REGISTRY, ViewExtensionSpec
├── metaclass.py      # ViewExtension registration
├── compose.py
├── resolve.py
└── bootstrap.py      # apply_view_extensions()
```

Public API:

```python
from horilla.extension.view import (
    ViewExtension,
    apply_view_extensions,
    resolve_view_class,
    clear_view_extension_cache,
)
```

---

## Reference targets

### Concrete views (Jalali / Edit Details)

| Target | Typical overrides |
|--------|-------------------|
| `FieldInfoResolver` | `get_field_info`, `parse_date_field_value`, `parse_datetime_field_value` |
| `ExtraFieldsProvider` | `get_extra_fields`, `apply_extra_field` (Custom Fields) |
| `UpdateAllFieldsView` | `check_before_save`, `handle_save_error` (Duplicates, Approvals) |

Date **display** and list/bulk **parse** still go through `DateTimeFormatter` — view extensions only customize view-specific behavior.

### Shared base classes (custom_fields, duplicates, cadences, form_layouts)

| Target | Typical overrides |
|--------|--------------------|
| `HorillaSingleFormView` | `form_valid` (duplicate check); `get_form` / `resolve_form_mode` (Form Layouts Custom Layout) |
| `HorillaMultiStepFormView` | `form_valid`, `get_form_kwargs` (duplicate check; keep Multiple Choice POST values across wizard steps); `resolve_form_mode` (Custom Layout link) |
| `HorillaDetailTabView` | `_prepare_detail_tabs` (add a tab conditionally — Potential Duplicates, Cadence) |
