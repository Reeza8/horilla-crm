"""
This module registers Floating, Settings, My Settings, and Main Section menus
for the Horilla Core app.
"""

from horilla.menu import settings_menu

# First party imports (Horilla)
from horilla.urls import reverse_lazy
from horilla.utils.translation import gettext_lazy as _


@settings_menu.register
class MailSettings:
    """Settings menu entries for the Mail module."""

    title = _("Mail")
    icon = "/assets/icons/email-orange.svg"
    order = 3
    items = [
        {
            "label": _("Outgoing Mail Server"),
            "url": reverse_lazy("mail:mail_server_view"),
            "hx-target": "#settings-content",
            "hx-push-url": "true",
            "hx-select": "#mail-server-view",
            "hx-select-oob": "#settings-sidebar",
            "perm": "mail.view_horillamailconfiguration",
        },
        {
            "label": _("Incoming Mail Server"),
            "url": reverse_lazy("mail:incoming_mail_server_view"),
            "hx-target": "#settings-content",
            "hx-push-url": "true",
            "hx-select": "#mail-server-view",
            "hx-select-oob": "#settings-sidebar",
            "perm": "mail.view_horillamailconfiguration",
        },
        {
            "label": _("Mail Template"),
            "url": reverse_lazy("mail:mail_template_view"),
            "hx-target": "#settings-content",
            "hx-push-url": "true",
            "hx-select": "#mail-template-view",
            "hx-select-oob": "#settings-sidebar",
            "perm": "mail.view_horillamailtemplate",
        },
        {
            "label": _("Mail History"),
            "url": reverse_lazy("mail:mail_history_view"),
            "hx-target": "#settings-content",
            "hx-push-url": "true",
            "hx-select": "#mail-history-view",
            "hx-select-oob": "#settings-sidebar",
            "perm": "mail.view_horillamail",
        },
    ]
