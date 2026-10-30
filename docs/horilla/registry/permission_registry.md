# Permission Registry (`permission_registry.py`)

## Purpose

`horilla/registry/permission_registry.py` maintains a set of model names that are exempt from permission checks.

The set is:

```python
PERMISSION_EXEMPT_MODELS
```

It includes built-in defaults like `Session`, `Group`, `Permission`, etc.

## API

### `@permission_exempt_model`

Decorator that adds `cls.__name__` into `PERMISSION_EXEMPT_MODELS`.

## Usage example

```python
from horilla.registry.permission_registry import permission_exempt_model


@permission_exempt_model
class ReviewCondition(HorillaCoreModel):
    ...
```

After class definition, `"ReviewCondition"` is in `PERMISSION_EXEMPT_MODELS`.

### `is_permission_exempt(model)`

Returns `True` if `model` must be excluded from permission listings and bulk actions: its `__name__` is in `PERMISSION_EXEMPT_MODELS`, or it is a model extension class (has `_inherit_model`). Permission listing and bulk-action views use this helper instead of testing set membership directly.
