# Horilla Navbar View (`horilla/contrib/generics/views/navbar.py`)

## 🎯 Purpose

`HorillaNavView` renders `templates/navbar.html` and provides a **shared navigation bar** for Horilla list-style pages.

It supports:
- pinned “default” views
- switching between view types (`all`, recently created/modified, recently viewed, custom view types, and saved filter list views)
- optional search and filter panel UI (controlled mostly by class flags)
- optional layout switching (list/kanban/card/group_by/timeline/split_view/chart)
- optional UI actions (import / add column / settings modals) when permissions allow

The class is designed to be subclassed by feature-specific Navbar classes (examples: `UserNavbar` in core, `LeadNavbar` in CRM).

### Extension resolution (`_inherit_nav`)

`HorillaNavView.as_view()` wraps the class so each request calls `resolve_nav_view_class()`. Target apps register navbar URLs in `AppLauncher.ready()` before extension apps import `navbars.py`. See [../../../extension/inherit.md](../../../extension/inherit.md).

### Implementation imports

`navbar.py` uses Horilla shims (not raw Django registry/query imports):

```python
from horilla.apps import apps
from horilla.db.models import Q
from horilla.urls import resolve, reverse_lazy
```

Saved filter lists and pinned views resolve models through `horilla.apps.apps.get_model()` when building dropdown context.

---

## 📦 Template integration

`HorillaNavView` is a `TemplateView`:
- `template_name = "navbar.html"`

`get_context_data()` fills all template variables used by `horilla_generics/templates/navbar.html`.

---

## 🔁 Main class: `HorillaNavView`

### 📍 Definition

```python
class HorillaNavView(TemplateView):
    template_name = "navbar.html"
    ...
```

### 🎯 How view type is selected

`view_type` is determined in `get_context_data()`:

1. Read `request.GET["view_type"]` if provided, otherwise use `get_default_view_type()`
2. Validate the value against `get_valid_view_types()`
3. If invalid, fallback to `"all"`

---

## 🧩 What `get_context_data()` returns (all variables set by navbar.py)

The table below lists context keys and where they come from, plus an example value you can expect.

### Core identity + layout values

| Context key | How it is set | Example |
|---|---|---|
| `effective_layout` | `request.GET["layout"]` OR `self.default_layout` OR `"list"` | `"kanban"` |
| `nav_title` | `self.nav_title` | `"Leads"` |
| `search_url` | `self.search_url` OR `request.path` | `"/leads/list/"` |
| `search_push_url` | `"true"` if `self.search_push_url` else `"false"` | `"true"` |
| `main_url` | `self.main_url` OR `request.path` | `"/leads/view/"` |
| `kanban_url` | `self.kanban_url` | `"/leads/kanban/"` |
| `group_by_url` | `getattr(self, "group_by_url", None) or ""` | `"/leads/group_by/"` |
| `card_url` | `getattr(self, "card_url", None) or ""` | `"/leads/card/"` |
| `timeline_url` | `getattr(self, "timeline_url", None) or ""` | `"/leads/timeline/"` |
| `timeline_settings_modal_url` | Built only when `timeline_url` is set; starts from `reverse_lazy("horilla_generics:timeline_settings")` and includes query params | `"/timeline-settings/?app_label=leads&model=Lead&main_url=/leads/view/&..."` |
| `split_view_url` | `getattr(self, "split_view_url", None)` as string or `""` | `"/leads/split_view/"` |
| `chart_url` | `getattr(self, "chart_url", None)` as string or `""` | `"/leads/chart/"` |
| `actions` | computed `@cached_property actions` (only if `enable_actions=True`) | `[{"action": "Add Column to List", ...}, ...]` |
| `new_button` | `self.new_button` OR `{}` | `{"url": "/leads/create?new=true", "attrs": {...}}` |
| `second_button` | `self.second_button` OR `{}` | `{}` |
| `model_name` | `self.model_name` | `"Lead"` |
| `model_app_label` | `self.model_app_label` | `"leads"` |
| `nav_width` | `self.nav_width` | `True` |

### View type + pin + available options

| Context key | How it is set | Example |
|---|---|---|
| `view_type` | validated from request / pinned / defaults | `"recently_created"` |
| `show_list_only` | `show_list_only()` based on `custom_view_type` entry | `True` |
| `custom_view_type` | `self.custom_view_type` | `{"converted_lead": {"name": "Converted Lead", "show_list_only": True}}` |
| `pinned_view` | first pinned view for user/model | `PinnedView(...)` or `None` |
| `recently_viewed_option` | `self.recently_viewed_option` | `True` |
| `all_view_types` | `self.all_view_types` | `True` |
| `filter_option` | `self.filter_option` | `True` |
| `applied_filter_count` | computed from GET lists `field`, `operator` + `search` | `2` |
| `one_view_only` | `self.one_view_only` | `False` |
| `reload_option` | `self.reload_option` | `True` |
| `search_option` | `self.search_option` | `True` |
| `border_enabled` | `self.border_enabled` | `True` |
| `navbar_indication` | `self.navbar_indication` | `False` |
| `enable_actions` | `self.enable_actions` | `True` |
| `navbar_indication_attrs` | `get_navbar_indication_attrs()` returns dict or `None` | `{"data-test": "x"}` |

### Saved filter list dropdown

| Context key | How it is set | Example |
|---|---|---|
| `available_saved_filter_lists` | `SavedFilterList.all_objects` filtered by `model_name`, where `Q(user=request.user) | Q(is_public=True)` and ordered | `[SavedFilterList(...), ...]` |

