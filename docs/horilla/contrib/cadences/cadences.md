# Horilla Cadences app — deep dive (`horilla.contrib.cadences`)

## What this app does

- **Cadence** definitions: ordered **task / call / email** follow-ups for a target **module** (`HorillaContentType` limited by **`cadence_models`** feature registry).
- **CadenceCondition** rows — field/operator/value + AND/OR ordering (same spirit as automation conditions).
- **CadenceEnrollment** — one row per **run** of a cadence for a record (automatic or manual); every item a run creates is stamped with its id, so runs never see, advance or cancel each other's items. See [Enrollments](#enrollments).
- **CadenceFollowUp** — each step: delay (`immediately`, `minute`, `hour`, `day`, `month`), optional **branch** from another follow-up, previous-activity status gates, plus type-specific fields (subject, due offsets, mail template FKs, call fields, etc.).
- **`view_extensions.py`** — `CadenceTabExtension`, a real `ViewExtension` (`_inherit_view`, see [extension index](../../extension/inherit.md)) registered against the shared **`HorillaDetailTabView`** base class, so it applies to every concrete detail-tab view automatically. It overrides `_prepare_detail_tabs` and **appends** the **Cadence** tab for the current detail model, but only when it has been registered via `register_cadence_tab(...)` **and** has at least one active cadence (uses `Cadence.objects.filter(module=content_type, is_active=True)`; `is_active` comes from **`HorillaCoreModel`**). This is the same mechanism `horilla.contrib.duplicates` uses for its **Potential Duplicates** tab on the same base class — the generics app has **no hardcoded knowledge of cadences**, and CRM apps don't reference the `cadences:` URL namespace in their own `urls` dicts.

---

## App startup (`apps.py`)

`CadencesConfig`:

| Setting | Value |
|---------|--------|
| `url_prefix` | `cadences/` |
| `url_namespace` | `cadences` |
| `auto_import_modules` | `registration`, `signals`, `menu`, **`view_extensions`** |

Importing **`view_extensions`** registers `CadenceTabExtension` (a real `ViewExtension`, not a monkey-patch) once per process, via `_inherit_view`'s normal `__init_subclass__` registration.

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
4. Records `(app_label, model_name) -> "cadences:<url_name>"` in an internal lookup table (`get_cadence_tab_url_name`) so `CadenceTabExtension` (`view_extensions.py`) can resolve the tab URL for that model without the caller wiring a `"cadences"` key into its own detail-tab `urls` dict.

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

- **Follow-up 1 can hold several items.** The `unique_first_followup_per_cadence` constraint and the "Follow up 1 can only contain one item" check were removed; follow-up 1 still clears `previous_status`.
- **`followup_type`** — `task` | `call` | `email`.
- **`branch_from`** — self-FK for branched sequences from a specific card action.
- Integrates with **`Activity`** model constants for status compatibility on `previous_status`.

### `CadenceEnrollment`

Generic FK to the record (`content_type` / `object_id`), plus `cadence`, `status` (`active` / `completed` / `unenrolled` / `failed`), `source` (`auto` / `manual`), `run_number` (1, then +1 each time the record is enrolled again), `started_at`, `ended_at` and `unenrolled_by`.

- **`unique_active_enrollment_per_record`** — at most one running enrollment per cadence per record; `cadence_enroll_record_idx` indexes the record.
- **`can_unenroll()`** — true only for running **manual** enrollments.
- List-column helpers used by the record tab: `unenroll_action_col`, `completed_at_col`, `unenrolled_at_col`, `enrolled_by_col` ("Automatic" for condition-based runs), cadence status (Ongoing / Completed / Failed / Stopped) and member status (Enrolled / Un-enrolled).

### `CadenceCondition`

- **`@permission_exempt_model`** — field permissions skipped where declared; useful for system-like rule rows.

---

## Services (`services.py`) — enrollment engine

