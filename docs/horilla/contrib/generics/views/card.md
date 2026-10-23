# Horilla Card View (`horilla_generics/views/card.py`)

## 🎯 Purpose

`HorillaCardView` is a **ListView-like** view that renders list data as a **grid of cards** (tiles).

It reuses `HorillaListView` queryset/filter/search/action behavior, but switches:
- template from the list/table layout to the card layout (`card_view.html`)
- HTMX “load more” behavior to load additional cards via a partial (`partials/card_view_load_more.html`)

---

## 📦 Module location

```text
horilla_generics/views/
└── card.py
horilla_generics/templates/
├── card_view.html
└── partials/
    ├── card_view_cards.html
    └── card_view_load_more.html
```

---

## 🔁 Main class: `HorillaCardView`

### 📍 Definition (summary)

```python
class HorillaCardView(HorillaListView):
    template_name = "card_view.html"
    paginate_by = 24
    bulk_select_option = False
    table_class = False
    table_width = False
```

### 🎯 What it changes vs `HorillaListView`

- Uses `template_name = "card_view.html"` for normal requests.
- Uses `render_to_response()` override to support:
  - full card page renders
  - HTMX infinite-scroll “load more” via partials
- Sets card-specific defaults:
  - `paginate_by = 24` (how many cards per page)
  - disables bulk/table styling flags (`bulk_select_option=False`, `table_class=False`, `table_width=False`)

---

## ⚙️ `render_to_response()` behavior

### 📍 Function signature

```python
def render_to_response(self, context, **response_kwargs):
    ...
```

### ✅ Step-by-step behavior

1. Detect HTMX:
   - `is_htmx = self.request.headers.get("HX-Request") == "true"`
2. Add/override:
   - `context["request_params"] = self.request.GET.copy()`
3. If HTMX:
   - `page_kwarg = getattr(self, "page_kwarg", "page")`
   - if `self.request.GET.get(page_kwarg)` is present:
     - render `partials/card_view_load_more.html` via `render_to_string(...)`
     - return `HttpResponse(html)`
   - else:
     - render full template via `render(self.request, "card_view.html", context)`
4. If not HTMX:
   - delegates to `super(HorillaListView, self).render_to_response(...)`

---

## 🎨 Templates and required context

Card rendering is split into:
- `card_view.html` (page wrapper + “no records” UI)
- `partials/card_view_cards.html` (renders each card + HTMX sentinel)
- `partials/card_view_load_more.html` (wraps `card_view_cards.html` for HTMX load-more)

Below are the context variables used directly in these templates.

---

## 📍 `card_view.html` context variables (with examples)

### Wrapper & reload

| Context variable | Where used | Example value |
|---|---|---|
| `view_id` | wrapper div id: `id="{{ view_id|safe }}"` and hx-target | `"leads-card-view"` |
| `filter_reload_url` | `data-filter-reload-url` if provided | `"/leads/lead-view/?status=open&view_type=all"` |
| (fallback) `request.path` | used when `filter_reload_url` is missing | `"/leads/leads_view/"` |
| `request` | many template accesses: `request.GET.urlencode`, `request.path` | Django request object |

### Filtering/UI includes

| Context variable | Where used | Example value |
|---|---|---|
| `filter_set_class` | `{% if filter_set_class %}{% include "filterpanel.html" %}` | `LeadFilter` (a FilterSet class) or `None` |
| `enable_quick_filters` | includes quick filters bar | `True` |

### Data / empty state

| Context variable | Where used | Example value |
|---|---|---|
| `queryset` | `{% if queryset %}` + card rendering block | `QuerySet[Lead]` |
| `no_record_section` | controls whether “empty section” spacer is shown | `True` |
| `view_type` | saved_list block + empty-message behavior | `"all"` or `"saved_list_12"` |
| `model_verbose_name` | empty-message text | `"Leads"` |
| `no_record_msg` | overrides empty message when set | `"No leads found for the selected filters."` |
| `no_found_img` | used as image path fallback | `"assets/img/not-found.svg"` (or empty to default) |

### Saved filter list empty-state controls

`HorillaListView` sets these keys when `view_type` starts with `saved_list_...`.

| Context variable | Where used | Example value |
|---|---|---|
| `saved_list_name` | shown in empty state text via `blocktrans with view=saved_list_name` | `"My Public Filters"` |
| `saved_list_is_owner` | decides whether to show “Delete List” button | `True` |

