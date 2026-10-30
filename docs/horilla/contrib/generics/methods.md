# Helper methods (`horilla_generics/methods.py`)
## Purpose
`horilla/contrib/generics/methods.py` provides:
- `get_dynamic_form_for_model(model)` — runtime form-class generation
- `get_condition_value_display(model_cls, field_name, value)` — readable text for a stored condition value
This helper is used when code needs a `ModelForm` for a model dynamically (without writing a dedicated static form class).
---
## Function reference
## `get_dynamic_form_for_model(model)`
Returns a dynamically created form class:
```python
class ResolvedDynamicForm(OwnerQuerysetMixin, HorillaModelForm):
class Meta:
  model = _model
  fields = "__all__"
  exclude = [
      "created_at",
      "updated_at",
      "created_by",
      "updated_by",
      "additional_info",
  ]
```
### Why `_model = model` is used
The function captures the incoming model in a local variable before class definition:
- `model = _model` inside `Meta` then binds correctly to this call’s target model.
This avoids accidental late-binding confusion when generating dynamic classes.
---
## `get_condition_value_display(model_cls, field_name, value)`
Turns a stored condition `value` into display text: for a relation field it returns `str()` of the related record with that pk, for a choice field the choice label. Anything else (empty input, unknown field, unresolved pk/key) is returned unchanged. It lives here (moved from `forms/condition_fields.py`).
---
## Inheritance behavior
`ResolvedDynamicForm` inherits:
- `OwnerQuerysetMixin`
- `HorillaModelForm`
### `OwnerQuerysetMixin` role
Filters User-related FK/M2M fields by the current user's permission level and role hierarchy:

- **Superuser / `change`/`add` perm** — full `User.objects.all()` queryset.
- **`change_own`/`add_own` perm** — current user + recursive subordinates (via `role.subroles`).
- **No matching perm** — only the requesting user.

Additionally, the queryset is scoped to the **active company**: when a company is resolved (from the edited object, the request's `active_company`, or `request.user.company`), `allowed_users` is filtered to that company only, preventing cross-company user choices in form dropdowns.
### `HorillaModelForm` role
Provides Horilla form conventions/behaviors and base model form integration.
---
## Field policy
The dynamic form includes all model fields except framework/audit metadata:
- `created_at`
- `updated_at`
- `created_by`
- `updated_by`
- `additional_info`
This gives a practical default for dynamic create/edit use cases while hiding system-managed columns.
---
## Typical use case
When a helper endpoint receives a model identifier and must construct a form class at runtime:
```python
from horilla_generics.methods import get_dynamic_form_for_model
DynamicForm = get_dynamic_form_for_model(MyModel)
form = DynamicForm(request.POST or None, instance=obj_or_none)
```
Useful in dynamic-create patterns, AJAX form renderers, and generic helper views.
---
## Integration note
This helper is commonly relevant when resolving "dynamic form paths" (for example, Select2/helper endpoints that cannot directly import nested runtime classes such as `DynamicForm` from another builder).
Instead of importing a non-module-level class, code can regenerate an equivalent form from model metadata using this function.
---
## Caveats
- The exclusion list is fixed in this helper; if you need different exclusions per model/view, create a dedicated form builder or wrap this function.
- Since it uses `fields = "__all__"`, model field-level permissions should still be enforced elsewhere (view/form permission pipeline).
- Dynamic classes are created per call; for high-frequency usage you may choose to cache by model in a custom wrapper.
---
## Summary
`horilla_generics/methods.py` provides a compact but important runtime utility: building a permission-aware default `ModelForm` class from a model object. It is a foundational helper for generic/dynamic form workflows where static form classes are not practical.
