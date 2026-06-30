# Horilla Notifications app — deep dive (`horilla.contrib.notifications`)

## What this app does

- Persists **in-app notifications** per user (`Notification`).
- Stores **sound mute** preference per user (`NotificationSoundPreference`).
- Provides **NotificationTemplate** (`HorillaCoreModel`) for automation-driven renders.
- Powers the bell dropdown / list views in the main shell and supplies context via **`horilla.context_processors.unread_notifications`** (see [../../context_processors.md](../../context_processors.md)).
- **REST API** at `notifications/`.

---

## App startup (`apps.py`)

`NotificationsConfig`:

| Setting | Value |
|---------|--------|
| `url_prefix` | `notifications/` |
| `url_namespace` | `notifications` |
| `auto_import_modules` | `registration`, `signals`, `menu` |
| API | `notifications/` → `horilla.contrib.notifications.api.urls` |

---

## Feature registration (`registration.py`)

```text
register_feature("notification_template", "notification_template_models")
```

Models that expose merge fields for **notification templates** register under **`notification_template_models`**.

---

## Models (`models.py`)

### `Notification` (`models.Model`)

Lightweight row (not `HorillaCoreModel`) for high volume:

- FK **`user`**, **`read`** flag, **`created_at`**, payload/title/body fields and optional link target (see model for exact columns).
- Queried by context processor: `filter(user=request.user, read=False).order_by("-created_at")`.

### `NotificationSoundPreference`

- One-to-one style link to user; **`sound_muted`** boolean. Missing row ⇒ treat as unmuted (`False`).

### `NotificationTemplate`

- Company-aware template used by **Automations** when `delivery_channel` includes notification.
- Extends **`HorillaCoreModel`** for permissions and audit.

---

## Forms (`forms.py`)

### `NotificationTemplateForm` (`forms.ModelForm`)

Same layout pattern as mail templates: **`field_order`**, **`fields = "__all__"`**, manual audit **`exclude`** (not `HorillaModelForm`).

- **`field_order`**: `title`, `content_type`, `message`, `company`
- **`Meta.exclude`**: `is_active`, `created_at`, `updated_at`, `created_by`, `updated_by`, `additional_info`
- **`company`** remains visible on the form
- **`clean_title`** / **`clean_message`**: non-empty validation (unchanged)

---

## Signals (`signals.py`)

Receivers create notifications when:

- Other apps call helper functions, or
- Automations enqueue notification delivery.

Exact senders are listed in `signals.py` (import side effects register receivers).

---

## Channels / real-time (if enabled)

Horilla CRM may push notification events over **Django Channels** (see `horilla.contrib.notifications.consumers` or project routing). Template shell often uses HTMX polling or WS for unread badge counts—confirm in frontend assets for your branch.

### Channel layer default

Project settings in **`horilla/settings/base.py`** default to:

```python
"BACKEND": "channels.layers.InMemoryChannelLayer"
```

This suits local/single-process ASGI. For multiple workers or hosts, switch to **`channels_redis.core.RedisChannelLayer`** (see [settings/base.md](../../settings/base.md#-channels-channel_layers)).

In-memory backends do not broadcast across processes; Redis is required when more than one ASGI worker must receive the same channel events.

---

## Typical flows

1. Automation sets **`delivery_channel=notification`** → template render → `Notification` row inserted for target users.
2. User loads any page → context processor adds **`unread_notifications`** queryset + **`notification_sound_muted`**.
3. User marks read via HTMX POST → view flips `read=True`.

---

## Related documentation

- Automations: [../automations/automations.md](../automations/automations.md)
- Context processors: [../../context_processors.md](../../context_processors.md)
