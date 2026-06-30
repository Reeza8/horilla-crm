# Horilla Activity app — deep dive (`horilla.contrib.activity`)

## What this app does

- Central **Activity** model for **events**, **meetings**, **tasks**, and **log calls** in one table (discriminated by `activity_type`).
- Links each row to **any registered record** via `HorillaContentType` + `object_id` + `GenericForeignKey` (`related_object`), limited by the **`activity_related`** feature registry (see `registration.py`).
- Surfaces in the UI under the **Schedule** sidebar section (sub-section menu) with HTMX navigation into `#mainContent`.
- Exposes a **REST API** under `/activity/` for external clients.

---

## App startup (`apps.py`)

`ActivityConfig` (`AppLauncher`):

| Setting | Value |
|---------|--------|
| `name` | `horilla.contrib.activity` |
| `label` | `activity` |
| `verbose_name` | Activity |
| `url_prefix` | `activity/` |
| `url_module` | `horilla.contrib.activity.urls` |
| `url_namespace` | `activity` |
| `auto_import_modules` | `registration`, `methods`, `menu`, `signals` |

`get_api_paths()` registers `/activity/` → `horilla.contrib.activity.api.urls` (`activity_api`, namespace `activity`).

`signals.py` is imported at startup but currently contains **no receivers** (reserved for future hooks).

---

## Feature registration (`registration.py`)

- **`register_feature("activity_related", "activity_related_models")`** — other apps register models under this key so they appear as valid **related** types for activities (`limit_content_types` on `Activity.content_type`).
- **`register_model_for_feature(..., model_name="Activity", features=["global_search", "automation"])`** — Activities participate in **global search** and can be targets/sources for **automations** (when automation rules reference the activity model).

Without `register_model_for_feature`, the four-layer permission system would not expose standard `activity.*` permissions for `Activity`.

---

## Menu (`menu.py`)

`ActivitySubSection` is registered with `@sub_section_menu.register`:

- **`section`** = `"schedule"` (groups with other schedule apps in the sidebar).
- **`app_label`** = `"activity"` (identity for ordering/placement).
- **`position`** = `2`.
- **`verbose_name`** / **`icon`** — user-visible label and `/assets/icons/activity.svg`.
- **`url`** — `reverse_lazy("activity:activity_view")`.
- **`attrs`** — `MAIN_CONTENT_HX_ATTRS` so list/detail loads via HTMX into the main shell.
- **`perm`** — `["activity.view_activity", "activity.view_own_activity"]` (either permission allows the menu entry; row-level **own** filtering still applies in views via `OWNER_FIELDS`).

---

## Model: `Activity` (`models.py`)

### Base and tenancy

- Extends **`HorillaCoreModel`** (`company`, audit fields, `is_active`, etc.).
- **`OWNER_FIELDS = ["owner", "assigned_to"]`** — enables **view_own_** / **change_own_** style filtering in list views and APIs.

### Polymorphic shape

- **`activity_type`** — `event` | `meeting` | `task` | `log_call`.
- **`status`** — workflow states (`not_started`, `scheduled`, `in_progress`, …); indexed for reporting and list filters.
- **Common fields** — `subject`, `description`, datetimes, `location`, `is_all_day`, M2M **`assigned_to`** / **`participants`**, FK **`meeting_host`**, FK **`owner`**.

### Generic relation

- **`content_type`** → `HorillaContentType`, limited to **`activity_related_models`**.
- **`object_id`** + **`related_object`** — the business record this activity is about (user, lead, contact, etc., depending on what apps register for `activity_related`).

### Type-specific columns

- **Meeting** — `is_online`, `meeting_provider`, `meeting_url` (generated on save), `meeting_host`, M2M `participants`, `external_participants` (JSON email list), `reminder`, FK `mail_template` (invitation override).
- **Task** — `task_priority`, `due_datetime`, `recipient_email`.
- **Log call** — `call_type`, `call_duration_display` / `call_duration_seconds` (computed in `clean()` and `save()` from `HH:MM:SS`), `call_purpose`, `notes`.
- **Calendar sync** — `google_event_id` (indexed; excluded from user-facing forms).

