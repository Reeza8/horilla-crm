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
| `auto_import_modules` | `menu`, `registration`, `extensions` |
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

## Form overrides (`extensions.py`)

Overrides are applied through Horilla's ``FormExtension`` compose step, not by
editing ``HorillaFormMixin`` or CRM model files.

The app discovers ``ModelForm`` subclasses in the opted-in models' own
``forms`` modules whose ``Meta.model`` is Lead or Opportunity (today:
``LeadSingleForm``, ``LeadFormClass``, ``OpportunitySingleForm``,
``OpportunityFormClass``). Each discovered form gets a dynamically created
``FormExtension`` subclass whose methods are copied from
``_FieldRequirementFormMethods`` — a real, statically-declared ``FormExtension``
template (mirroring ``custom_fields.extensions._SingleFormMethods``) that is
never itself registered and never subclassed directly. Views already call
``resolve_form_class``, so create and edit screens pick the composed class up
without listing form class names.

``setup_form_extension_fields`` runs after the target form finishes building
fields and calls ``apply_field_requirement_overrides``, which sets
``field.required`` from ``get_field_requirements_for_model``. Making a field
optional also drops the HTML ``required`` attribute. Making a field required
is skipped for hidden multi-step fields and for checkboxes, so later wizard
steps and unchecked boxes keep submitting.

Django's ``ModelForm`` already excludes empty, non-required form fields from
model validation when the column is ``blank=False``. An optional Lead email
therefore stores as an empty string instead of raising ``full_clean`` errors.

This app is listed before the CRM apps, so discovery runs later than its own
``ready()`` — after Lead and Opportunity have opted in. Rather than
reassigning ``apply_form_extensions`` on the ``horilla.extension.forms``
module (a monkey-patch), the app registers an ordinary callback via
``horilla.extension._pre_compose_hooks.register_pre_compose_hook("forms", ...)``.
``apply_form_extensions()`` calls every registered hook itself at the start of
each compose pass, so no Horilla module attribute is ever reassigned — the
same mechanism ``custom_fields`` uses for its own dynamic discovery. Turning
the feature off is still one ``INSTALLED_APPS`` line: no FormExtension
classes are registered, and the core/generics form mixins are unchanged.