---

## 🔌 Request GET parameters that affect navbar.py

| GET parameter | Used for | Example |
|---|---|---|
| `view_type` | selects dropdown view mode | `view_type=recently_viewed` |
| `layout` | selects effective layout icon/menu + action branching | `layout=kanban` |
| `search` | increments `applied_filter_count` and controls search field value | `search=Acme` |
| `field` (multi) | increments `applied_filter_count` for applied filters | `field=title&field=status` |
| `operator` (multi) | paired with `field` entries | `operator=contains&operator=equals` |
| `section` | not used directly in navbar.py, but often kept in URL patterns in layouts/actions | `section=sales` |
| Any other query params | preserved in navbar template when constructing hx-get URLs | `?status=open` |

---

## 🎛️ Subclass configuration: which attributes you usually set

Most application navbars subclass `HorillaNavView` and override only the attributes they need.

### Example: `LeadNavbar` (typical configuration)

```python
from functools import cached_property
from django.utils.decorators import method_decorator
from horilla.utils.decorators import htmx_required, permission_required_or_denied
from horilla_generics.views import HorillaNavView
from horilla.urls import reverse_lazy
from horilla_crm.leads.models import Lead
from horilla_crm.leads.filters import LeadFilter
from horilla.utils.translation import gettext_lazy as _


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(["leads.view_lead", "leads.view_own_lead"]),
    name="dispatch",
)
class LeadNavbar(HorillaNavView):
    nav_title = Lead._meta.verbose_name_plural
    search_url = reverse_lazy("leads:leads_list")
    main_url = reverse_lazy("leads:leads_view")
    filterset_class = LeadFilter

    kanban_url = reverse_lazy("leads:leads_kanban")
    group_by_url = reverse_lazy("leads:leads_group_by")
    card_url = reverse_lazy("leads:leads_card")
    split_view_url = reverse_lazy("leads:leads_split_view")
    chart_url = reverse_lazy("leads:leads_chart")
    timeline_url = reverse_lazy("leads:leads_timeline")

    model_name = "Lead"
    model_app_label = "leads"

    exclude_kanban_fields = "lead_owner"
    enable_actions = True
    enable_quick_filters = True
    column_selector_exclude_fields = ["message_id", "is_convert"]

    @cached_property
    def custom_view_type(self):
        return {
            "converted_lead": {"name": _("Converted Lead"), "show_list_only": True},
        }
```

### What each of those attributes does (mapped to context)

| Attribute on the subclass | Becomes in template context | Typical example |
|---|---|---|
| `nav_title` | `nav_title` | `"Leads"` |
| `search_url` | `search_url` | `reverse_lazy("leads:leads_list")` |
| `main_url` | `main_url` | `reverse_lazy("leads:leads_view")` |
| `kanban_url` | `kanban_url` | `reverse_lazy("leads:leads_kanban")` |
| `group_by_url` | `group_by_url` | `reverse_lazy("leads:leads_group_by")` |
| `card_url` | `card_url` | `reverse_lazy("leads:leads_card")` |
| `split_view_url` | `split_view_url` | `reverse_lazy("leads:leads_split_view")` |
| `chart_url` | `chart_url` | `reverse_lazy("leads:leads_chart")` |
| `timeline_url` | `timeline_url` + `timeline_settings_modal_url` | `reverse_lazy("leads:leads_timeline")` |
| `model_name` | `model_name` | `"Lead"` |
| `model_app_label` | `model_app_label` + permission strings for actions | `"leads"` |
| `custom_view_type` | `custom_view_type` + affects `view_type` valid values | `{"converted_lead": {...}}` |
| `enable_actions` | toggles `actions` generation | `True` |
| `enable_quick_filters` | toggles “Add Quick Filter” action in list layout | `True` |
| `exclude_kanban_fields` | used in kanban/group_by settings hx-get | `"lead_owner"` |
| `column_selector_exclude_fields` | used to build `column_selector_url` exclude query | `["message_id", "is_convert"]` |

---

## 🔥 Actions (optional): permissions + layout branching

If `enable_actions=False`, `context["actions"]` is always `[]`.

If `enable_actions=True`, navbar.py computes actions only when the current user has the right permissions:

- `view_perm = f"{model_app_label}.view_{model_name.lower()}"`
- `view_own_perm = f"{model_app_label}.view_own_{model_name.lower()}"`
- `can_create_perm = f"{model_app_label}.add_{model_name.lower()}"`

Actions are also dependent on effective `layout` (from GET `layout` or `default_layout`):
- `layout="kanban"` → “Kanban Settings”
- `layout="group_by"` (and `group_by_url` exists) → “Group By Settings”
- `layout="timeline"` (and timeline settings modal URL could be built) → “Timeline settings”
- `layout="list"` → “Add Column to List” and (optionally) “Add Quick Filter”

---

## 📌 Summary

To use `HorillaNavView` in your own navbar:
- set `model_name` and `model_app_label`
- set `nav_title`, `search_url`, and `main_url`
- optionally set layout URLs (`kanban_url`, `group_by_url`, `card_url`, `split_view_url`, `timeline_url`, `chart_url`)
- optionally set `enable_actions=True` and permissions-based settings keys (`exclude_kanban_fields`, `column_selector_exclude_fields`, etc.)
- optionally define `custom_view_type` to extend the view dropdown