### Indexes

Composite-friendly indexes on `activity_type`, `created_at`, `status`, `start_datetime`, `due_datetime` for list dashboards and calendar views.

### URL helpers

`get_detail_url`, `get_edit_url` (per-type named URLs), `get_activity_edit_url`, `get_delete_url` — used by generics, timeline rows, and mail templates.

### List / inline UI

- **`status_col`** / **`get_status_update_html`** — render partials via `render_template()` for inline status changes in list views.

---

## Forms (`forms.py`)

All activity create/update modals use **`OwnerQuerysetMixin, HorillaModelForm`** (see [single-step form base](../generics/forms/single_step.md)).

### HorillaModelForm layout (`field_order` + `Meta`)

Each dedicated form class now uses:

| Pattern | Purpose |
|---------|---------|
| `field_order` | Default field order for `HorillaSingleFormView` |
| `Meta.fields = "__all__"` | All `Activity` columns unless excluded |
| `Meta.exclude` | Hide columns for **other** activity types (and computed/system fields) |
| Auto `HORILLA_FORM_EXCLUDE` | `company`, `is_active`, `created_at`, `updated_at`, `created_by`, `updated_by`, `additional_info` — do **not** repeat these in `Meta.exclude` |

Shared **computed / system** fields (listed in `exclude` where relevant):

