# Horilla extension system

The Horilla **platform** supports extending installed apps in separate packages without forking target-app migrations or form/view classes. CRM modules (`horilla_crm.*`) are common targets; core modules (`horilla.contrib.core`, etc.) work the same way.

| Mechanism | Doc | Package | Status |
|-----------|-----|---------|--------|
| **`_inherit_model`** — add DB columns to existing models | [models/inherit.md](./models/inherit.md) | `horilla/extension/models/` | Implemented |
| **`_inherit_form`** — extend create/edit forms | [forms/inherit.md](./forms/inherit.md) | `horilla/extension/forms/` | Implemented |
| **`_inherit_list`** — extend list views (`HorillaListView`) | [list/inherit.md](./list/inherit.md) | `horilla/extension/list/` | Implemented |
| **`_inherit_card`** — extend card views (`HorillaCardView`) | [card/inherit.md](./card/inherit.md) | `horilla/extension/card/` | Implemented |
| **`_inherit_kanban`** — extend kanban views (`HorillaKanbanView`) | [kanban/inherit.md](./kanban/inherit.md) | `horilla/extension/kanban/` | Implemented |
| **`_inherit_detail`** — extend detail views (`HorillaDetailView`) | [detail/inherit.md](./detail/inherit.md) | `horilla/extension/detail/` | Implemented |
| **`_inherit_filter`** — extend filtersets (`HorillaFilterSet`) | [filter/inherit.md](./filter/inherit.md) | `horilla/extension/filter/` | Implemented |
| **`_inherit_nav`** — extend nav bars (`HorillaNavView`) | [nav/inherit.md](./nav/inherit.md) | `horilla/extension/nav/` | Implemented |
| **`_inherit_formatter`** — extend date/time format & parse (`DateTimeFormatter`) | [formatting/inherit.md](./formatting/inherit.md) | `horilla/extension/formatting/` | Implemented |
| **`_inherit_view`** — extend `horilla.views.generic.View` subclasses | [view/inherit.md](./view/inherit.md) | `horilla/extension/view/` | Implemented |

## Package layout

```text
horilla/extension/
├── __init__.py           # model API + makemigrations/migrate autodetector patch
├── bootstrap.py          # bootstrap_extensions() — compose all layers (URLconf hook)
├── models/               # _inherit_model (metaclass, migrations, registry)
├── forms/                # _inherit_form (registry, compose, resolve, bootstrap, cache)
├── filter/               # _inherit_filter (registry, compose, resolve, bootstrap, cache)
├── nav/                  # _inherit_nav (registry, compose, resolve, bootstrap, cache)
├── list/                 # _inherit_list (registry, compose, resolve, bootstrap, cache)
├── card/                 # _inherit_card (registry, compose, resolve, bootstrap, cache)
├── kanban/               # _inherit_kanban (registry, compose, resolve, bootstrap, cache)
├── detail/               # _inherit_detail (registry, compose, resolve, bootstrap, cache)
├── formatting/           # _inherit_formatter (registry, compose, resolve, bootstrap, cache)
└── view/                 # _inherit_view (registry, compose, resolve, bootstrap, cache)
```

Each view/form subpackage includes a **`cache.py`** module (resolver cache + bootstrap fingerprint) with **no imports** of `compose`, `bootstrap`, or `resolve`. That breaks cyclic imports between `registry`, `compose`, `bootstrap`, and `resolve` while keeping behavior unchanged.

## Typical extension app

**CRM example** (`my_lead_extensions`):

```text
my_lead_extensions/
├── apps.py               # AppLauncher; auto_import_modules = ["models", "forms", "filters", "navbars", "lists", ...]
├── models.py             # _inherit_model = "leads.Lead"
├── forms.py              # _inherit_form = "horilla_crm.leads.forms.LeadSingleForm"
├── filters.py            # _inherit_filter = "horilla_crm.leads.filters.LeadFilter"
├── navbars.py            # _inherit_nav = "horilla_crm.leads.views.core.LeadNavbar"
├── lists.py              # _inherit_list = "horilla_crm.leads.views.core.LeadListView"
├── cards.py              # _inherit_card = "horilla_crm.leads.views.core.LeadCardView"
├── kanbans.py            # _inherit_kanban = "...LeadKanbanView"
├── details.py            # _inherit_detail = "...LeadDetailView"
└── migrations/
```

