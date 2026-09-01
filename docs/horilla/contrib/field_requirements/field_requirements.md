# Field Requirements (`horilla.contrib.field_requirements`)

Lets an administrator decide, per company, whether a field is required on an
opted-in model's create and edit forms — without editing the model definition.

This app is self-contained. Turning it on or off is a single line in
`INSTALLED_APPS`. `horilla.contrib.core`, `horilla.contrib.generics`, and CRM
model files do not import it.

## App startup (`apps.py`)

`FieldRequirementsConfig` (`AppLauncher`):

| Setting | Value |
|---------|--------|
| `name` | `horilla.contrib.field_requirements` |
| `label` | `field_requirements` |
| `auto_import_modules` | `menu`, `registration` |
| `url_prefix` | `field-requirements/` |
| `url_namespace` | `field_requirements` |

## Feature registration (`registration.py`)

```text
register_feature("field_requirements", "field_requirement_models", auto_register_all=False)
```

`auto_register_all=False` is required. Many CRM models call
`register_model_for_feature(..., all=True)`. If this feature auto-registered
those models, Account, Contact, User, and others would appear as configurable
without an explicit opt-in.

Models opt in from their own `registration.py`:

```python
register_model_for_feature(
    app_label="leads",
    model_name="Lead",
    features=["field_requirements"],
)
```

Lead and Opportunity do this today. The model class files themselves are not
touched.

Helpers live in `registry.py` and read `FEATURE_REGISTRY["field_requirement_models"]`:

| Helper | Purpose |
|--------|---------|
| `is_requirement_configurable(model)` | Whether the model opted in |
| `get_configurable_models()` | Opted-in model classes, sorted by verbose name |
| `get_configurable_fields(model)` | Concrete, editable, non-M2M fields that may be configured |
| `can_relax_requirement(field)` | Whether making the field optional is safe for the database |
| `get_relax_blocked_reason(field)` | Translated explanation when relaxing is refused |

A field can be made optional only when the column can store an empty value
(`null=True`, a text-like empty string, or a default). Non-nullable foreign
keys such as Lead Stage cannot be relaxed.

## Stored override (`models.py`)

`FieldRequirement` is a `HorillaCoreModel`:

| Field | Role |
|-------|------|
| `content_type` | Target model (`HorillaContentType`, limited to opted-in models) |
| `field_name` | Target field |
| `is_required` | Required vs optional on forms |
| `company` | Company scope (from `HorillaCoreModel`) |

`unique_together` is `(content_type, field_name, company)`. `clean()` rejects
models that did not opt in, unknown or excluded fields, and relaxations the
database cannot store.

FK reverse accessors include the app label (`field_requirements_fieldrequirement_*`)
so they do not clash with another model named `FieldRequirement`.

## Resolution (`utils.py`)

`get_field_requirements_for_model(model)` returns `{field_name: bool}` for the
active company. Missing keys keep the model's own `blank` flag. Unsafe or
stale relaxations are dropped on read. Results are cached on the current
request.

## Settings UI

The app registers its own settings section (same pattern as Duplicate
Control). Admins with `field_requirements.view_fieldrequirement` open
**Settings → Field Requirements** and create per-company overrides.

| URL name | Role |
|----------|------|
| `field_requirements:field_requirement_view` | Settings page shell |
| `field_requirements:field_requirement_list_view` | Override list |
| `field_requirements:field_requirement_create_form` | Create modal |
| `field_requirements:field_requirement_update_form` | Edit modal |
| `field_requirements:field_requirement_delete_view` | Delete |
| `field_requirements:field_requirement_field_choices` | Field picker for the selected model |

The field picker lists configurable fields for Lead and Opportunity. Fields the
database cannot store empty are labelled "always required"; saving one as
optional is refused.

Lead and Opportunity **forms do not yet apply these overrides**. That is the
next stage (`FormExtension` discovery).

