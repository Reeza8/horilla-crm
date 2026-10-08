"""
Pluggable "incoming mail" actions.

Other apps (e.g. leads, contacts) register their own "convert this email into
a record" actions here so this app never has to import them. See
horilla/contrib/process/integration.py for the same pattern used elsewhere.
"""

_incoming_mail_actions = []


def register_incoming_mail_action(
    key,
    label,
    handler,
    icon=None,
    permission=None,
    already_exists_check=None,
    warning_check=None,
):
    """
    Register an action that can be run against an IncomingMail row.

    - key: short unique string identifying this action (e.g. "contact", "lead").
      Stored into IncomingMail.additional_info["converted_actions"] once the
      handler succeeds.
    - label: human-readable button label.
    - handler: callable(incoming_mail, request) that performs the create/dedup
      work and returns a result for the view to render.
    - icon: optional icon path for the action button.
    - permission: optional Django permission string required to run this action.
    - already_exists_check: optional callable(incoming_mail, request) -> bool.
      Lets the registering app report "this sender already has a record" even
      on a message that itself was never converted (e.g. a second email from
      a sender already added as a Contact) - mail has no notion of what a
      Contact/Lead is, so it only ever calls this predicate, never inspects
      the result.
    - warning_check: optional callable(incoming_mail, request) -> str | None.
      Lets the registering app surface a non-blocking warning in the confirm
      step (e.g. "this sender already has a Contact, create a Lead anyway?")
      without preventing the action - mirrors how Salesforce/HubSpot/Zoho
      warn rather than block when creating a Lead for someone already a
      Contact. mail only ever renders the returned string, it never inspects
      what the warning is about.
    """
    if any(action["key"] == key for action in _incoming_mail_actions):
        return
    _incoming_mail_actions.append(
        {
            "key": key,
            "label": label,
            "handler": handler,
            "icon": icon,
            "permission": permission,
            "already_exists_check": already_exists_check,
            "warning_check": warning_check,
        }
    )


def get_incoming_mail_actions():
    """Return all registered incoming-mail actions."""
    return list(_incoming_mail_actions)


def get_incoming_mail_action(key):
    """Return the registered action dict for a given key, or None."""
    for action in _incoming_mail_actions:
        if action["key"] == key:
            return action
    return None
