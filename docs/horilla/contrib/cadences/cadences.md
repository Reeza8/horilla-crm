# Horilla Cadences app — deep dive (`horilla.contrib.cadences`)

## What this app does

- **Cadence** definitions: ordered **task / call / email** follow-ups for a target **module** (`HorillaContentType` limited by **`cadence_models`** feature registry).
- **CadenceCondition** rows — field/operator/value + AND/OR ordering (same spirit as automation conditions).
- **CadenceFollowUp** — each step: delay (`immediately`, `minute`, `hour`, `day`, `month`), optional **branch** from another follow-up, previous-activity status gates, plus type-specific fields (subject, due offsets, mail template FKs, call fields, etc.).
- **`inject.py`** — at import time, wraps **`HorillaDetailTabView._prepare_detail_tabs`** and **appends** the **Cadence** tab for the current detail model, but only when it has been registered via `register_cadence_tab(...)` **and** has at least one active cadence (uses `Cadence.objects.filter(module=content_type, is_active=True)`; `is_active` comes from **`HorillaCoreModel`**). This is the same extension pattern used by `horilla.contrib.duplicates` for its **Potential Duplicates** tab — the generics app has **no hardcoded knowledge of cadences**, and CRM apps don't reference the `cadences:` URL namespace in their own `urls` dicts.

---

## App startup (`apps.py`)

`CadencesConfig`:

| Setting | Value |
|---------|--------|
| `url_prefix` | `cadences/` |
| `url_namespace` | `cadences` |
| `auto_import_modules` | `registration`, `signals`, `menu`, **`inject`** |

Importing **`inject`** runs **monkey-patch registration** once per process (see `inject_cadence_tab()`).

---

## Feature registration (`registration.py`)

```text
register_feature("cadence", "cadence_models")
```

### `register_cadence_tab(app_label, model_name, url_prefix, url_name)`

CRM apps call this from their own **`registration.py`** to:

1. **`register_model_for_feature(..., features=["cadence"])`** — opts the model into cadence enrollment.
2. **Dynamically subclass** `CadenceRecordTabView` with `app_label` / `model_name` bound on the class.
3. **`urlpatterns.append(...)`** on `horilla.contrib.cadences.urls` — registers the HTMX tab endpoint without the cadences app importing CRM models directly.
4. Records `(app_label, model_name) -> "cadences:<url_name>"` in an internal lookup table (`get_cadence_tab_url_name`) so `inject.py` can resolve the tab URL for that model without the caller wiring a `"cadences"` key into its own detail-tab `urls` dict.

Failures are logged with `logger.warning` and do not crash startup.

---

## Menu (`menu.py`)

Registers settings and/or main navigation entries for cadence builder UI (list, create, follow-up modals). Exact URLs use namespace **`cadences:`** (e.g. `cadences:cadence_detail_view`, `cadences:cadence_followup_create_view`).

---

## Models — behavioral notes

### `Cadence`

- **`module`** FK → target entity type.
- Helpers: **`get_add_followup_url`**, **`_get_default_followup_number`** — gap-filling stage numbers for the “+” next-stage UX.
- **`is_active_col`** — renders template partial for list “active” toggle column.

### `CadenceFollowUp`

- **`followup_type`** — `task` | `call` | `email`.
- **`branch_from`** — self-FK for branched sequences from a specific card action.
- Integrates with **`Activity`** model constants for status compatibility on `previous_status`.

### `CadenceCondition`

- **`@permission_exempt_model`** — field permissions skipped where declared; useful for system-like rule rows.

---

## Signals (`signals.py`)

Typically handle:

- Enrollment when a record enters a pipeline stage (if configured).
- Creating **`Activity`** rows when a follow-up fires.

Consult `horilla/contrib/cadences/signals.py` for exact senders.

---

## Runtime injection (`inject.py`)

1. Wraps `HorillaDetailTabView._prepare_detail_tabs` (same extension mechanism `duplicates` uses for its tab) and calls the original implementation first, so `self.object_id` and the standard tabs are already built.
2. Reads `self.model` — the detail-tab subclass (e.g. `LeadsDetailViewTabView`, `AccountDetailViewTabs`, `ContactDetailViewTabs`, `OpportunityDetailViewTabView`) sets this before calling `super()._prepare_detail_tabs()`.
3. Looks up a registered cadence tab URL name for that model via `registration.get_cadence_tab_url_name(app_label, model_name)`.
4. If a URL name is found **and** at least one active `Cadence` exists for that model's content type, appends a `{"title": "Cadence", "id": "cadence", "target": "tab-cadence-content", ...}` tab (inserted right after the `activity` tab when present, else appended).

This avoids empty tabs on unrelated models, and keeps `horilla.contrib.generics` and CRM apps' `urls` dicts free of any cadence-specific keys.

---

## Forms (`forms.py`)

Cadence builder forms use **`HorillaModelForm`** (see [single-step form base](../generics/forms/single_step.md)). Only **`field_order`** and **`Meta`** were aligned to the 1.10 pattern; **`__init__`**, HTMX module reload, and **`clean()`** are unchanged.

### Shared conventions

| Pattern | Usage |
|---------|--------|
| `field_order` | Default layout order |
| `Meta.fields = "__all__"` | All model columns unless excluded |
| `keep_on_form` | Fields removed from auto `HORILLA_FORM_EXCLUDE` |
| `Meta.exclude` | Extra columns hidden on this form only |

Do **not** list `company`, `created_at`, `updated_at`, `created_by`, `updated_by`, or `additional_info` in `Meta.exclude` on `HorillaModelForm` subclasses unless you intentionally override the base list.

### `CadenceForm`

- **`field_order`**: `name`, `module`, `description`, `is_active`
- **`keep_on_form`**: `("is_active",)`
- **Conditions**: `CadenceCondition` rows via `HorillaSingleFormView` (`field`, `operator`, `value`); **`clean()`** requires at least one complete condition row
- **HTMX**: `module` reloads the form partial on change (GET merged into `initial`, not bound `data`)

### `CadenceFollowUpForm`

- **`field_order`**: cadence metadata first, then all task/call/email columns (runtime visibility via **`TYPE_FIELD_MAP`** in `__init__`)
- **`Meta.exclude`**: `call_type`, `call_status`, `order`
- **HTMX**: `followup_type` / `do_this_unit` toggles unchanged

---

## Related documentation

- Activity outcomes used by follow-ups: [../activity/activity.md](../activity/activity.md)
- Mail templates for email steps: [../mail/mail.md](../mail/mail.md)
- Generics detail tabs: [../generics/views/detail_tabs.md](../generics/views/detail_tabs.md)
