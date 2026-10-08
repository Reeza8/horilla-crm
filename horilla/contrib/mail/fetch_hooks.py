"""
Pluggable "incoming mail fetch" hooks.

The periodic fetch task (tasks.py's fetch_emails_to_incoming_mail) walks every configured incoming
mailbox (HorillaMailConfiguration) and always persists each message as an
IncomingMail row, regardless of CRM configuration. Apps such as leads (via
EmailToLeadConfig) can additionally register a hook here to, per mailbox:

  1. look up their own per-mailbox config object (get_config)
  2. derive an allowed-sender filter list from it (get_allowed_senders)
  3. apply keyword/subject/body filters to a candidate message (matches_filters)
  4. auto-create a Lead/Contact once a message is persisted (create_record)
  5. optionally flag a message as an already-seen duplicate even when its
     IncomingMail row no longer exists (is_duplicate_message)

This mirrors horilla/contrib/mail/actions.py's registration pattern so this
app never has to import EmailToLeadConfig/Lead/Contact: CRM apps register
callables, and this app only ever calls through these opaque interfaces.

Multiple hooks can register (e.g. leads today, a future second CRM app
tomorrow). For a given mailbox, resolve_fetch_hook_for_mailbox() picks the
first registered hook whose get_config() returns a non-None config for that
mailbox - a message is only ever auto-converted by one hook, same
single-config-per-message semantics as before. is_duplicate_message is the
exception: it's cheap and additive, so it's consulted across *every*
registered hook regardless of which one (if any) "owns" the mailbox, so two
CRM apps' dedup records both count.
"""

_incoming_mail_fetch_hooks = []


def register_incoming_mail_fetch_hook(
    get_config,
    get_allowed_senders,
    matches_filters,
    create_record,
    is_duplicate_message=None,
):
    """
    Register an incoming-mail fetch hook. Multiple apps may each call this.

    - get_config: callable(mail_config: HorillaMailConfiguration) -> config | None.
      Looks up the registering app's own per-mailbox configuration object.
      Returning None means "no special handling for this mailbox" from this
      hook - the fetch task still persists every message to the Inbox, just
      with no filtering/auto-create from this particular hook for that
      mailbox (another registered hook may still claim it).
    - get_allowed_senders: callable(config) -> list[str]. Lowercased sender
      emails to accept; an empty list means "accept all senders".
    - matches_filters: callable(config, subject, body) -> bool. Any other
      content-based filter (e.g. keyword matching) applied before persisting.
    - create_record: callable(config, incoming_mail) -> None. Called once a
      new IncomingMail row has been persisted; may create a Lead/Contact and
      should mark the row converted itself (see IncomingMail.mark_action_converted).
    - is_duplicate_message: optional callable(message_ids: list[str]) -> bool.
      Given one or more RFC822 Message-IDs (either a single already-fetched
      message's own id, or a reply's In-Reply-To/References ids), returns
      True if the registering app has already created a record from one of
      them. Lets a message be recognized as already-processed even if the
      IncomingMail row it originated from was since deleted (e.g. leads
      keeps Lead.message_id around for exactly this). When omitted, dedup
      relies solely on IncomingMail.message_id's own unique constraint plus
      matching in_reply_to/references against IncomingMail rows that still
      exist - a simpler behavior that only differs from the old behavior in
      the edge case of a deleted IncomingMail whose derived Lead still exists.
    """
    hook = {
        "get_config": get_config,
        "get_allowed_senders": get_allowed_senders,
        "matches_filters": matches_filters,
        "create_record": create_record,
        "is_duplicate_message": is_duplicate_message,
    }
    if hook not in _incoming_mail_fetch_hooks:
        _incoming_mail_fetch_hooks.append(hook)


def get_incoming_mail_fetch_hooks():
    """Return every registered fetch hook dict (empty list if none, e.g. CRM off)."""
    return list(_incoming_mail_fetch_hooks)


def resolve_fetch_hook_for_mailbox(mail_config):
    """
    Return the (hook, config) pair that "owns" this mailbox - the first
    registered hook whose get_config() returns a non-None config for it - or
    (None, None) if no registered hook claims this mailbox.
    """
    for hook in _incoming_mail_fetch_hooks:
        config = hook["get_config"](mail_config)
        if config is not None:
            return hook, config
    return None, None


def any_hook_reports_duplicate(message_ids):
    """
    True if ANY registered hook's is_duplicate_message says one of the given
    Message-IDs has already been converted - consulted across all hooks
    regardless of which one (if any) owns the mailbox, since this is cheap
    and additive (two CRM apps' dedup records should both count).
    """
    for hook in _incoming_mail_fetch_hooks:
        is_duplicate = hook.get("is_duplicate_message")
        if is_duplicate and is_duplicate(message_ids):
            return True
    return False
