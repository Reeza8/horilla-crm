# Horilla `_inherit_form` — Form Extension Guide

Extend existing Horilla forms (single-step and multi-step) **without** editing target-app form classes. CRM apps (`horilla_crm.*`) and core apps (`horilla.contrib.core.*`) use the same API.

**Related:** [Extension system index](../inherit.md) · [Model `_inherit`](../models/inherit.md)

**Reference implementation:** `horilla/extension/forms/` · **CRM example:** `my_lead_extensions/forms.py` · **Core tests:** `horilla/extension/forms/tests.py` (`HolidayForm`, `UserFormSingle`)

---

## Quick start

Pair with a model extension that adds `industry_code` on `leads.Lead`, then extend the Lead forms:

```python
# my_lead_extensions/forms.py
from django import forms

from horilla.extension.forms import FormExtension
from horilla.utils.translation import gettext_lazy as _


class LeadSingleFormExtension(FormExtension):
    _inherit_form = "horilla_crm.leads.forms.LeadSingleForm"

    field_order_insert = [
        ("title", "industry_code"),
    ]

    class Meta:
        exclude = ()

    def setup_form_extension_fields(self):
        if "industry_code" in self.fields:
            self.fields["industry_code"].widget.attrs.update(
                {"class": "uppercase", "placeholder": _("e.g. FIN")}
            )

    def clean_industry_code(self):
        value = self.cleaned_data.get("industry_code")
        return value.upper() if value else value


class LeadFormClassExtension(FormExtension):
    _inherit_form = "horilla_crm.leads.forms.LeadFormClass"

    step_fields_insert = {
        2: [("industry", "industry_code")],
    }

    class Meta:
        exclude = ()
```

```python
# my_lead_extensions/apps.py
auto_import_modules = ["models", "forms", "lists", "kanbans", "details"]
```

```python
# local_settings.py — client-owned
INSTALLED_APPS += ["my_lead_extensions"]  # after horilla_crm.* is OK
```

Restart the dev server after changing extensions.

---

## Rules

