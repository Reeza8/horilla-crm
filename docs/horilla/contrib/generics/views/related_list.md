# Related list views (`horilla_generics/views/related_list.py`)

## Purpose

This module powers the **Related Lists** tab in detail pages.

It provides:

1. `HorillaRelatedListSectionView` — discovers/builds related-list metadata and full list blocks.
2. `HorillaRelatedListContentView` — HTMX endpoint that loads one related list block on demand.

The key design goal is flexibility: each subclass can configure related lists differently depending on domain needs (simple reverse relations, intermediate models, custom queryset, custom actions/buttons, permissions, etc.).

---

## Architecture

### `HorillaRelatedListSectionView`

Base class for per-model related-list tabs.

Core attributes:

| Attribute | Default | Role |
| ----------- | --------- | ------ |
| `template_name` | `related_list.html` | Wrapper tab template. |
| `related_list_config` | `{}` | Per-subclass config for standard + custom related lists. |
| `max_items_per_list` | `None` | Optional cap per list block. |
| `excluded_related_lists` | `[]` | Exclude unwanted auto-discovered reverse relations. |

Also auto-registers subclasses in `_view_registry[model]` for lookup by `HorillaRelatedListContentView`.

Caches the parent via `get_object()` / `self.object` so `dispatch`, metadata, and `_can_add_to_related()` do not re-query the same row. `_can_add_to_related()` lives on the base class (CRM subclasses no longer `Model.objects.get` again).

### `HorillaRelatedListContentView`

HTMX content loader for one related list:

- resolves parent model from `class_name` registry when possible (avoids ContentType), else `model_name` via `HorillaContentType`,
- caches `get_queryset()` for the request,
- sets `parent_view.object` so config/`_can_add_to_related` reuse the loaded parent,
- calls `get_single_related_list(object, field_name)`,
- renders `related_list_content.html`.

---

## Two list types you can configure

## 1) Standard related fields (auto-discovered)

Auto-discovery scans `obj._meta.get_fields()` and includes fields that are:

- `one_to_many`
- `many_to_many`
- `GenericRelation`

excluding hidden/internal/audit names and `excluded_related_lists`.

For each standard field, config is read from:

```python
related_list_config.get(field.name, {})
```

So you can override only selected reverse fields.

## 2) Custom related lists (`custom_related_lists`)

Configured under:

```python
related_list_config = {
    "custom_related_lists": {
        "my_list_name": {
            "app_label": "...",
            "model_name": "...",
            # either queryset function OR intermediate pattern
            "queryset": callable,  # optional
            "related_field": "...",  # optional
            "intermediate_field": "...",  # optional
            "intermediate_model": "...",  # optional
            "config": {...}
        }
    }
}
```

Use this when relation is not a direct reverse field, or when you need special query/annotation logic.

---

## Metadata vs content methods

### `get_related_lists_metadata()`

Returns lightweight list descriptors for tab navigation:

- name, title, model_name, app_label, parent_model_name
- `is_custom`
- config references

### `get_related_lists()`

Returns fully built related list data for all discoverable/custom lists.

### `get_single_related_list(obj, field_name)`

Returns one list block payload, handling both:

- standard fields via `build_related_list_data`
- custom fields via `build_custom_related_list_data`

Used by `HorillaRelatedListContentView` for lazy loading.

---

## Standard related list builder

`build_related_list_data(obj, field)`:

1. gets related manager/queryset from `getattr(obj, field.name)`.
2. counts total records.
3. reads config for this field:
   - `title`, `columns`, `actions`, `dropdown_actions`, `custom_buttons`, `can_add`, `add_url`, etc.
4. builds a temporary `HorillaListView` configured for embedded mode.
5. renders `list_view.html` as HTML string.
6. returns a normalized data dict for template.

Embedded list defaults include:

- `bulk_select_option=False`
- `filterset_class=None`
- `table_width=False`
- `table_class=False`
- `owner_filtration=False` (important for related list scope)

---

## Custom related list builder

`build_custom_related_list_data(obj, custom_name, custom_config)` supports **three patterns**:

### Pattern A: explicit queryset callable

```python
"queryset": lambda obj: SomeModel.objects.filter(...)
```

Use for fully custom logic.

### Pattern B: intermediate model bridge

For many-to-many-through or relationship tables:

- `related_field`: field on intermediate model pointing to parent object
- `intermediate_field`: relation path used for fallback filtering
- `intermediate_model`: optional model name for robust resolution across apps

The builder:

1. locates intermediate model,
2. filters bridge rows by parent object,
3. finds bridge field pointing to related model,
4. extracts related IDs,
5. queries related model by those IDs,
6. optionally annotates extra columns from intermediate model (`_build_intermediate_annotations`).

### Pattern C: fallback relation path

When intermediate model resolution fails, uses:

```python
related_model.objects.filter(**{f"{intermediate_field}__{related_field}": obj})
```

---

## How embedded list view is prepared

`create_generic_list_view_instance(...)` configures an in-memory `HorillaListView` for each related list.

Notable behavior:

- computes section (`get_section_info_for_model`) and injects `section=...` into `hx-get/hx-post/hx-delete/href` in `col_attrs` to preserve UI section context.
- applies configured columns/actions/action_method/col_attrs.
- sets `view_id` to `<related-name>-content`.

`render_generic_list_view(...)` then:

1. runs `list_view.get_queryset()` (including sort behavior),
2. sets `object_list`,
3. gets context,
4. renders HTML via `render_to_string`.

---

## Column resolution rules

`get_columns_for_model(model, config)`:

