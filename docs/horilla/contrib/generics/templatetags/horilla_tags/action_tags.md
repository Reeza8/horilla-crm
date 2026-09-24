# Action permission tags (`horilla_generics/templatetags/horilla_tags/action_tags.py`)
## Purpose
`action_tags.py` provides template tags and helpers that decide whether row-level UI actions should be shown to the current user.
It supports:
- direct object permission checks
- owner-based permissions (`own_permission`)
- multi-permission logic (`permissions` with `OR`/`AND`)
- intermediate-model permission checks (for bridged relationships)
- queryset-level fast check to decide if Actions column should render
---
## Why this module matters
Action buttons in list/detail templates often need conditional visibility based on user permissions and ownership.
Without centralized logic:
- permission checks become duplicated in templates,
- intermediate-model cases become brittle,
- action columns may appear even when no action is actually usable.
This module centralizes those decisions and exposes template tags for clean UI control.
---
## Core helper functions
## `get_app_labels_from_context(related_obj, request, action=None)`
Builds an ordered list of app labels to try when resolving intermediate model names dynamically.
Priority order (deduplicated):
1. `action["intermediate_app_label"]` (if provided)
2. `related_obj._meta.app_label`
3. current view model app label (via `resolver_match.func.view_class.model`)
4. URL-derived app hints:
   - namespace prefix in `url_name`
   - prefix before `_` in plain `url_name`
5. `resolver_match.namespace`
6. all installed app labels (fallback)
Why:
- actions may be configured with model names only,
- this list gives best-effort model lookup across apps.
---
## `get_intermediate_instance(action, related_obj, request)`
Resolves an intermediate/bridge model row for permission checks.
Required action config keys:
- `intermediate_model` (model name)
- `intermediate_field` (FK to related object)
- `parent_field` (FK to parent object from URL `pk`)
Flow:
1. get parent `pk` from `request.resolver_match.kwargs`
2. resolve intermediate model class by trying app labels from `get_app_labels_from_context(...)`
3. build filter:
   - `{intermediate_field: related_obj, f"{parent_field}_id": parent_id}`
4. fetch first matching intermediate object
Returns:
- intermediate instance or `None`.
Logs warnings/errors for unresolved models or invalid config.
---
## `has_action_permission(action, context)`
Main permission evaluator.
Expected context keys:
- `user`
- `object`
- optional `intermediate_object`
Supported action keys:
- `permission` (single global permission)
- `permissions` (list)
- `permission_logic` (`OR` or `AND`)
- `own_permission`
- `owner_field` (string or list)
- `owner_method` (callable method name on target object)
- `intermediate_model` (switches target to `intermediate_object` when available)
---
### Evaluation order
1. **short-circuit allow**
   - if no permission constraints configured, allow
   - superuser always allow
2. **configuration validation**
   - if `own_permission` set without owner resolver (`owner_field`/`owner_method`) -> raise `ValueError`
   - if both `owner_field` and `owner_method` set -> raise `ValueError`
3. **single permission**
   - if `permission` exists and user has it -> allow
4. **multi-permission list**
   - evaluate `permissions` by `permission_logic`:
     - `OR`: any true
     - `AND`: all true
   - invalid logic value -> raise `ValueError`
5. **owner path (`own_permission`)**
   - target object is intermediate object when configured/found, else main object
   - `owner_method` path:
     - call method with user, require truthy + `own_permission`
   - `owner_field` path:
     - supports one field or list
     - owner match + `own_permission` -> allow
     - allowed owner IDs come from `get_allowed_user_ids(user)`
       (`horilla.contrib.core.utils`), which walks the role hierarchy; its result is
       cached per request per user (`request._allowed_user_ids_cache`) so it is
       computed once even though this evaluator runs once per `owner_field` action
       per row.
6. otherwise deny.
---
## Template tags
## `filter_actions_by_permission` (simple_tag, takes context)
Signature:
- `filter_actions_by_permission(context, actions, data)`
Behavior:
1. resolve `request` and `user` from template context
2. for each action:
   - build action context with object
   - if intermediate model configured, resolve intermediate instance
   - evaluate with `has_action_permission(...)`
