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

### Matching against Lead custom fields

A `LeadAssignmentMatchCriteria.field` isn't limited to real `Lead` model columns — it can also be a synthetic `cf_<id>` field for a user-defined custom field (the `custom_fields` app). This is not special-cased here or in `horilla_crm.leads.models.assignment_rules`/`horilla_crm.leads.signals`; all three go through the generic **condition-field extension registry** in [`condition_fields.py`](../../horilla/contrib/generics/forms/condition_fields.md#condition-field-extension-registry), so this app never imports `custom_fields` directly:

- **Field dropdown** — `get_model_field_choices()` (used to build `condition_field_choices["field"]`) appends any `cf_<id>` choices contributed by a registered extension.
- **Value widget/operators** — `condition_widget.py` renders the appropriate input (e.g. a `select` for a Choice-type custom field) via `get_condition_field_widget_info()`; see [condition_widget.md](../../horilla/contrib/generics/views/helpers/condition_widget.md#synthetic-non-model-fields).
- **Display** — `LeadAssignmentMatchCriteria.get_field_label()` uses `get_condition_field_label()` for the "Field" column instead of `Lead._meta.get_field(...).verbose_name`.
- **Evaluation** — `horilla_crm.leads.signals._eval_single_criterion()` uses `get_condition_field_value(field, lead)` instead of `getattr(lead, field)` whenever `get_condition_field_extension(field)` returns an owner; `None` means "can't resolve, treat as no match", matching how an unknown real field is handled.

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
- Condition-field extension registry (custom-field matching): [../../horilla/contrib/generics/forms/condition_fields.md](../../horilla/contrib/generics/forms/condition_fields.md#condition-field-extension-registry)
- Condition value widgets: [../../horilla/contrib/generics/views/helpers/condition_widget.md](../../horilla/contrib/generics/views/helpers/condition_widget.md)
