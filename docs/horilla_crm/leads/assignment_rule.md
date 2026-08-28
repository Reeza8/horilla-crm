# Lead Assignment Rules (`horilla_crm.leads.views.assignment_rule`)

## What this module does

Defines class-based views for managing **lead assignment rules** — configurable rules that automatically assign incoming leads to users or roles based on matching conditions.

---

## View inventory

| View | Base | Purpose |
|------|------|---------|
| `LeadsAssignmentView` | `HorillaView` | Main shell — [settings list shell](../../horilla/contrib/core/settings_list_shell.md) |
| `LeadAssignmentNavbar` | `HorillaNavView` | Navigation bar with "Create Rule" action button |
| `LeadAssignmentListView` | `HorillaListView` | Rule list with edit/delete column actions |
| `LeadAssignmentActivateView` | `View` | HTMX POST — toggles `is_active` on a rule |
| `LeadAssignmentForm` | `HorillaSingleFormView` | Create/update a single assignment rule |
| `LeadAssignmentDelete` | `HorillaSingleDeleteView` | Delete an assignment rule |
| `AssignmentRuleDetailView` | `DetailView` | Detail page showing rule + its conditions list |
| `AssignmentRuleDetailNavbar` | `HorillaNavView` | Navbar for the detail page |
| `AssignmentConditionFormView` | `HorillaSingleFormView` | Create/update a single condition row tied to a rule |
| `ToggleAssignToFieldView` | `TemplateView` | HTMX partial — swaps between `assign_to_users` and `assign_to_roles` widgets |
| `ToggleNotifyMethodFieldView` | `TemplateView` | HTMX partial — swaps between mail template and notification template widgets |
| `AssignmentConditionDeleteView` | `HorillaSingleDeleteView` | Delete one condition; triggers HTMX refresh on the detail page |

---

## Key patterns

### Conditional field toggling

`ToggleAssignToFieldView` and `ToggleNotifyMethodFieldView` are lightweight `TemplateView` endpoints that return only a field partial. The form calls them via HTMX when the user changes the assignment type or notification method, swapping the visible field without re-rendering the full modal.

### Rule pre-fill in condition form

`AssignmentConditionFormView` reads `rule_pk` from GET params and pre-fills the `rule` FK in the form's initial data. This allows opening the condition form directly from the rule detail page without manual input.

### Dynamic `model_name` initialisation

The condition form resolves field choices based on the parent rule's target model. `AssignmentConditionFormView.get_initial()` extracts `model_name` from the rule instance and injects it into form initial so field selector widgets load the correct column list.

### Missing object handling

- **HTMX requests** on a missing object → **`RefreshResponse`** (`horilla.web`) — HTMX-aware partial refresh.
- **Non-HTMX requests** on a missing object → **`HttpNotFound`** (`horilla.web`) — standard 404 page.

### Condition delete refresh

`AssignmentConditionDeleteView.delete()` returns an HTMX response that triggers a reload of the conditions list partial, keeping the detail page reactive.

---

## URL names (reference)

All URLs are namespaced under `leads:`.

| Name | Pattern | View |
|------|---------|------|
| `leads:assignment_rule_view` | `assignment-rules/` | `LeadsAssignmentView` |
| `leads:assignment_rule_list` | `assignment-rules/list/` | `LeadAssignmentListView` |
| `leads:assignment_rule_form` | `assignment-rules/form/` | `LeadAssignmentForm` |
| `leads:assignment_rule_form` | `assignment-rules/form/<int:pk>/` | `LeadAssignmentForm` (update) |
| `leads:assignment_rule_delete` | `assignment-rules/delete/<int:pk>/` | `LeadAssignmentDelete` |
| `leads:assignment_rule_detail` | `assignment-rules/detail/<int:pk>/` | `AssignmentRuleDetailView` |
| `leads:assignment_condition_form` | `assignment-conditions/form/` | `AssignmentConditionFormView` |
| `leads:assignment_condition_delete` | `assignment-conditions/delete/<int:pk>/` | `AssignmentConditionDeleteView` |

---

## Related documentation

- [Lead stages](lead_stages.md)
- `HorillaSingleFormView`: [../../horilla/contrib/generics/views/single_form.md](../../horilla/contrib/generics/views/single_form.md)
- `HorillaListView`: [../../horilla/contrib/generics/views/list.md](../../horilla/contrib/generics/views/list.md)
- Permission model (four layers): [../../horilla/contrib/generics/mixins.md](../../horilla/contrib/generics/mixins.md)