| Topic | Rule |
|-------|------|
| Base class | `FormExtension` (`horilla.extension.forms`) — do **not** instantiate; views use the composed class |
| `_inherit_form` | `"<module>.<ClassName>"` e.g. `"horilla_crm.leads.forms.LeadSingleForm"` |
| Naming | Under `horilla/`, use `FormExtension` not `HorillaFormExtension` — see [Extension index](../inherit.md#bootstrap) |
| Target | Concrete CRM form (`LeadSingleForm`), **not** `HorillaModelForm` |
| Field tweaks | `setup_form_extension_fields()` — **not** `__init__` |
| Validation | `clean_<field>()` on the extension class |
| App order | Extension app **after** CRM in `INSTALLED_APPS` when possible; `bootstrap_extensions()` + `resolve_form_class()` still work if CRM loads first |
| Model fields | Injected columns on `fields = "__all__"`; use layout hooks to position them |

### `_inherit_form` validation

| Rule | Result |
|------|--------|
| Module import fails | Startup error |
| Class missing | Startup error |
| Not a `django.forms.BaseForm` subclass | Startup error |
| Duplicate declared field (two extensions) | Startup error (use `override_fields` to allow) |

---

## `setup_form_extension_fields`

After the target form builds `self.fields`, the composed mixin calls your hook:

```python
def setup_form_extension_fields(self):
    if "industry" in self.fields:
        self.fields["industry"].required = False
```

Do **not** override `__init__` on extension classes — `super()` does not chain correctly on composed mixins. The platform generates a mixin `__init__` that calls `super(mixin, self).__init__()` then `setup_form_extension_fields()`.

---

## Show core fields (`keep_on_form`)

`company`, audit fields, etc. are hidden by `HORILLA_FORM_EXCLUDE` on `HorillaModelForm` / `HorillaMultiStepForm`:

```python
class Meta:
    exclude = ()
    keep_on_form = ("company",)

field_order_insert = [("lead_owner", "company")]
```

Multi-step: also add the field to a step:

```python
step_fields_insert = {1: [("lead_owner", "company")]}
```

Composed forms re-apply `keep_on_form` via `apply_horilla_form_meta_exclude()` in `horilla/contrib/generics/forms/form_class_mixin.py` (parent `Meta.exclude` may already list `company` before merge).

**Note:** `required = False` on the form does not change the database; use `blank=True` on the model for empty saves.

---

## Layout hooks

| Hook | Use |
|------|-----|
| `field_order_insert` | `[("after_field", "new_field"), …]` — single-step |
| `field_order_append` | Append names if missing |
| `step_fields_insert` | `{step: [("after", "new_field"), …]}` — wizard |
| `step_fields_append` | `{step: ["field", …]}` |
| `fieldsets_insert` | `[("after_field", "new_field"), …]` — insert into an existing fieldset group |

Insert after an anchor field; if the anchor is missing, the field is appended.

**`fieldsets_insert`:** walks each `(name, options)` group on the target form’s `fieldsets` tuple and inserts `new_field` after `after_field` in that group’s `fields`. If the anchor is missing, the field is appended to the last group. Templates that loop `form.get_fieldsets()` pick up the extra field without HTML changes — see [HorillaModelForm.get_fieldsets](../../contrib/generics/forms/single_step.md#fieldsets-and-get_fieldsets).

Example — add a date-system choice after `date_format` on regional formatting:

```python
class RegionalFormattingFormExtension(FormExtension):
    _inherit_form = "horilla.contrib.core.forms.base.RegionalFormattingForm"

    fieldsets_insert = [
        ("date_format", "date_system"),
    ]

    class Meta:
        fields_append = ("date_system",)
```

`LAYOUT_KEYS` in `horilla/extension/forms/registry.py` lists all layout hook names (`field_order_*`, `step_fields_*`, `fieldsets_insert`) so compose and registration stay in sync.

**Conflict:** two extensions insert at the same place → higher `_inherit_form_priority` wins, then `INSTALLED_APPS` order.

---

## Meta merge

| Attribute | Policy |
|-----------|--------|
| `model` | Target wins |
| `fields` | Target wins; use `fields_append` when target uses an explicit list (not `"__all__"`) |
| `exclude` | Union |
| `keep_on_form` | Union |
| `widgets`, `labels`, `help_texts`, `error_messages` | Dict merge |

`HorillaFormMixin.__init_subclass__` still applies `HORILLA_FORM_EXCLUDE` on the composed class after merge.

---

## Declared fields

```python
industry_code = forms.CharField(required=False, ...)
```

Supported **only** when the field exists on the model (via model `_inherit`). Pure form-only fields are unsupported in v1.

---

## Method merge

| Method | Policy |
|--------|--------|
| `setup_form_extension_fields` | Called after parent `__init__` |
| `clean_<field>` | Normal MRO; prefer over overriding `clean()` |
| `clean` / `save` | If overridden, must call `super()` |

Prefer `clean_<field>()` so `HorillaModelForm.clean()` (permissions, readonly, conditions) still runs.

---

## Composition and MRO

Composed classes use v1.1 bases:

```python
type(name, (*reversed(mixins), target), namespace)
```

```text
LeadSingleFormExtended
 → LeadSingleFormExtensionMixin
 → LeadSingleForm
 → OwnerQuerysetMixin
 → HorillaModelForm
 → HorillaFormMixin
 → ModelForm
```

Markers on composed classes:

```python
__horilla_composed__ = True
__horilla_form_path__ = "horilla_crm.leads.forms.LeadSingleForm"
__wrapped_form__ = LeadSingleForm
```

The original target class is never modified.

---

## Registry and priority

```python
FORM_EXTENSION_REGISTRY = {
    "horilla_crm.leads.forms.LeadSingleForm": [ExtensionSpec(...), ...],
}
```

Optional:

```python
_inherit_form_priority = 100  # higher runs later in mixin order
```

Sort key: `(priority, INSTALLED_APPS order)`.

---

## Platform hooks (core — not in your extension app)

Unlike model `_inherit`, form extensions **require** two integrations already shipped in Horilla core:

| Hook | Location | Purpose |
|------|----------|---------|
| `bootstrap_extensions()` | `horilla/extension/bootstrap.py`, called from `horilla/urls/project.py` | Compose forms + list + kanban + detail + formatter at URLconf load |
| `apply_form_extensions()` | `horilla/extension/forms/bootstrap.py` | Build `FORM_COMPOSED_MAP` (also invoked by `bootstrap_extensions()`) |
| `resolve_form_class()` | `HorillaSingleFormView` / `HorillaMultiStepFormView.get_form_class()`, and `horilla.views.generic.FormView` | Return composed form at runtime |

Model extensions use `ExtensionModelBase` — **no** form/list bootstrap. See [Extension index](../inherit.md#bootstrap) and [models/inherit.md](../models/inherit.md#bootstrap-models-vs-forms-vs-lists).

## Views and resolution

`HorillaSingleFormView` / `HorillaMultiStepFormView` / `horilla.views.generic.FormView`:

```python
def get_form_class(self):
    base = super().get_form_class()
    if base is None:
        return base
    from horilla.extension.forms.resolve import resolve_form_class
    return resolve_form_class(base)
```

`horilla/urls/project.py` calls `bootstrap_extensions()` after all apps load; each form view also calls `resolve_form_class()` per request.

Plain Django `FormView` subclasses that are not Horilla single/multi-step views should inherit `horilla.views.generic.FormView` (see [generic FormView](../../views/generic.md)) and instantiate via `self.get_form_class()`, not the raw `form_class`. Regional formatting uses this pattern.

```python
from horilla.extension.forms import resolve_form_class

form_class = resolve_form_class(LeadSingleForm)  # → LeadSingleFormExtended
```

Select2 uses `data-form-class` from `__horilla_form_path__` for stable routing.

**Limitation (v1):** `form_class = None` dynamic forms are not supported.

---

## Package layout

```text
horilla/extension/forms/
├── __init__.py       # FormExtension, resolve_form_class, …
├── cache.py          # resolver cache + is_bootstrap_applied / set_bootstrap_applied
├── registry.py       # FORM_EXTENSION_REGISTRY, ExtensionSpec, LAYOUT_KEYS
├── metaclass.py      # FormExtension registration
├── compose.py        # MRO composition, Meta/layout merge
├── resolve.py        # resolve_form_class()
├── bootstrap.py      # apply_form_extensions()
├── checks.py         # manage.py check --tag form_extensions
├── debug.py          # get_form_extensions(), print_form_mro()
└── tests.py
```

`registry.py` only stores specs (no compose import). `resolve_form_class()` lazy-imports `apply_form_extensions()`; bootstrap clears `cache.RESOLVER_CACHE` after composing and imports `forms.checks` for `manage.py check --tag form_extensions`. See [Extension index](../inherit.md#registration-and-cache-invalidation).

Public API (`horilla.extension.forms`):

```python
from horilla.extension.forms import (
    FormExtension,
    resolve_form_class,
    apply_form_extensions,
    get_form_extensions,
    print_form_mro,
)
```

---

## Debugging

```python
from horilla.extension.forms import print_form_mro, get_form_extensions

print_form_mro("horilla_crm.leads.forms.LeadSingleForm")
print(get_form_extensions("horilla_crm.leads.forms.LeadSingleForm"))
```

```bash
python manage.py check --tag form_extensions
```

---

## Preserving `HorillaModelForm` behavior

The composed form must still run the parent pipeline:

| Step | Behavior |
|------|----------|
| `_pop_form_options` | `request`, `field_permissions`, `condition_*`, `hidden_fields` |
| `ModelForm.__init__` | Fields from `Meta` + model (injected fields with `fields="__all__"`) |
| Widget loop | Select2, date/time, readonly CSS |
| `_remove_fields_by_permission` | 4-layer field permissions |
| `clean()` | FK checks, readonly enforcement, condition fields |

`OwnerQuerysetMixin` stays on the target form through MRO — do not replace the target class.

---

## Design background

### Why not patch `horilla_crm.leads.forms`?

Views bind at import time:

```python
form_class = LeadSingleForm  # stale if module is patched later
```

Resolution must happen in `get_form_class()` via `resolve_form_class()`.

### Model vs form extension

| | `_inherit` (model) | `_inherit_form` (form) |
|--|-------------------|------------------------|
| Key | `"leads.Lead"` | `"horilla_crm.leads.forms.LeadSingleForm"` |
| Base | `HorillaCoreModel` | `FormExtension` |
| Storage | DB + extension migrations | Python composition only |
| View change | None | `resolve_form_class()` in `get_form_class()` |
| `clean()` | Target first; extension model: no `super().clean()` | Normal MRO; use `clean_<field>`, `super()` in `save` if needed |

### Non-goals (v1)

- Template xpath inheritance
- DRF serializer extension
- List view / global `HorillaModelForm` extension
- Runtime hot-reload of extensions (restart required)
- Pure form-only fields without a model column

Templates that hard-code `{{ form.field_name }}` will not show `fieldsets_insert` fields. Prefer `form.get_fieldsets()`.

### Acceptance criteria

- Extension apps add fields without editing core forms
- Core CRM migrations unchanged by form extensions
- `manage.py check` passes (including `--tag form_extensions`)
- `LeadSingleForm` HTMX (country/state) preserved
- Select2 / `data-form-class` works on composed forms
- Uninstalling extension app restores original form behavior

---

## Comparison summary

`_inherit_form` provides safe Django form extensibility aligned with model `_inherit`: startup-time registration, deterministic ordering, no monkey patching, and preserved parent form lifecycle.