Task / call / email creation lives here (moved out of `signals.py`); every created item gets `cadence_runtime.enrollment_id` and `run_number`.

| Function | Purpose |
|----------|---------|
| `enroll(cadence, instance, user)` | Always starts a **fresh run** from follow-up 1. Cadence conditions are **not** checked; earlier runs and their activities stay untouched. |
| `unenroll(enrollment, user)` | Closes the enrollment **first** (so cancelling activities cannot advance it), then cancels open items and keeps completed ones. Raises `EnrollmentError`. |
| `get_or_create_auto_enrollment(cadence, instance)` | Creates an automatic enrollment only if the record was **never** enrolled in that cadence, so a save never restarts a completed or un-enrolled record. |
| `create_first_followups` / `create_next_followups` | Create items limited to the enrollment's own items. |
| `refresh_status(enrollment)` | `completed` once all items are closed; `failed` when nothing could be created (automatic runs stay ongoing and retry on next save). |
| `eligible_cadences(instance)` / `get_ineligible_reason(...)` | Active, same module, has a follow-up 1, not already running for the record. |
| `adopt_legacy_enrollment(...)` | Lazily adopts items created before enrollments existed by adding `enrollment_id` to their JSON — no data migration. |

## Signals (`signals.py`)

- Record save → `_run_automatic_enrollment()` for matching cadences (conditions apply to **automatic** enrollments only).
- Activity status change → advance the next follow-up, **only while its enrollment is active**; manual enrollments ignore cadence conditions.
- Runtime activities are de-duplicated per `(enrollment, follow-up)`; items without an enrollment keep the old per-cadence key.
- Follow-ups added later are backfilled into manual enrollments that are still running.

## Runtime query behavior

Cadence record tabs and initial follow-up setup share the same cadence queryset.
The queryset prefetches `conditions` and `followups`; condition evaluation must
use the prefetched list and sort it in memory. Calling
`cadence.conditions.all().order_by(...)` bypasses the prefetch cache and causes
an extra query for the same condition rows.

`ensure_initial_followups_for_instance()` returns the prefetched cadence list so
`CadenceRecordTabView` can reuse it. The record-tab queryset is also cached for
the lifetime of the view instance because the generic list lifecycle may call
`get_queryset()` more than once during one request.

When changing this path, preserve these rules: keep the runtime follow-up
initialization behavior, reuse prefetched related managers, and validate with
`python manage.py check` plus a request to a registered record Cadence tab.

---

## Record Cadence tab (`views/record_tab.py`, `views/enrollment.py`)

`register_cadence_tab()` now creates **three** classes per model and URLs `<url_name>`, `<url_name>_nav`, `<url_name>_list`:

- `CadenceRecordTabView` (`HorillaView` shell) → loads
- `CadenceRecordNavbar` (`HorillaNavView`) — has the **Enroll** button, and
- `CadenceRecordListView` (`HorillaListView`) — **one row per enrollment**, newest first: Cadence, Start Date, Completed Date, Enrolled By, Un-enrolled Date, Cadence Status, Member Status, Last Follow-up, plus a per-row **Un-enroll** button (`cadence_unenroll_action_col.html`, disabled when `can_unenroll()` is false). Earlier runs stay visible.

`CadenceEnrollView` (`CadenceEnrollForm`: a multi-select of eligible cadences, enrolled in one go with per-cadence success/error messages) and `CadenceUnenrollView` both require **edit access to the record** (`change_<model>`, or `change_own_<model>` + ownership) and take the record from the URL, never from posted data.

`register_feature("cadence", "cadence_models", auto_register_all=False)` — only models that opt in through `register_cadence_tab` are registered.

---

## Cadence detail board (`views/detail.py`)

