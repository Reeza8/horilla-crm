# Horilla Calendar app — deep dive (`horilla.contrib.calendar`)

## What this app does

- **User preferences** for calendar display and sync.
- **Availability** blocks for scheduling.
- **Custom calendars** and **conditions** (org-defined views/filters).
- **Google Calendar** OAuth-style settings and per-user/config rows for sync.
- Exposes **REST API** at `/calendar/` for SPA or integrations.

---

## App startup (`apps.py`)

`CalendarConfig`:

| Setting | Value |
|---------|--------|
| `url_prefix` | `calendar/` |
| `url_namespace` | `calendar` |
| `auto_import_modules` | `registration`, `menu`, `signals` |
| API | `/calendar/` → `horilla.contrib.calendar.api.urls` |

---

## Feature registration (`registration.py`)

- Registers the **`custom_calendar`** feature with registry key **`custom_calendar_models`** (`auto_register_all=False`). Apps opt in models that can participate in custom calendar definitions.

## Menu (`menu.py`)

Registers main / floating entries for the calendar shell view and Google settings (see source for `reverse_lazy` names, icons, and `perm` strings).

---

## Models (`models.py`) — overview

### `UserCalendarPreference`

Per-user defaults: visible calendars, time slot length, week start, sync toggles, etc. (see field definitions in `models.py`).

### `UserAvailability`

Recurring or dated availability windows; used when suggesting meeting times or conflict detection.

### `CustomCalendar` / `CustomCalendarCondition`

Organizations define named calendars and rule rows (similar spirit to report conditions) to filter which activities or events appear.

### `GoogleIntegrationSetting` / `GoogleCalendarConfig`

Store integration credentials/config scopes and mapping between Horilla users and Google calendars. Used by views under `templates/google_calendar/` and sync tasks.

All primary models extend **`HorillaCoreModel`** unless noted otherwise in code—company isolation applies.

---

## Signals (`signals.py`)

Used for:

- Keeping Google tokens refreshed or invalidating on error (check receivers).
- Invalidating caches when preferences change.

(Read `horilla/contrib/calendar/signals.py` for the authoritative list of senders.)

---

## Google Calendar sync (`google_calendar/sync.py`)

Pull sync maps Google Calendar events into `Activity` rows via `_upsert_activity_from_google(gevent, config)`.

### Datetime handling on pull

| Step | Behavior |
|------|----------|
| Parse | `start_dt` / `end_dt` from Google `start` / `end` via `_parse_google_datetime` |
| All-day | When Google sends date-only start, normalize to `09:00`–`10:00` on that day and treat as timed |
| End guard | `end_dt = max(end_dt, start_dt)` so end is never before start (covers malformed or equal Google payloads) |

Other pull rules in the same helper:

- **Type:** `extendedProperties.private.horilla_event_type` first, else map Google `eventType` (`default` → `event`, `focusTime` / `outOfOffice` / `workingLocation` → `task`).
- **Subject:** strip Horilla push prefixes (`[Task]`, `[Event]`, etc.) from `summary`.
- **Status:** preserve existing Horilla `completed` status; Google events do not carry completion state.
- **Skip:** `birthday`, `fromGmail` event types are not imported (handled by caller).

Push and token refresh logic live in the same module; see source for `_push_activity_to_google` and sync entry points.

---

## Forms (`forms.py`)

### `CustomCalendarForm` (`HorillaModelForm`)

- **`field_order`**: `name`, `color`, `module`, `start_date_field`, `end_date_field`, `display_name_field`, `is_selected`
- **`Meta.fields = "__all__"`**, **`Meta.exclude = ["user"]`** — `user` is set on create in the view, not on the form
- **`htmx_field_choices_url`**: `generics:get_model_field_choices`
- **`__init__`**: HTMX GET reload merges query params into `initial`; date/display field choices rebuilt from selected `module` (unchanged)

### Other forms

- **`GoogleSyncDirectionForm`** / **`GoogleCredentialsUploadForm`** — plain `forms.Form` / `ModelForm`; not part of the `__all__` refactor

See [single-step form base](../generics/forms/single_step.md) for `HORILLA_FORM_EXCLUDE` on `HorillaModelForm`.

---

## Templates and UX

- Main shell calendar: `horilla/contrib/calendar/templates/calendar.html` (extends project layout; HTMX loads events).
- Google settings partials: `templates/google_calendar/`.

---

## Typical flows

1. User opens **Calendar** from the menu → week/month view loads activities whose datetimes fall in range.
2. User connects **Google** in settings → OAuth flow writes `GoogleCalendarConfig` → sync jobs create/update **`Activity.google_event_id`** rows on the activity app.
3. Mobile or SPA hits **`/calendar/`** API → serializers return JSON blocks consistent with web filters.

---

## Related documentation

- Activity model (events/tasks tied to Google IDs): [../activity/activity.md](../activity/activity.md)
- Dashboard home may embed calendar widgets: [../dashboard/dashboard.md](../dashboard/dashboard.md)