**Core platform example** (same mechanics; see `horilla/extension/*/tests.py`):

```text
# Model: _inherit_model = "core.Department"
# Form:  _inherit_form = "horilla.contrib.core.forms.base.HolidayForm"
# List:  _inherit_list = "horilla.contrib.core.views.users.UserListView"
# Detail: _inherit_detail = "horilla.contrib.core.views.users.UserDetailView"
# Kanban: _inherit_kanban = "horilla.contrib.core.views.users.UserKanbanView"
# Formatter: _inherit_formatter = "horilla.contrib.generics.formatting.datetime.DateTimeFormatter"
# View:  _inherit_view = "horilla.contrib.generics.views.helpers.edit_field.EditFieldView"
```

```python
# Client local_settings.py only — do not edit horilla/settings/base.py or horilla_apps.py
INSTALLED_APPS += [
    "my_lead_extensions",  # after target apps (horilla_crm.*, core, etc.) is OK
]
```

## Bootstrap

| Layer | When it composes | Entry point |
|-------|------------------|-------------|
| **Models** | Import / `makemigrations` | `ExtensionModelBase` + `HorillaAutodetector` (no `ready()` hook) |
| **Forms** | Startup + each `get_form_class()` | `apply_form_extensions()` via `bootstrap_extensions()` and `resolve_form_class()` |
| **Filters** | Startup + each `get_filterset_class()` | `apply_filter_extensions()` via `bootstrap_extensions()` and `resolve_filterset_class()` |
| **Nav** | Startup + each navbar HTTP request | `apply_nav_extensions()` via `bootstrap_extensions()` and `HorillaNavView.as_view()` wrapper |
| **Lists** | Startup + each list HTTP request | `apply_list_extensions()` via `bootstrap_extensions()` and `HorillaListView.as_view()` wrapper |
| **Cards** | Startup + each card HTTP request | `apply_card_extensions()` + `resolve_card_view_class()` via `HorillaListView.as_view()` (`HorillaCardView`) |
| **Kanban** | Startup + each kanban HTTP request | `apply_kanban_extensions()` + `resolve_kanban_view_class()` via `HorillaListView.as_view()` |
| **Detail** | Startup + each detail HTTP request | `apply_detail_extensions()` + `resolve_detail_view_class()` via `HorillaDetailView.as_view()` |
| **Formatter** | Startup + each `get_datetime_formatter()` | `apply_formatter_extensions()` via `bootstrap_extensions()` and `get_datetime_formatter()` |
| **View** | Startup + each Horilla `View.as_view()` / `resolve_view_class()` | `apply_view_extensions()` via `bootstrap_extensions()` and `horilla.views.generic.View.as_view` |

**Unified startup** — after all apps are loaded, `horilla/urls/project.py` calls:

```python
from horilla.extension.bootstrap import bootstrap_extensions

bootstrap_extensions()
```

`bootstrap_extensions()` runs `apply_form_extensions`, `apply_filter_extensions`, `apply_nav_extensions`, `apply_list_extensions`, `apply_card_extensions`, `apply_kanban_extensions`, `apply_detail_extensions`, `apply_formatter_extensions`, and `apply_view_extensions` (all `force=True`).

**Naming:** Under `horilla/`, types and functions omit a redundant `Horilla` prefix when the import path already provides context — e.g. `ListExtension`, `FormExtension`, `bootstrap_extensions()` (not `HorillaListExtension`). Framework types such as `HorillaCoreModel` in `horilla.contrib.core` keep their established names.

`CoreConfig.ready()` also invokes all `apply_*_extensions` hooks when `django.apps.ready` is already true; in practice the **URLconf call above** is what matters for extension apps listed after their target apps.

Extension apps may load **after** the apps they extend in `INSTALLED_APPS`; no `horilla_apps.py` / `base.py` edits are required.

**Migrations:** `horilla/extension/__init__.py` patches `makemigrations` / `migrate` to use `HorillaAutodetector` so injected model fields generate migrations in the **owning extension app**, not in the target app.

