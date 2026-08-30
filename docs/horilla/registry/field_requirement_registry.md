# Field Requirement Registry (`field_requirement_registry.py`)

## Purpose

`horilla/registry/field_requirement_registry.py` records which models let an
administrator reconfigure whether their fields are required on forms, and owns
the rule deciding when relaxing a field is safe.

Requiredness normally comes from the model definition (`blank=False`), so an
installation cannot adapt a form to its own process without editing source.
Registering a model exposes its fields on the **Field Requirements** settings
page instead.

Opting in is explicit, so the settings page only offers models whose forms are
known to tolerate the change.

The set is:

```python
CONFIGURABLE_REQUIREMENT_MODELS
```

It stores model labels (`"leads.lead"`) and starts empty.

## API

### `@configurable_field_requirements`

Decorator that adds `cls._meta.label_lower` into
`CONFIGURABLE_REQUIREMENT_MODELS` and returns the class unchanged.

### `is_requirement_configurable(model)`

Returns True when `model` opted in.

### `get_configurable_models()`

Returns the registered model classes, sorted by verbose name. Resolved through
the app registry, so a model whose app is uninstalled is skipped rather than
raising.

### `get_configurable_fields(model)`

Returns the model fields whose requiredness may be configured: concrete,
editable, non-primary-key, non-many-to-many fields that are not excluded.

### `get_excluded_fields(model)`

Returns field names that must never be configurable. Combines the primary key
with the model's `field_permissions_exclude` (audit columns, `company`,
`is_active`, `additional_info`) and an optional `requirement_config_exclude`
for model-specific additions.

### `can_relax_requirement(model_field)`

Returns whether the field can be made optional without breaking saves. A form
may only stop requiring a value if the column has somewhere to put the absence
of one:

| Condition | Why it is safe |
| --- | --- |
| `null=True` | The column stores NULL |
| `empty_strings_allowed` | Text-like columns store `""`; False for numeric, date, boolean and foreign key columns |
| `has_default()` | The default supplies the missing value |

Without one of those, clearing the field would raise `IntegrityError` at save
time, so the settings page refuses the change up front.

### `get_relax_blocked_reason(model_field)`

Returns a translated explanation when a field cannot be made optional, or None
when it can.

## Usage example

```python
from horilla.registry.field_requirement_registry import (
    configurable_field_requirements,
)


@configurable_field_requirements
class Lead(HorillaCoreModel):
    ...
```

After class definition, `"leads.lead"` is in
`CONFIGURABLE_REQUIREMENT_MODELS`, and Lead's fields appear on the Field
Requirements settings page.

To keep a specific field off that page, list it on the model:

```python
@configurable_field_requirements
class Lead(HorillaCoreModel):
    requirement_config_exclude = ["lead_score"]
```
