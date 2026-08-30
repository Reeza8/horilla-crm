# Field Requirements

## Purpose

Lets an administrator decide, per company, whether a field is required on a
model's create and edit forms -- without editing the model definition.

Every installation runs a slightly different process. One team captures an
email address on every lead; another works from phone calls and cannot supply
one. Because requiredness is declared in the model (`Lead.email` is
`blank=False`), the second team previously had no way to proceed but to patch
the source.

## Where it lives

| Concern | Location |
| --- | --- |
| Opt-in registry and safety rule | `horilla/registry/field_requirement_registry.py` |
| Stored override | `horilla.contrib.core.models.FieldRequirement` |
| Resolution | `horilla.contrib.core.utils.get_field_requirements_for_model` |
| Form application | `HorillaFormMixin.is_field_required` |
| Settings page | `horilla/contrib/core/views/field_requirements.py` |

## Using the settings page

**Settings → Base → Field Requirements** lists the configured overrides. Each
row names a model, a field, and whether that field is Required or Optional.
Creating a row picks the model first; the field list then reloads to show the
fields configurable on it. Deleting a row restores the requiredness declared on
the model.

Access is gated by the usual model permissions:
`core.view_fieldrequirement`, `core.add_fieldrequirement`,
`core.change_fieldrequirement`, and `core.delete_fieldrequirement`.

Overrides are scoped to the active company, so branches can capture different
information.

## Which fields can be changed

A model must opt in with `@configurable_field_requirements`. Lead and
Opportunity do so today.

Making an optional field **required** is always allowed. Making a required
field **optional** is allowed only when the database can store an empty value
for that column -- see `can_relax_requirement` in the
[registry docs](../../registry/field_requirement_registry.md). Text-like
columns qualify because they store `""`; a non-nullable integer, date or
foreign key does not, and the settings page refuses it with an explanation
rather than letting the save fail later.

Bookkeeping columns (`company`, `is_active`, `additional_info`, the audit
fields and the primary key) are never configurable.

## How the override reaches the form

`is_field_required()` consults the overrides before falling back to the
model's `blank` flag:

```python
override = self.field_requirement_overrides.get(field_name)
if override is not None:
    return override
```

`field_requirement_overrides` is resolved once per form instance, so the number
of fields on a form does not affect the query count. It is empty for models
that have not opted in, which means forms behave exactly as before wherever
nothing has been configured.

Multi-step forms already re-resolve requiredness per step through
`resolve_field_required()`, so they pick the override up automatically.
Single-step forms inherit `required` from Django, which derives it from `blank`
once when the field is built; they call
`apply_field_requirement_overrides()` at the end of `__init__` to re-resolve
only the fields an admin explicitly configured.

Two safeguards keep an override from making a record unsavable:

- **Requiredness is not mandatoriness.** `is_field_mandatory()` still reports
  what the *column* accepts and ignores overrides entirely, so field
  permissions continue to keep a non-nullable field on the form.
- **Unsafe rows are dropped on read.** `get_field_requirements_for_model`
  re-checks `can_relax_requirement` and discards a relaxation it cannot honour,
  so an imported or stale row cannot turn into an `IntegrityError`.

## Why relaxing a `blank=False` field is safe

Django's `BaseModelForm._get_validation_exclusions()` excludes a field from
model validation when the model field is not blankable, the *form* field is not
required, and the submitted value is empty. Setting `required = False` is
therefore enough: the model's blank check is skipped, and the column stores
`""` or NULL according to its own definition. No model validation is patched.
