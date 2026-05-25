"""
Registers Settings → Integrations and My Settings menu entries
for the Horilla Calls Integration app.
"""

# First party imports (Horilla)
from horilla.urls import reverse_lazy
from horilla.utils.translation import gettext_lazy as _
from horilla.menu import my_settings_menu
from horilla.contrib.core.menu import IntegrationsSettings

# Local imports
from .models import CallIntegrationSetting

# ── Admin: Settings → Integrations → Call Integration ────────────────────────
IntegrationsSettings.items.append(
    {
        "label": _("Call Integration"),
        "url": reverse_lazy("calls:integration_settings"),
        "hx-target": "#settings-content",
        "hx-push-url": "true",
        "hx-select": "#call-integration-settings-view",
        "hx-select-oob": "#settings-sidebar",
        "perm": "calls.change_callintegrationsetting",
    }
)


# ── Per-user: My Settings → Calls ────────────────────────────────────────────
@my_settings_menu.register
class CallsUserSettings:
    """
    Registers Calls in the My Settings sidebar.
    Only shown when the admin has enabled the call integration for this company
    and the current user has access.
    """

    title = _("Calls")
    url = reverse_lazy("calls:user_settings")
    active_urls = "calls:user_settings"
    order = 7
    attrs = {
        "hx-boost": "true",
        "hx-target": "#my-settings-content",
        "hx-push-url": "true",
        "hx-select": "#calls-user-settings-view",
        "hx-select-oob": "#my-settings-sidebar",
    }
    condition = staticmethod(CallIntegrationSetting.user_has_menu_access)