| Layer | Load-order sensitivity |
|-------|-------------------------|
| Form / filter / formatter | No — `get_form_class()` / `get_filterset_class()` / `get_datetime_formatter()` resolve when called |
| Nav / list / card / kanban / detail / view | No for authors — per-request `as_view()` wrapper (see [nav/inherit.md](./nav/inherit.md), [list/inherit.md](./list/inherit.md#why-request-time-resolution), [view/inherit.md](./view/inherit.md)) |

Filter panel field options come from `_get_model_fields()` and composed `Meta.exclude` — see [filter/inherit.md](./filter/inherit.md#how-the-filter-panel-uses-your-filterset).

## Registration and cache invalidation

When an extension class is defined (`__init_subclass__`):

| Step | Module | Action |
|------|--------|--------|
| 1 | `metaclass.py` | Build `*ExtensionSpec`, call `register_*_extension()` |
| 2 | `registry.py` | Append spec to `*_EXTENSION_REGISTRY`; invalidate resolver cache (`list`/`kanban`/`detail`: `invalidate_after_registry_change()`; `filter`: `invalidate_all()`) |
| 3 | `metaclass.py` | Call `_compose_registered_target()` → `apply_*_extensions()` when `django.apps.ready` |

`registry.py` does **not** import `compose` or `resolve`. `compose.py` loads `get_*_extensions_for()` via a **lazy import inside** `compose_*_view_class()`. `bootstrap` and `resolve` read/write shared state only through `cache.py` (`RESOLVER_CACHE`, `LAST_FINGERPRINT` / `BOOTSTRAP_APPLIED`).

```text
registry  →  cache          (invalidate only)
bootstrap →  compose → registry   (lazy get_* inside compose)
resolve   →  bootstrap (lazy apply_*)
          →  registry  (COMPOSED_MAP)
          →  cache     (RESOLVER_CACHE)
```

Do not import `horilla.extension` from `horilla/__init__.py` (risk of `AppRegistryNotReady`).

## Public API (extension authors)

| Layer | Import | Registration class |
|-------|--------|-------------------|
| Model | `from horilla.contrib.core.models import HorillaCoreModel` | Subclass + `_inherit_model = "app_label.Model"` |
| Form | `from horilla.extension.forms import FormExtension` | Subclass + `_inherit_form = "module.FormClass"` |
| Filter | `from horilla.extension.filter import FilterExtension` | Subclass + `_inherit_filter = "module.FilterClass"` |
| Nav | `from horilla.extension.nav import NavExtension` | Subclass + `_inherit_nav = "module.NavbarClass"` |
| List | `from horilla.extension.list import ListExtension` | Subclass + `_inherit_list = "module.ListViewClass"` |
| Card | `from horilla.extension.card import CardExtension` | Subclass + `_inherit_card = "module.CardViewClass"` |
| Kanban | `from horilla.extension.kanban import KanbanExtension` | Subclass + `_inherit_kanban = "module.KanbanViewClass"` |
| Detail | `from horilla.extension.detail import DetailExtension` | Subclass + `_inherit_detail = "module.DetailViewClass"` |
| Formatter | `from horilla.extension.formatting import DateTimeFormatterExtension` | Subclass + `_inherit_formatter = "module.DateTimeFormatter"` |
| View | `from horilla.extension.view import ViewExtension` | Subclass + `_inherit_view = "module.ViewClass"` |

Startup (platform — already wired in `horilla/urls/project.py`):

```python
from horilla.extension.bootstrap import bootstrap_extensions
```

Debug helpers:

```python
from horilla.extension.forms import resolve_form_class, print_form_mro, get_form_extensions
from horilla.extension.filter import resolve_filterset_class, print_filter_mro, get_filter_extensions
from horilla.extension.nav import resolve_nav_view_class, print_nav_view_mro, get_nav_extensions
from horilla.extension.list import resolve_list_view_class, print_list_view_mro, get_list_extensions
from horilla.extension.card import resolve_card_view_class, print_card_view_mro, get_card_extensions
from horilla.extension.kanban import resolve_kanban_view_class, print_kanban_view_mro, get_kanban_extensions
from horilla.extension.detail import resolve_detail_view_class, print_detail_view_mro, get_detail_extensions
from horilla.extension.formatting import get_datetime_formatter, resolve_datetime_formatter_class
from horilla.extension.view import resolve_view_class
```

```bash
python manage.py check   # includes form/filter/nav extension check IDs (E001+)
```

## Architecture

See [Plan_HORILLA_INHERIT_MIGRATION.md](../../Plan_HORILLA_INHERIT_MIGRATION.md) for HR → CRM mapping and design decisions.