| Field | Reason |
|-------|--------|
| `meeting_url` | Set on save when an online meeting is generated |
| `external_participants` | Filled in `clean()` from `external_participants_email` POST key |
| `call_duration_seconds` | Set in `LogCallForm.clean()` from `call_duration_display` |
| `google_event_id` | Google Calendar sync only; pull sync maps datetimes in `google_calendar/sync.py` (`end_dt = max(end_dt, start_dt)` guard) — see [../calendar/calendar.md](../calendar/calendar.md#google-calendar-sync-google_calendarsyncpy) |

`__init__`, `clean()`, HTMX paths, and helper methods are unchanged from the prior implementation; only `field_order` and `Meta` were updated to match the Horilla 1.10 form pattern.

### Form classes

| Class | View | Purpose |
|-------|------|---------|
| `MeetingsForm` | `MeetingsCreateForm` | Dedicated meeting modal |
| `LogCallForm` | `CallCreateForm` | Log call modal |
| `EventForm` | `EventCreateForm` | Event modal |
| `ActivityCreateForm` | `ActivityCreateView` | Multi-type create/edit (calendar, New activity) |

Named URL routes (for reference): `activity:meeting_create_form`, `activity:meeting_update_form`, `activity:call_create_form`, `activity:call_update_form`, `activity:event_create_form`, `activity:event_update_form`, `activity:activity_create_form`, `activity:activity_edit_form`.

### `MeetingsForm`

- **`field_order`**: `object_id`, `content_type`, `title`, `subject`, `status`, `owner`, `start_datetime`, `end_datetime`, `participants`, `meeting_host`, `is_all_day`, `is_online`, `location`, `meeting_provider`, `reminder`, `mail_template`, `activity_type`.
- **`Meta.exclude`**: task/call/event-only fields plus `meeting_url`, `external_participants`, `google_event_id` (see `forms.py`).
- **Extra field**: class-level `meeting_provider` `ChoiceField` (choices filled in `__init__` from connected Zoom / Google Meet / Teams).
- **HTMX**: hardcoded `/activity/meeting-create-form/` and `/activity/meeting-update-form/<pk>/` paths on `is_all_day` / `is_online`; `is_online` POST uses `_toggle_field=is_online`.
- **`__init__`**: uses `kwargs.pop("request")` as `self._request` for provider lookup (legacy pattern on this form).

### `LogCallForm`

- **`field_order`**: `object_id`, `content_type`, `subject`, `owner`, `call_purpose`, `call_type`, `call_duration_display`, `status`, `notes`, `activity_type`.
- **`Meta.exclude`**: meeting/event/task schedule fields and system fields such as `call_duration_seconds`, `meeting_url`, `google_event_id`.
- **`clean_call_duration_display`** / **`clean`**: `HH:MM:SS` validation; persists `call_duration_seconds`.

### `EventForm`

- **`field_order`**: `object_id`, `content_type`, `title`, `subject`, `owner`, `start_datetime`, `end_datetime`, `location`, `assigned_to`, `status`, `is_all_day`, `activity_type`.
- **`Meta.exclude`**: meeting/call/task-specific and system fields.
- **HTMX**: `/activity/event-create-form/` and `/activity/event-update-form/<pk>/` on `is_all_day`; hides start/end datetimes in `__init__` when all-day is checked.

### `ActivityCreateForm`

- **`field_order`**: full cross-type ordering (activity type first, then shared and type-specific columns).
- **`Meta.exclude`**: only `meeting_url`, `external_participants`, `call_duration_seconds`, `google_event_id` (all other type-specific fields stay on the form and are shown/hidden at runtime).
- **`visible_fields`**: `ActivityCreateView.get_form_kwargs()` passes a subset from **`ACTIVITY_FIELD_MAP`** per `activity_type` (`event`, `meeting`, `task`, `log_call`, `email` placeholder).
- **HTMX**: `activity_type` / `content_type` reload via `/activity/activity-create-form/` or edit URL with optional `?view=calendar`; `object_id` Select2 uses `reverse_lazy("generics:model_select2", …)`; meeting branch calls `_configure_activity_meeting_fields(base_url)`.
- **Calendar**: drops `log_call` and `email` from `activity_type` choices when `?view=calendar`.

### Extending activity forms

1. Add the column on `Activity` (or model `_inherit` in an extension app).
2. Add the name to **`field_order`** and remove it from **`Meta.exclude`** on the form class that should show it (or add to `ACTIVITY_FIELD_MAP` for `ActivityCreateForm`).
3. Keep widgets, HTMX, and validation in `__init__` / `clean` on the concrete form (see [form extension](../../extension/form_extension.md)).

---

## Kanban views (`views/core.py`)

| View | Purpose |
|------|---------|
| `AcivityKanbanView` | All-type activity kanban (backward compatible); groups by `status` |
| `AllActivityKanbanTabbedView` | Tabbed kanban — one activity type per tab |

### `AcivityKanbanView.update_kanban_item` override

The generic kanban POST handler normally re-renders `partials/kanban_blocks.html` inline. Activities override this because the view registry maps **Activity → one kanban class for all types**, while tabbed UIs each show a single `activity_type`.

After drag-drop:

1. Resolves the model with **`horilla.apps.apps.get_model()`** (not `django.apps`).
2. Type-checks FK group fields with **`horilla.db.models.ForeignKey`** (not `django.db.models`).
3. Saves the status (or FK) change on the item.
4. Returns `<script>$('#reloadButton').click();</script>` so the active tab's kanban reloads instead of swapping a partial that would mix all activity types.

Permission checks use `can_user_modify_item()`; failures also trigger `#reloadButton`.

---

## Create/update views (`views/create_view/`)

All four views extend **`HorillaSingleFormView`** with **`ActivityOwnerPermissionMixin`**, **`LoginRequiredMixin`**, and `@method_decorator(htmx_required, name="dispatch")`.

### Common patterns

- **`@cached_property form_url`** — returns the create URL when no `pk` is present, the update URL otherwise (avoids re-computing on every render).
- **Object linking** — `GET` params `object_id`, `model_name`, and `app_label` bind the activity to any registered CRM record (passed via `get_initial()`).
- **HTMX close + tab reload** — `form_valid()` returns a script that triggers the relevant tab button click (`#CallsTab`, `#EventTab`, `#MeetingsTab`) and calls `closeModal()`.

### `CallCreateForm` (`views/create_view/call.py`)

| Attribute | Value |
|-----------|-------|
| Form | `LogCallForm` |
| Named URLs | `activity:call_create_form` / `activity:call_update_form` |
| Create default | `call_duration_display` initialised to `"00:00:00"` in `get_initial()` |
| HTMX trigger | Clicks `#CallsTab` and closes modal on save |

### `EventCreateForm` (`views/create_view/event.py`)

| Attribute | Value |
|-----------|-------|
| Form | `EventForm` |
| Named URLs | `activity:event_create_form` / `activity:event_update_form` |
| `get_initial()` | Handles `is_all_day` toggle state from GET param, POST data, or existing object |
| `toggle_is_all_day` | GET param `toggle_is_all_day=1` flips the value before re-rendering the form |
| `get_form_kwargs()` | Passes raw GET data as `initial` values to the form |
| HTMX trigger | Clicks `#EventTab` and closes modal on save |

### `MeetingsCreateForm` (`views/create_view/meeting.py`)

| Attribute | Value |
|-----------|-------|
| Form | `MeetingsForm` |
| Named URLs | `activity:meeting_create_form` / `activity:meeting_update_form` |
| Toggles | `is_all_day` and `is_online` both handled; `content_type` resolved from `model_name` when missing |
| `_toggle_field` | `"is_online"` — a POST to the form URL with `_toggle_field=is_online` re-renders the form in-place without saving |
| `form_valid()` | Calls `generate_meeting_url()`, sends invitations to participants and external emails, updates external participants list |
| Helper methods | Instance methods bridge to `meeting_helpers` functions |
| HTMX trigger | Clicks `#MeetingsTab` and closes modal on save |

### Meeting emails and branding

`meeting_helpers.send_meeting_invites()` and Celery `tasks._send_reminder_for_meeting()` set template `company_name` to `str(company)` when a company is available, otherwise **`str(load_branding()["TITLE"])`** from `horilla.utils.branding.load_branding()` (driven by `settings.BRANDING_MODULE`).

### `ActivityCreateView` (`views/create_view/activity.py`)

| Attribute | Value |
|-----------|-------|
| Form | `ActivityCreateForm` |
| Named URLs | `activity:activity_create_form` / `activity:activity_edit_form` |
| Field map | `ACTIVITY_FIELD_MAP` drives visible fields per `activity_type` |
| Calendar mode | `?view=calendar` drops `log_call` and `email` from type choices; pre-fills datetimes |
| Meeting branch | `is_online` partial POST re-renders form; `generate_meeting_url()` + invites on save |

---

## Typical flows

1. User opens **Activities** from the schedule sub-menu → HTMX loads `activity_view` into the shell.
2. User creates a **task** linked to a **lead** → `content_type`/`object_id` set; `owner`/`assigned_to` drive row permissions.
3. Automations or cadences create **Activity** rows (task/call/email) with due dates → same model, different `activity_type`.
4. Global search indexes activity subjects/titles when the feature registry includes the model.

---

## UI details — call sub-tab styling (`activity_tab.html`)

The **Pending Calls** and **Completed Calls** sub-tab buttons inside the activity tab include the `cursor-pointer` CSS class. This ensures the browser renders a pointer cursor on hover, giving users a consistent clickable affordance on both sub-tabs without requiring any JavaScript.

---

## Related documentation

- Core models and `HorillaContentType`: [../core/models.md](../core/models.md)
- Feature registry: [../core/Registry/feature.md](../core/Registry/feature.md)
- **`HorillaModelForm` (single-step forms)**: [../generics/forms/single_step.md](../generics/forms/single_step.md)
- **`HorillaSingleFormView`**: [../generics/views/toolkit/single_form_builder.md](../generics/views/toolkit/single_form_builder.md)
- Form extension (`_inherit_form` plan): [../../extension/form_extension.md](../../extension/form_extension.md)
- Meeting integration (URLs, OAuth): [../meeting/meeting.md](../meeting/meeting.md)
- Google Calendar pull/push sync: [../calendar/calendar.md](../calendar/calendar.md#google-calendar-sync-google_calendarsyncpy)
- Generics list/detail patterns: [../generics/views/list.md](../generics/views/list.md), [../generics/views/details.md](../generics/views/details.md)
- Module version metadata: `horilla/contrib/activity/__version__.py`
