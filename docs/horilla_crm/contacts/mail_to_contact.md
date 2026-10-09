# Mail to Contact (`horilla_crm.contacts.utils`, `horilla_crm.contacts.registration`)

## What this feature does

Lets an incoming email be converted into a **Contact** — either automatically (an `EmailToLeadConfig` with `create_as="contact"`, see [Mail to Lead / Contact](../leads/mail_to_lead.md)) or interactively, via the Inbox screen's **"Add as Contact"** row action (`horilla/contrib/mail/views/inbox.py`). Both paths call the same helpers in this file, so behavior is identical either way.

Unlike `Lead` (which had no email-uniqueness constraint before this feature), **Contact dedup is email-address-based** — this didn't exist at all before this feature was built.

See also: [Incoming mail / Inbox](../../horilla/contrib/mail/mail.md#incoming-mail--inbox-incomingmail-actionspy-fetch_hookspy) for the generic registry machinery this plugs into, and [Mail to Lead / Contact](../leads/mail_to_lead.md) for the `EmailToLeadConfig`/automatic-pipeline side.

---

## Model changes (`contacts/models.py`)

- **`message_id`** (new): `CharField(max_length=255, unique=True, null=True, blank=True, editable=False)`. Set only when a Contact was created from an email; mirrors `Lead.message_id`'s existing role exactly — no new FK/relationship was added purely for "link back to the source email", since matching on this field and looking up `IncomingMail.objects.get(message_id=...)` on demand was simpler and consistent with the existing Lead convention.
- **`contact_source`** choices (`CONTACT_SOURCE_CHOICES`) extended with `("email", _("Email"))`.
- **`address_country`** relaxed to `blank=True, default=""` — raw emails don't supply a country, and this was the only hard-required field (besides `contact_owner`, which stays required and is always supplied by the request's user or the config's `lead_owner`) blocking a Contact from being created with just a sender email/name.

---

## Helpers (`contacts/utils.py`)

### `find_duplicate_contact(email, company)`

`Contact.objects.filter(email__iexact=email, company=company).first()` — the one place Contact dedup logic lives; both the automatic pipeline and the Inbox action predicate/warning call through this, never duplicating the query.

### `contact_already_exists_for_mail(incoming_mail, request)`

The Inbox action's `already_exists_check`: `True` if the sender already has a Contact, **even if this particular message was never itself converted** — e.g. a second email from someone already added as a Contact. Drives the Inbox's hide/disable logic for the "Add as Contact" button on that row (see `horilla/contrib/mail/views/inbox.py`'s `_is_action_blocked`).

### `create_contact_from_email(incoming_mail, request, owner=None)`

1. Runs `find_duplicate_contact` first — if a match exists in the company, returns the **existing** Contact unchanged (no duplicate created). Return shape mirrors Django's `get_or_create`: `(contact, created)`.
2. Otherwise splits `incoming_mail.sender_name` into `first_name`/`last_name` on the first space (fallback: whole string as `first_name`, empty `last_name`).
3. Creates `Contact.objects.create(contact_owner=owner or request.user, first_name=..., last_name=..., email=incoming_mail.sender_email, company=request.active_company, contact_source="email", message_id=incoming_mail.message_id)`.

---

## Registration (`contacts/registration.py`)

Registers `key="contact"` via `register_incoming_mail_action` (from `horilla.contrib.mail.actions`):

- `handler` → `_add_as_contact(incoming_mail, request)`, which calls `create_contact_from_email` and returns just the `Contact` (discarding the `created` flag — the Inbox view only needs a result to render, not whether it was newly made).
- `already_exists_check` → `contact_already_exists_for_mail`.
- `icon` → `assets/icons/add_as_contact.svg`.
- `permission` → `contacts.add_contact`.

No `warning_check` is registered for the Contact action (unlike the Lead action's `lead_warning_for_mail`) — creating a Contact for someone who might already have a Lead isn't treated as noteworthy the way "already has a Contact" is surfaced on the Lead side; "Add as Contact" simply reuses the existing Contact silently via dedup instead.

---

## Edge cases / deliberately out of scope

- **Two people sharing an inbox address**: `find_duplicate_contact` matching on email alone means a shared mailbox (e.g. `support@company.com` used by multiple people) will be treated as the same Contact across different senders' names. Not handled specially — flagged as a known limitation of email-based dedup, not a bug.
- **CC-recipient contacts**: not processed; see [Mail to Lead / Contact](../leads/mail_to_lead.md#edge-cases--deliberately-out-of-scope).
