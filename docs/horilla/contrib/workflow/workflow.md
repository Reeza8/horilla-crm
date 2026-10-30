# Horilla Workflow app — deep dive (`horilla.contrib.workflow`)

## What this app does

- **`WorkflowRule`** — module (`HorillaContentType`), name, description, triggers on create/edit, active flag.
- **`WorkflowCondition`** — criteria rows (field / operator / value / logical operator).
- **`WorkflowAction`** / **`WorkflowTimeTriggerAction`** — actions on match (update field, task, email, notification) with JSON **`action_config`** built from hidden compose fields.
- Runs on record create/edit for models registered under the workflow feature registry (core models such as users, departments, and holidays, plus any app that calls `register_model_for_feature` with workflow enabled).

**Owner resolution for `assign_task` actions** tries common owner FK names in order: `owner`, `assigned_to`, `created_by`, then `lead_owner` for legacy CRM models.

---

## Forms (`forms.py`)

### `WorkflowRuleForm` (`HorillaModelForm`)

Uses the Horilla 1.10 layout pattern (see [single-step form base](../generics/forms/single_step.md)).

| Setting | Value |
|---------|--------|
| **`field_order`** | `name`, `model`, `description`, `trigger_on_create`, `trigger_on_edit`, `is_active` |
| **`Meta.fields`** | `"__all__"` |
| **`keep_on_form`** | `("is_active",)` |
| **`Meta.exclude`** | None — the model only exposes the fields above plus core audit columns (auto-excluded except `is_active` via `keep_on_form`) |

### Action / condition forms (unchanged layout)

These remain plain **`forms.ModelForm`** + **`ActionConfigMixin`** (not `fields = "__all__"`):

| Class | Model fields on form | Notes |
|-------|----------------------|--------|
| **`WorkflowConditionForm`** | `rule`, `field`, `operator`, `value`, `logical_operator`, `order` | Dynamic `field` choices in **`__init__`** |
| **`WorkflowActionForm`** | `rule`, `action_type`, `order` + hidden action-config fields | Injected in **`__init__`** |
| **`WorkflowTimeTriggerActionForm`** | delay fields + `action_type`, `order` + hidden config | Date-field choices from view |

---

## Conditions on fields that aren't model columns

`evaluate_workflow_condition` calls `evaluate_extension_condition` first (see [condition_fields.md](../generics/forms/condition_fields.md#conditionfieldprovider-extension-seam)); when an extension owns the field its value is compared as text with the workflow's `_compare_string_operator`, otherwise the model field is read as before. The condition field dropdown comes from the generic condition builders, which include extension fields. Rule detail pages show those values with `get_condition_value_display`.

---

## Related documentation

- Automations (similar condition/action patterns): [../automations/automations.md](../automations/automations.md)
- Form extension API: [../../extension/form_extension.md](../../extension/form_extension.md)
- Generics single-step forms: [../generics/forms/single_step.md](../generics/forms/single_step.md)
