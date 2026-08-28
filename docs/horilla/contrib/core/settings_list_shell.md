# Settings list shell (`settings/settings_list_shell.html`)

Shared HTMX layout for **Settings → list** pages (roles, branches, lead stages, mail templates, automations, and similar). Introduced to deduplicate the repeated `#navBar` + `#mainSession` pattern across ~30 settings modules.

---

## Template structure

Extends `settings/settings.html` and defines:

| Element | ID | HTMX load |
|---------|-----|-----------|
| Navbar partial | `#navBar` | `hx-get="{{ nav_url }}"` on `load` |
| Main content | `#mainSession` | `hx-get="{{ layout_url }}"` on `load` |

Optional query passthrough: `{{ request.GET.urlencode }}` on both requests. When the navbar filter form triggers a reload, `filter_form` is appended so the list partial can react.

```django
{% extends "settings/settings.html" %}
{% block settings %}
    <div id="{{ view_id|default:'settings-view' }}" class="h-full flex flex-col">
        {% include "messages.html" %}
        <div id="navBar" hx-get="{{ nav_url }}?..." hx-trigger="load"></div>
        <div id="mainSession" hx-get="{{ layout_url }}?..." hx-trigger="load"></div>
    </div>
{% endblock %}
```

---

## View wiring (`HorillaView`)

Subclass **`HorillaView`** and set:

| Attribute | Required | Purpose |
|-----------|----------|---------|
| `template_name` | Yes | `"settings/settings_list_shell.html"` |
| `nav_url` | Yes | HTMX endpoint for navbar (`HorillaNavView`) |
| `list_url` | Usually | Default layout loaded into `#mainSession` |
| `view_id` | Recommended | Stable root element id (e.g. `leads-status-view`) |

`HorillaView.get_layout_url()` picks `list_url`, or another layout URL when `?layout=` is present (kanban, group_by, etc.). Settings pages typically expose only `list_url`.

### Example (lead stages)

```python
class LeadsStageView(LoginRequiredMixin, HorillaView):
    template_name = "settings/settings_list_shell.html"
    view_id = "leads-status-view"
    nav_url = reverse_lazy("leads:lead_stage_nav_view")
    list_url = reverse_lazy("leads:lead_stage_list_view")
```

### Example (matching rules — core contrib)

```python
class MatchingRulesView(LoginRequiredMixin, HorillaView):
    template_name = "settings/settings_list_shell.html"
    view_id = "matching-rules-view"
    nav_url = reverse_lazy("duplicates:matching_rules_nav")
    list_url = reverse_lazy("duplicates:matching_rules_list")
```

---

## Modules using this shell (v1.13.7)

Includes: `horilla.contrib.core` (roles, branches, departments, recycle bin, team/partner/customer roles), `horilla.contrib.mail`, `horilla.contrib.notifications`, `horilla.contrib.automations`, `horilla.contrib.workflow`, `horilla.contrib.cadences`, `horilla.contrib.duplicates`, `horilla.contrib.process`, and CRM apps (`leads`, `opportunities`, `forecast`, `scoring_rules`).

When adding a new settings list page, prefer this shell over copying navbar/list HTMX markup.

---

## Related documentation

- [`HorillaView`](../generics/views/core.md#-horillaview)
- [Core app index](core_app.md)
