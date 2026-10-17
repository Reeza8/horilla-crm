# Mail to Lead / Contact (`horilla_crm.leads.views.mail_to_lead`, `EmailToLeadConfig`)

## What this feature does

Lets an admin configure an incoming mailbox (an `incoming`-channel `HorillaMailConfiguration`, from the generic `mail` app) so that matching emails are automatically converted into either a **Lead** or a **Contact** — admin's choice, per mailbox, not both. This is the automatic counterpart to the Inbox screen's interactive "Add as Lead" / "Add as Contact" row actions (`horilla/contrib/mail/views/inbox.py`); both paths share the exact same creation helpers so behavior is identical regardless of which one ran.

Settings UI label: **"Email to Record"** (not "Mail to Lead") — reflects that a config can produce either record type.

See also: [Incoming mail / Inbox](../../horilla/contrib/mail/mail.md#incoming-mail--inbox-incomingmail-actionspy-fetch_hookspy) in the `mail` app doc for the generic fetch/registry machinery this feature plugs into.

---

## `EmailToLeadConfig` model (`leads/models/base.py`)

| Field | Notes |
|-------|-------|
| `mail` | FK → `HorillaMailConfiguration` (`SET_NULL`) — which incoming mailbox this config watches. |
| `create_as` | `CharField`, choices `"lead"` / `"contact"`, default `"lead"`. A simple either/or per config — **not** a combined "create both" mode. |
| `accept_emails_from` | Comma-separated sender allow-list; blank = accept all senders. |
| `lead_owner` | FK → user; becomes the owner of whichever record type is created (Lead's `lead_owner` or Contact's `contact_owner`). |
| `apply_assignment_rule` | Boolean, default on. When the config creates a **Lead**, checked means assignment rules decide the owner and `lead_owner` is the fallback when nothing matches; unchecked always keeps `lead_owner`. Ignored for Contacts. |
| `keywords` | Comma-separated; required. Email must contain at least one keyword in subject OR body to match. |
| `last_fetched` | Bookkeeping timestamp for the fetch task. |

---

## How it plugs into the generic `mail` app

`horilla/contrib/mail` never imports `horilla_crm` — instead `leads/registration.py` registers **both**:

1. **A fetch hook** (`register_incoming_mail_fetch_hook`, from `horilla.contrib.mail.fetch_hooks`) so the periodic Celery fetch task (`mail/tasks.py`'s `fetch_emails_to_incoming_mail`) can, per mailbox: look up the matching `EmailToLeadConfig` (`get_config`), derive the sender allow-list (`get_allowed_senders`), apply keyword filtering (`matches_filters`), and auto-create a record (`create_record`) once a message is persisted as `IncomingMail`. `create_record` branches on `config.create_as` to call `create_lead_from_email` or `create_contact_from_email`.
2. **An Inbox action** (`register_incoming_mail_action`, from `horilla.contrib.mail.actions`) under `key="lead"`, so the Inbox screen's "Add as Lead" button works independently of whatever `create_as` a config is set to — a user can always manually create a Lead from any fetched message, whether or not an `EmailToLeadConfig` exists at all.

`_ConfigRequest` (a tiny request-like shim in `leads/registration.py`) lets `create_lead_from_email`/`create_contact_from_email` — whose shared contract expects a request object for `request.user`/`request.active_company` — also be driven from the Celery task, which has no real request, only the config's own `lead_owner`/`company`.

---

## Shared creation helpers (`leads/utils.py`, `contacts/utils.py`)

### `create_lead_from_email(incoming_mail, request, owner=None, apply_assignment_rule=True, assignment_decision=None)` — `leads/utils.py`

`build_lead_from_email` fills `first_name` from the sender name, `title` from the subject, `email` from the sender, and `requirements` from the body converted to plain text (`_html_to_text`). It also sets `lead_owner`, the first `LeadStatus`, `company`, `lead_source="email"` and `message_id`. `create_lead_from_email` saves that lead.

- `apply_assignment_rule=False` sets `_skip_assignment_rule` so the post-save engine keeps the given owner (the Email to Record config when the checkbox is off).
- `assignment_decision` is the `(condition, owner)` the Inbox form already settled. The lead keeps that owner and records it in `additional_info` instead of running the rules again. The Inbox confirm step is `InboxAddAsLeadExtension` on `InboxRunActionView` (`leads/view_extensions.py`).

- `Lead.message_id` already existed before this feature (used for reply-thread dedup, `check_existing_thread`) — reused here rather than adding a new field, and it doubles as the link back to the originating `IncomingMail` row (`IncomingMail.objects.get(message_id=lead.message_id)`), mirroring how `Contact.message_id` works on the other side. No `source_mail` FK was added for this purpose.

### `lead_warning_for_mail(incoming_mail, request)` — `leads/utils.py`

The Inbox action's `warning_check`: if the sender already has a **Contact** (via `contacts.utils.find_duplicate_contact`), returns a non-blocking HTML warning with a link to that Contact — doesn't prevent creating the Lead anyway (mirrors Salesforce/HubSpot/Zoho's "warn, don't block" behavior for a genuinely new inquiry from an existing customer). Built with `django.utils.html.format_html` so the interpolated sender email / Contact name / URL are all individually escaped — a maliciously-named Contact can't inject markup into this warning.

### `create_contact_from_email` / `find_duplicate_contact` / `contact_already_exists_for_mail` — `contacts/utils.py`

See [Mail to Contact](../contacts/mail_to_contact.md) for the Contact-side helpers (dedup, name splitting, `contact_source`).

---

## Views (`leads/views/mail_to_lead.py`)

Standard settings-screen shape, same conventions as every other `HorillaListView`-backed config screen in the codebase:

| View | Base | Purpose |
|------|------|---------|
| `MailToLeadView` | `HorillaView` | Settings shell page. |
| `MailToLeadNavbar` | `HorillaNavView` | Navbar; title "Email to Record". |
| `MailToLeadListView` | `HorillaListView` | Lists `EmailToLeadConfig` rows — columns: mailbox, mailbox type, lead owner. Edit/Delete row actions. |
| `MailToLeadFormView` | `HorillaSingleFormView` | Create/update a config (`EmailToLeadForm`, field order includes `create_as`). |
| `EmailToLeadConfigDeleteView` | `HorillaSingleDeleteView` | Deletes a config — the reference example other delete views in this feature (e.g. Inbox's `InboxDeleteView`) were modeled on. |

---

## Edge cases / deliberately out of scope

- **CC-as-contact**: `IncomingMail.cc` is captured and stored, but nothing auto-converts CC'd addresses — flagged as a possible future extension, not built.
- **Thread replies**: `check_existing_thread` checks `Lead.message_id` (and now `IncomingMail.message_id`/`in_reply_to`/`references`) for dedup; a reply in a Contact-only thread (no Lead ever created) is handled via `any_hook_reports_duplicate`/`DeletedIncomingMessageId`, not a Lead-specific thread check.
- **No combined "both" mode**: `create_as` is strictly either/or by design — a user who wants both a Lead and a Contact from the same email creates the first one automatically via the config, then manually clicks the Inbox's other action button on that row.
