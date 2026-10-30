# Horilla Automations app — deep dive (`horilla.contrib.automations`)

## What this app does

- **`HorillaAutomation`** rules: when a registered model is created/updated/deleted (or on a **schedule**), evaluate **`AutomationCondition`** rows and send **email**, **in-app notification**, or **both**.
- Uses **`HorillaContentType`** so any model that opts into the **`automation_models`** feature can be a trigger target (no hard-coded model list in signals).
- Supports **Celery** execution (`execute_automation_task`) when async is enabled; otherwise runs synchronously from signal handlers.
- Ships **JSON seed automations** from `load_automation/automation.json` via `automation_files` on the app config.

---

## App startup (`apps.py`)

`AutomationsConfig`:

| Setting | Value |
|---------|--------|
| `url_prefix` | `automations/` |
| `url_namespace` | `automations` |
| `auto_import_modules` | `registration`, `menu`, `signals` |
| `celery_schedule_module` | `celery_schedules` |
| `automation_files` | `["load_automation/automation.json"]` |

`registration` runs first in practice because `menu` and `signals` depend on registry entries.

---

## Feature registration (`registration.py`)

```text
register_feature("automation", "automation_models")
```

Apps register models into **`automation_models`**. The universal **`post_save`** / **`pre_delete`** receivers in `signals.py` **only** continue if `sender` is in that registry list—this keeps automation overhead off unrelated tables.

---

## Menu (`menu.py`)

`AutomationSettings` (`@settings_menu.register`):

- Section title **Automations**, icon `/assets/icons/automation.svg`, `order = 4`.
- First item: **Mail & Notifications** → `automations:automation_view` with HTMX targeting `#settings-content`, OOB `#settings-sidebar`, fragment `#automation-view`.
- Permission gate: `automation.view_horillaautomation`.

---

## Models (`models.py`)

### `HorillaAutomation`

- **`title`** (unique), **`method_title`** (internal/slug-like, `editable=False`).
- **`model`** → `HorillaContentType`, `limit_choices_to=limit_content_types("automation_models")`.
- **`trigger`** — `on_create` | `on_update` | `on_create_or_update` | `on_delete` | `scheduled`.
- **`delivery_channel`** — `mail` | `notification` | `both`.
- **Templates** — FK to **`HorillaMailTemplate`**, **`NotificationTemplate`** (validated in `clean()` based on channel).
- **"+ Add" for templates** — the form view sets `dynamic_create_fields` / `dynamic_create_field_mapping` so the Mail Template and Notification Template selects get an "+ Add" button that opens the generic dynamic-create popup (Summernote body/message via `rich_text_fields`, insert-field tools, module pre-filled from `TemplateFieldsView`'s `model_id`). It needs `mail.add_horillamailtemplate` / `notifications.add_notificationtemplate`; the new template is added to the select and chosen.
- **Owner fields** — `HorillaAutomationForm` uses `OwnerQuerysetMixin`, so owner querysets are restricted like other forms.
- **`mail_server`** — optional outgoing **`HorillaMailConfiguration`**.
- **`mail_to`** — rich text rules: literals, `self`, `instance.owner.email`, etc. (see field `help_text` in code).
- **`also_sent_to`** — extra users (M2M).
- **Scheduled-only fields** — `schedule_date_field`, offset amount/direction/unit, `schedule_run_time`; required combinations validated in `clean()`.
  - `schedule_run_time` is optional; when set, the scheduler task holds off running that automation until this time has passed. It's interpreted in the automation's own timezone — `created_by.time_zone`, falling back to `company.time_zone`, then UTC — not the raw server clock (see `tasks.py` below).
- **Edge trigger.** An `on_update` automation can set `additional_info["edge_trigger_only"] = True` so it fires only when a condition newly becomes true, not on later edits of a record that already matched. The model must expose a pre-save snapshot as `_old_<field>` (Opportunity amount does this in `horilla_crm/opportunities/signals.py` for Big Deal Alert). Automations that leave the flag unset are unchanged.
- **Recipient timezone.** Mail and notification templates render bare datetime variables (`{{ instance.due_datetime }}`) in each recipient's `time_zone` (else UTC). The send thread calls `timezone.activate` because a background thread has no active timezone; `MockRequest` only backs filters such as `user_datetime_format`.

### `AutomationCondition`

- Links to an automation; stores **field**, **condition** operator (custom `CONDITIONS` list), **value**, ordering, and logical grouping for AND/OR evaluation in `methods.py`.

### `AutomationRunLog`

- Prevents duplicate scheduled sends and stores execution metadata (see model for fields used by scheduler).

`HorillaAutomation` is a normal **`HorillaCoreModel`** (company-scoped, audited). Related condition/runlog rows cascade with the automation.

---

## Signals (`signals.py`)

- **`is_running_migrations()`** — skips handlers during `migrate` or before `auditlog_logentry` exists to avoid boot-time errors.
- **`post_save`** (`trigger_automations_on_save`) — if sender is in `FEATURE_REGISTRY["automation_models"]` and matching `HorillaAutomation` rows exist for that content type, computes `on_create` vs `on_update`, builds **`request_info`** from `_thread_local.request` (user, company, META), then dispatches to **`trigger_automations`** (sync or Celery).
- **`pre_delete`** — parallel path for **`on_delete`** triggers.

Thread-local request is populated by **`ThreadLocalMiddleware`** (`horilla.contrib.utils.middlewares`), registered in project settings.

---

## Typical flows

1. Admin enables automation for **Lead** by registering the model under **`automation_models`** (in that app’s `registration.py`).
2. Admin creates a **HorillaAutomation** row with trigger `on_create_or_update` and a mail or notification template. Those fields offer **+ Add**, which opens the generic dynamic-create popup (pre-filled with the automation's module, limited to models allowed for that template) and selects the new template.
3. User saves a lead → signal runs → conditions evaluated → mail/notification sent.
4. Scheduled automation: Celery beat hits `celery_schedules` → `run_scheduled_automations` resolves "today"/"current time" in the automation's own timezone (`created_by.time_zone` → `company.time_zone` → UTC) → honors `schedule_run_time` in that timezone → loads due rows using date field + offset (via a `__date` lookup for `DateTimeField` targets, exact match for `DateField` targets) → **`AutomationRunLog`** dedupes.

---

## Conditions and fields that aren't model columns

- **Field dropdown** — `AutomationFieldChoicesView` builds the condition field list after a module is chosen; `HorillaAutomationForm._get_model_field_choices` builds it on first render. The view exposes `get_extra_field_choices(model)` (default `[]`) for fields that aren't model columns, and the form method can be overridden by a `FormExtension`.
- **Evaluation** — `evaluate_condition(condition, instance)` first asks `evaluate_extension_condition` (see [condition_fields.md](../generics/forms/condition_fields.md#conditionfieldprovider-extension-seam)); when an extension owns the field the value is compared as text with `_compare_generic_operator`, otherwise the model field is read as before. Cadences reuse this function, so they get the same behaviour.

---

## Related documentation

- Mail templates and servers: [../mail/mail.md](../mail/mail.md)
- Notifications templates: [../notifications/notifications.md](../notifications/notifications.md)
- Feature registry: [../core/Registry/feature.md](../core/Registry/feature.md)