- if `config["columns"]` exists -> use it directly.
- else auto-pick up to first 5 fields excluding default audit/meta list + `config["exclude"]`.

This lets each related list choose:

- explicit domain-specific columns, or
- generic fallback columns.

---

## Subclass config patterns (detailed examples)

Below are patterns seen in the repo where each module configures related lists differently.

## Case 1: Minimal/standard related lists + exclusions

Use default auto-discovery and only hide noisy relations.

```python
class ContactRelatedListsTab(HorillaRelatedListSectionView):
    model = Contact
    excluded_related_lists = [
        "opportunity_roles",
        "contact_campaign_members",
        "account_relationships",
    ]
```

When to use:

- mostly direct reverse relations are sufficient,
- only a few relations should be hidden.

---

## Case 2: Custom related list via intermediate model

From opportunities/leads/contacts/account patterns:

```python
related_list_config = {
    "custom_related_lists": {
        "contact": {
            "app_label": "contacts",
            "model_name": "Contact",
            "intermediate_model": "OpportunityContactRole",
            "intermediate_field": "contact",
            "related_field": "opportunity",
            "config": {
                "title": _("Contact Roles"),
                "columns": [
                    ("First Name", "first_name"),
                    ("Last Name", "last_name"),
                    ("Role", "opportunity_roles__role"),
                ],
                "can_add": True,
                "add_url": reverse_lazy("opportunities:add_opportunity_contact_role"),
                "actions": [...],
                "col_attrs": [...],
            },
        }
    }
}
```

When to use:

- parent <-> child relation exists through bridge model,
- need columns coming from both child + bridge table,
- need relationship-specific actions (edit/delete relation row).

---

## Case 3: Permission-gated custom list

In `LeadRelatedLists`, config is returned only if user has permissions:

```python
if not can_view_members:
    return {"custom_related_lists": {}}
```

When to use:

- entire related list tab item should disappear for unauthorized users.

---

## Case 4: Custom buttons in header

Accounts related contacts example builds contextual button groups:

```python
"custom_buttons": [
    {
        "label": _("New Contact"),
        "url": reverse_lazy("contacts:related_account_contact_create_form"),
        "attrs": 'hx-target="#modalBox" ...',
        "icon": "fa-solid fa-user-plus",
        "class": "...",
    },
    ...
]
```

When to use:

- list needs additional non-row actions (add relation, launch helper forms).

---

## Case 5: Add button + ownership-aware conditions

Patterns like:

```python
"can_add": user.has_perm("campaigns.add_campaignmember") and (
    (is_owner(Lead, pk) and user.has_perm("leads.change_own_lead"))
    or user.has_perm("leads.change_lead")
),
"add_url": reverse_lazy("campaigns:add_to_campaign")
```

When to use:

- creation of related record should be allowed only when parent edit permissions are satisfied.

---

## Case 6: Rich row actions with relation-specific URLs

Actions often include placeholders resolved by row object methods:

```python
"actions": [
    {
        "action": "edit",
        "permission": "...",
        "own_permission": "...",
        "owner_field": "created_by",
        "attrs": """
            hx-get="{get_specific_member_edit_url}"
            hx-target="#modalBox"
            hx-swap="innerHTML"
            onclick="openModal()"
        """,
    },
    ...
]
```

When to use:

- each row has domain-specific edit/delete endpoints,
- permissions differ by action.

---

## Case 7: `col_attrs` for click-to-detail + section preservation

Common pattern:

```python
"col_attrs": [
    {
        "campaign_name": {
            "hx-get": "{get_detail_view_url}?referrer_app=...&section=...",
            "hx-target": "#mainContent",
            "hx-swap": "outerHTML",
            "hx-push-url": "true",
            "hx-select": "#mainContent",
        }
    }
]
```

The base class also auto-injects `section` parameter into link attrs for consistency.

---

## Case 8: Standard field override (non-custom)

You can target a direct reverse field by name:

```python
related_list_config = {
    "tasks": {
        "title": _("Open Tasks"),
        "columns": [("Subject", "subject"), ("Status", "status")],
        "exclude": ["internal_notes"],
        "actions": [...],
    }
}
```

No custom list registration needed — this decorates auto-discovered relation `tasks`.

---

## HTMX loading flow (single tab click)

1. UI requests `horilla_generics:related_list_content` with `pk`, `model_name`, `field_name`, `class_name`.
2. `HorillaRelatedListContentView` resolves parent model via `HorillaContentType`.
3. Picks registered section subclass from `_view_registry`.
4. Builds one related list payload via `get_single_related_list`.
5. Renders `related_list_content.html`.

---

## Recommended subclass checklist

- set `model`.
- decide exclusions: `excluded_related_lists`.
- decide whether config needs `@cached_property` (recommended when building dynamic URLs/permissions).
- for each custom list, choose one pattern:
  - `queryset` callable,
  - intermediate model mapping,
  - direct relation override.
- define `columns` explicitly when relation + intermediate fields are mixed.
- include permission keys for actions and optional `can_add`.
- include `col_attrs` for click-through UX if needed.

---

## Related routes/templates

Routes:

- `horilla_generics:related_list_content` (`related-list-content/<int:pk>/`)

Templates:

- `related_list.html` (tab wrapper and list metadata UI)
- `related_list_content.html` (single list content response)
- `list_view.html` (embedded list renderer)

---

## Summary

`related_list.py` gives a reusable related-list engine where subclasses can be as simple as "auto-discover + exclude" or as advanced as "bridge-model annotations + dynamic actions + custom buttons + ownership-gated add flows". This is why each app config looks different: the base is intentionally composable per domain workflow.
