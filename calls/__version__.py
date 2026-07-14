"""Version and metadata for the calls app."""

from horilla.utils.translation import gettext_lazy as _

__version__ = "1.11.0"
__module_name__ = _("Calls Integration")
__release_date__ = ""
__description__ = _(
    "Telephony integration for click-to-call from CRM records, multi-provider "
    "support (Twilio, SignalWire(Beta), Telnyx(Beta), Sinch(Beta), Exotel(Beta), call logging, agent "
    "mapping, and company-level access control."
)
__icon__ = "assets/fontawesome/svgs/solid/phone.svg"

__1_11_0__ = _(
    "Initial release: multi-provider telephony (Twilio, SignalWire(Beta), Telnyx(Beta), Sinch(Beta), "
    "Exotel(Beta), Mock) with adapter factory; company enable/disable and role/user access "
    "control; Click-to-Call modal with HTMX live status, cancel, and recording toggles; "
    "CallLog history with Activity Timeline integration; agent mapping; secure "
    "credential storage; Settings → Integrations and My Settings UIs; REST API and "
    "webhook/WebSocket consumers."
)