3. return filtered action list
Typical usage:
- template iterates only allowed actions for each row.
---
## `resolve_row_actions` (simple_tag, takes context)
Signature:
- `resolve_row_actions(context, actions, data, queryset)`
Purpose:
- like `filter_actions_by_permission`, but for the main (non-dropdown) row-action
  icons: instead of dropping an action a row can't perform, it keeps the action
  visible-but-disabled as long as *some* row in the current page's `queryset`
  would be allowed to use it — so the action column doesn't shift per row.
Behavior:
1. for each action: skip if `hidden_if(data)` is true.
2. if `has_action_permission` passes for this row, keep the action as-is.
3. otherwise, call `_any_row_allows(action, user, queryset, request)`; if no row on
   the page allows it, drop the action entirely; if at least one does, keep it with
   `disabled_if` forced to `True`.
Caching:
- `_any_row_allows` scans the whole page `queryset` calling `has_action_permission`
  per object — expensive to repeat once per row. Its result is cached on the
  request (`request._any_row_allows_cache`), keyed by `(id(action), id(queryset),
  user.pk)`, so the scan runs at most once per action per request instead of once
  per row whose own permission check fails.
---
## `has_any_actions_for_queryset` (simple_tag, takes context)
Signature:
- `has_any_actions_for_queryset(context, actions, queryset)`
Purpose:
- determines if at least one row has at least one visible action,
- used to decide whether to render Actions column in table header.
Optimization strategy:
1. if user missing or actions empty -> `False`
2. fast short-circuit:
   - if any action has direct `permission` and user has it -> `True`
3. sample-based row check:
   - inspect up to first 10 queryset rows
   - evaluate each action via `has_action_permission`
   - return `True` on first match
4. return `False` if no match.
Note:
- sample-based approach trades exactness for performance on large querysets.
---
## Action configuration patterns
## Pattern 1: simple permission
```python
{
  "action": "edit",
  "permission": "crm.change_lead",
}
```
## Pattern 2: owner-based action
```python
{
  "action": "edit_own",
  "own_permission": "crm.change_own_lead",
  "owner_field": "owner",
}
```
Or with method:
```python
{
  "action": "edit_own",
  "own_permission": "crm.change_own_lead",
  "owner_method": "is_owned_by",
}
```
## Pattern 3: multiple permissions
```python
{
  "action": "advanced",
  "permissions": ["crm.change_lead", "crm.approve_lead"],
  "permission_logic": "AND",
}
```
## Pattern 4: intermediate model permission target
```python
{
  "action": "remove_member",
  "intermediate_model": "CampaignMember",
  "intermediate_field": "member",
  "parent_field": "campaign",
  "own_permission": "campaign.change_own_campaignmember",
  "owner_field": "created_by",
}
```
---
## Template usage examples
### Filter per-row actions
```django
{% load horilla_tags %}
{% filter_actions_by_permission actions row_obj as allowed_actions %}
```
### Conditionally render Actions header
```django
{% load horilla_tags %}
{% has_any_actions_for_queryset actions object_list as show_actions %}
{% if show_actions %}
  <th>Actions</th>
{% endif %}
```
---
## Error handling and safety
- intermediate model resolution failures are logged and treated as no intermediate object.
- misconfigured owner permission schemas raise explicit `ValueError` (fail-fast for developer errors).
- missing request/user in template context yields safe defaults (`[]` / `False`).
---
## Caveats
- `has_any_actions_for_queryset` checks only first 10 rows; rare permissions in later rows may be missed for header decision.
- intermediate model lookup depends on configuration correctness (`intermediate_model`, `intermediate_field`, `parent_field`).
- when both global and owner permissions are configured, global checks can short-circuit before owner checks.
---
## Summary
`action_tags.py` is the authorization-aware action visibility engine for templates. It combines direct permissions, owner checks, multi-permission logic, and intermediate-model resolution into reusable tags that keep action rendering consistent and secure across Horilla UI tables and lists.
