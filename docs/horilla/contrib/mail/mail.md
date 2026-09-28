# Horilla Mail app — deep dive (`horilla.contrib.mail`)

## What this app does

- **Outgoing mail configuration** per channel (SMTP, etc.) via **`HorillaMailConfiguration`**.
- **Message queue / history** via **`HorillaMail`** and **`HorillaMailAttachment`**.
- **Reusable HTML templates** via **`HorillaMailTemplate`** (seeded from `load_template/template.json` on install).
- **Celery** tasks in `tasks.py` for async send; **`scheduler`** module for periodic mail jobs.
- **REST API** at `mail/` for mobile/integrations.

---

## App startup (`apps.py`)

`MailConfig`:

| Setting | Value |
|---------|--------|
| `url_prefix` | `mail/` |
| `url_namespace` | `mail` |
| `auto_import_modules` | `registration`, `signals`, **`scheduler`**, `menu` |
| `celery_schedule_module` | `celery_schedules` |
| `template_files` | `["load_template/template.json"]` |
| API | `mail/` include → `horilla.contrib.mail.api.urls` |

---

## Feature registration (`registration.py`)

```text
register_feature("mail_template", "mail_template_models")
```

Models that expose themselves under **`mail_template_models`** can be selected when building mail templates with merge fields / loops (see mail template editor views).

---

## Models (`models.py`) — concepts

### `HorillaMailConfiguration`

- Stores host, port, username, **`EncryptedCharField`** for **password** and **Outlook client secret**, TLS, default from-address, **`mail_channel`** (`incoming` / `outgoing`) for limit choices on automations.

### `HorillaMail`

- One row per send attempt: headers, body snapshot, status, FK to template used, link to triggering user/company.
- **`rendered_subject`** / **`rendered_body`** — HTML/text snapshot of the template (or compose body) **persisted at send time**, so later preview of a sent message does not re-render against live template context (avoids stale or privileged context leaks).

### `HorillaMailAttachment`

- File rows bound to a parent mail message (`upload_path` pattern from `horilla.utils.upload`).

### `HorillaMailTemplate`

- Named template with HTML body; referenced by **Automations**, **Cadences**, and manual compose UIs.

---

## Forms (`forms.py`)

### `HorillaMailTemplateForm` (`forms.ModelForm`, not `HorillaModelForm`)

- **`field_order`**: `title`, `subject`, `content_type`, `body`, `company`
- **`Meta.fields = "__all__"`**
- **`Meta.exclude`**: `is_active`, `created_at`, `updated_at`, `created_by`, `updated_by`, `additional_info` — **`company` stays on the form** (manual exclude list, same effect as `keep_on_form` on `HorillaModelForm`)
- Used by **`MailTemplateCreateUpdateView`** (`FormView`, not `HorillaSingleFormView`)

### `SaveAsMailTemplateForm`

- Still uses explicit **`fields = ["title", "body", "company", "content_type"]`** (unchanged)

### Mail configuration (`HorillaModelForm`)

| Form | `keep_on_form` | `Meta.exclude` (high level) |
|------|----------------|----------------------------|
| **`HorillaMailConfigurationForm`** (outgoing SMTP) | `company` | Outlook/OAuth fields (`outlook_*`, `token`, `oauth_state`, `last_refreshed`) |
| **`IncomingHorillaMailConfigurationForm`** | `company` | Outgoing-only SMTP + Outlook/OAuth fields |
| **`OutlookMailConfigurationForm`** | `company` | SMTP fields (`host`, `port`, `from_email`, model `password`, TLS/SSL, …) + token/oauth |

Each configuration form declares a class-level **`password`** or **`outlook_client_secret`** `CharField` override. **`__init__`** required-field logic is unchanged.

### Other

- **`DynamicMailTestForm`**, **`MailTemplateSelectForm`** — plain `forms.Form`; unchanged

---

## Signals (`signals.py`)

Common patterns:

- Update counters or audit when mail delivery status changes.
- Invalidate caches for inbox widgets.

Read `horilla/contrib/mail/signals.py` for concrete `@receiver` blocks.

---

## Scheduler (`scheduler.py`)

Registers APScheduler / Celery beat entries for mailbox sync or retry queues (implementation-specific—read module).

---

## Open tracking (`services.py`, `views/core/track.py`)

Outbound HTML from **`HorillaMailManager.send_mail()`** appends a 1×1 tracking pixel when the body is HTML:

1. **`reverse("mail:track_open", kwargs={"uid": str(mail.tracking_uid)})`** — built via `horilla.urls.reverse` (not `django.urls`).
2. **`SITE_URL`** from settings, or the current request's absolute URI (honours `X-Forwarded-Host` / `X-Forwarded-Proto` for ngrok and reverse proxies).
3. An invisible `<img>` tag is appended to the HTML body before SMTP send.

**`TrackOpenView`** (`mail/track-open/<uuid:uid>/`, name `mail:track_open`):

- Public GET endpoint (no login).
- Looks up `HorillaMail` by `tracking_uid`.
- On first open: sets `opened_at`, updates `mail_status` to `"opened"`, saves.
- Returns a transparent GIF via **`horilla.web.HttpResponse`** (`content_type="image/gif"`).

Model fields involved: `HorillaMail.tracking_uid` (UUID, set on create), `opened_at`, and `mail_status` choice `"opened"`.

---

## Mail templates list & preview

### `MailTemplateListView`

- Gated by **`mail.view_horillamailtemplate`**.
- Title column `col_attrs` load the detail modal only when the user has that view permission (pointer/HX attrs omitted otherwise).
- Row actions use the correct permission codenames (`change_horillamailtemplate`, `delete_horillamailtemplate`).

### Preview (`views/core/preview_draft.py`)

- Preview renders **`rendered_subject` / `rendered_body`** when present, otherwise a fresh render; HTML is passed through **`sanitize_html`** before display.
- Access checks ensure the user can only preview drafts/messages they are allowed to see (IDOR guard on the mail row).
- Template-error / XSS false positives surface via `mail_preview_error.html` rather than treating safe content as blocked.

---

## Typical flows

1. Admin configures **outgoing** server → the mail backend selects a configuration
   scoped to the **active company** with `mail_channel="outgoing"` (preferring the
   primary), not an unrelated or first-global row.
2. **HorillaAutomation** with `delivery_channel=mail` renders **`HorillaMailTemplate`** with context from triggering instance → `HorillaMail` row created → Celery sends SMTP (pixel injected when HTML).
3. User composes one-off mail from record detail → same models, different view.
4. Recipient opens the message → browser loads the pixel → `TrackOpenView` records the first open.

---

## Related documentation

- Automations delivery: [../automations/automations.md](../automations/automations.md)
- Notifications (parallel channel): [../notifications/notifications.md](../notifications/notifications.md)