- Header is a `CadenceDetailNavbar` (`HorillaNavView`, URL `cadence_detail_nav_view`): back arrow via `navbar_indication` (`get_cadence_previous_url`), **Edit** as primary button (`cadences.change_cadence`), **View Reports** as secondary; search/filter/reload/view-type are off. The cadence description is the navbar description (default text as fallback).
- 5 follow-up columns shown by default (was 4).
- Add buttons: a standalone **"add another"** at the bottom of the follow-up 1 column (`show_standalone_add`); per-card `can_add_sibling` (`_flag_last_sibling_add`) shows "Add another follow-up here" only under the last card of a sibling group and while the parent has unused statuses; decisions use `_bucket_followups` / `_can_add_next_for_parent` (`_compute_can_add_to_bucket` removed). `branch_from` is passed to the create form only for cards with a parent.
- Hovering a card highlights it and all its ancestors (`data-branch-from-id`, `cadence_detail.js`).

## Permissions

`CadenceReportView`, `CadenceReportTabView` and `CadenceNavbar` require **`cadences.view_cadence`**; the report's task / call / email tabs use it too (previously `activity.view_activity`). A missing cadence in the report shows the 404 page.

---

## Cross-app integration (`view_extensions.py`)

`CadenceTabExtension(ViewExtension)` sets `_inherit_view = "horilla.contrib.generics.views.detail_tabs.HorillaDetailTabView"` (the shared base class), overriding `_prepare_detail_tabs`:

1. Calls `super()._prepare_detail_tabs()` first (which chains through any other extension registered on the same base, e.g. `horilla.contrib.duplicates`'s `DuplicateTabExtension` — both compose together correctly — down to the real target), so `self.object_id` and the standard tabs are already built.
2. Reads `self.model` — the detail-tab subclass (e.g. `LeadsDetailViewTabView`, `AccountDetailViewTabs`, `ContactDetailViewTabs`, `OpportunityDetailViewTabView`) sets this before calling `super()._prepare_detail_tabs()`.
3. Looks up a registered cadence tab URL name for that model via `registration.get_cadence_tab_url_name(app_label, model_name)`.
4. If a URL name is found **and** at least one active `Cadence` exists for that model's content type, appends a `{"title": "Cadence", "id": "cadence", "target": "tab-cadence-content", ...}` tab (inserted right after the `activity` tab when present, else appended).

This avoids empty tabs on unrelated models, and keeps `horilla.contrib.generics` and CRM apps' `urls` dicts free of any cadence-specific keys. `resolve_view_class()`'s base-class MRO fallback (see [extension index — Targeting a shared base class](../../extension/inherit.md#targeting-a-shared-base-class)) is what makes registering directly on `HorillaDetailTabView` apply to every concrete detail-tab view automatically, instead of requiring a monkey-patch on the base or a registration per concrete subclass.

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
- **Labels**: "Do This Value" → **Wait for** (help text shown as an info icon), "Trigger Date + Days" → **Due Date (days after trigger)**, "Call Start + Days" → **Call Date (days after trigger)**, "After previous … is" → **When the previous … is**; help text added to Do This / Wait for / previous status / day fields.

### `CadenceEnrollForm`

Non-model form on `CadenceEnrollment`: one `cadences` multi-select (select2) limited to `services.eligible_cadences(record)`; the record comes from `initial` / the session key `ENROLL_RECORD_SESSION_KEY`. `save()` returns `(enrolled_names, errors)`.

---

## Conditions on fields that aren't model columns

Cadence conditions are evaluated with `automations.methods.evaluate_condition`, which asks the condition-field extension that owns the field for its value first — see [automations.md](../automations/automations.md#conditions-and-fields-that-arent-model-columns). The condition dropdown comes from `get_model_field_choices`, which includes extension fields ([condition_fields.md](../generics/forms/condition_fields.md#conditionfieldprovider-extension-seam)).

---

## Related documentation

- Activity outcomes used by follow-ups: [../activity/activity.md](../activity/activity.md)
- Mail templates for email steps: [../mail/mail.md](../mail/mail.md)
- Generics detail tabs: [../generics/views/detail_tabs.md](../generics/views/detail_tabs.md)