### “Add new” button (empty state)

`HorillaListView` provides `no_record_add_button`.

| Context variable | Where used | Example value |
|---|---|---|
| `no_record_add_button` | button hx-get attrs | `{ "url": "/leads/create/?new=true", "target": "#modalBox", "swap": "innerHTML", "onclick": "openModal()", "class": "...", "attrs": '...' , "title": "Add New" }` |

### URL used for delete saved list

| Context variable | Where used | Example value |
|---|---|---|
| `main_url` | `hx-vals` for delete list modal | `"/leads/leads_view/"` |

---

## 📍 `partials/card_view_cards.html` context variables (with examples)

This partial iterates cards and renders a **pagination sentinel** for HTMX.

| Context variable | Where used | Example value |
|---|---|---|
| `queryset` | `{% for data in queryset %}` | `QuerySet[Lead]` |
| `columns` | used to decide what fields display per card | `[("Title","title"), ("Status","status"), ...]` |
| `col_attrs` | maps `field_key -> attrs` (permissions, hx-get, etc.) | `[{ "title": { "hx-get": "…", "permission": "leads.view_lead", ... } }]` (format depends on your list view column attrs generation) |
| `visible_actions` | dropdown actions per card | `[{ "action": "Edit", "attrs": 'hx-get="..."', ... }, ...]` |
| `view_id` | hx-select/hx-target selectors + sentinel list | `"leads-card-view"` |
| `has_next` | sentinel render toggle | `True` |
| `next_page` | used for sentinel hx-get page number | `3` |
| `search_params` | appended to hx-get query string | `"status=open&field=title&operator=icontains"` |
| `request` | `request.path` and theme/color access | Django request object with `active_company` |

### Request-dependent fields (via `request.active_company`)

The partial uses:
- `request.active_company.companytheme_set.first.theme.primary_400`
- `request.active_company.companytheme_set.first.theme.primary_600`

Example:
- `primary_400 = "#F7C8C1"`
- `primary_600 = "#E54F38"`

If missing, the template falls back to:
- `#F7C8C1` / `#E54F38` via `|default`.

---

## 📍 `partials/card_view_load_more.html` context variables

It just wraps `card_view_cards.html` and therefore needs:
- `view_id`
- all variables required by `card_view_cards.html` (`queryset`, `columns`, `col_attrs`, `visible_actions`, `has_next`, etc.)

`HorillaCardView.render_to_response()` calls:
- `render_to_string("partials/card_view_load_more.html", context, request=self.request)`

So `request` is explicitly passed to the template rendering call.

---

## 🧪 Usage example (subclass like other Navbar/List views)

Your app usually subclasses `HorillaCardView` through a list view or replaces only `template_name`/pagination via inheritance.

Example skeleton:

```python
from horilla.urls import reverse_lazy
from horilla_generics.views.card import HorillaCardView
from horilla_crm.leads.models import Lead
from horilla_crm.leads.filters import LeadFilter


class LeadCardView(HorillaCardView):
    model = Lead
    view_id = "leads-card-view"

    search_url = reverse_lazy("leads:leads_list")
    main_url = reverse_lazy("leads:leads_view")
    filterset_class = LeadFilter

    enable_quick_filters = True
    enable_actions = True

    # Used by empty state
    no_record_section = True
    no_record_msg = "No leads match your filters."

    # Used by empty state "Add New" button
    no_record_add_button = {
        "url": f"{reverse_lazy('leads:leads_create')}?new=true",
        "target": "#modalBox",
        "swap": "innerHTML",
        "onclick": "openModal()",
        "class": "bg-primary-600 rounded-md hover:bg-primary-800 transition duration-300 text-white text-sm px-4 py-2 m-auto flex",
        "attrs": "",
        "title": "Add New",
    }
```

Once you route this view and load it in your pages:
- HTMX requests with `HX-Request: true` and a `page` query param will load more cards via `card_view_load_more.html`.
- Normal GET requests render `card_view.html`.

---

## 📌 Summary

- Use `HorillaCardView` to render `HorillaListView` data as cards.
- `card_view.html` + `partials/card_view_cards.html` define the required template context.
- The view sets:
  - `template_name = "card_view.html"`
  - `paginate_by = 24`
  - HTMX “load more” partial rendering when a page query param is present.
