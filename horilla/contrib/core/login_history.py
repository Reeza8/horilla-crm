"""Extend the third-party LoginHistory model with display helpers.

``login_history.LoginHistory`` ships from the ``login_history`` pip package
(not a Horilla model), so its display/formatting helpers are added through
``_inherit_model`` (see ``docs/horilla/extension/models/inherit.md``) instead
of assigning functions onto the class directly. This gives the same result
as editing the class body, but goes through the declared extension registry
(``horilla/extension/models/metaclass.py``) like every other model
extension in this codebase (e.g. ``calls/extensions.py``'s
``ActivityCallExtension``).
"""

# Third-party imports (Django)
from django.utils.timezone import localtime
from user_agents import parse

from horilla.contrib.core.models import HorillaCoreModel
from horilla.utils.html import format_html
from horilla.utils.translation import gettext_lazy as _


class LoginHistoryDisplayExtension(HorillaCoreModel):
    """Inject display/formatting helpers onto ``login_history.LoginHistory``."""

    _inherit_model = "login_history.LoginHistory"

    # The pip package doesn't set verbose_name on any of its fields, so
    # Django falls back to the raw field name ("user agent", "is login", …)
    # in exports/column labels; override them declaratively here instead
    # of reaching into LoginHistory._meta directly. ExtensionModelBase
    # applies this the same way it applies PROPERTY_LABELS below.
    _field_overrides = {
        "ip": {"verbose_name": _("IP")},
        "user": {"verbose_name": _("User")},
        "user_agent": {"verbose_name": _("User Agent")},
        "date_time": {"verbose_name": _("Date Time")},
        "is_login": {"verbose_name": _("Is Login")},
        "is_logged_in": {"verbose_name": _("Is Logged In")},
    }

    PROPERTY_LABELS = {
        "user_status": "Status",
        "short_user_agent": "Browser",
        "formatted_datetime": "Login Time",
        "is_login_icon": "Is Active",
    }

    def user_status(self):
        """Return 'Login' or 'Logout' based on is_logged_in status."""
        if self.is_logged_in is True:
            return "Login"
        return "Logout"

    def short_user_agent(self):
        """Return first UA part (Mozilla/5.0 ...) plus parsed browser/OS/device info."""
        if not self.user_agent:
            return self.user_agent

        ua = parse(self.user_agent)

        end = self.user_agent.find(")") + 1
        first_part = self.user_agent[:end] if end > 0 else ""

        major = ua.browser.version[0] if ua.browser.version else ""
        browser = f"{ua.browser.family} {major}".strip() if major else ua.browser.family

        device_parts = [
            p for p in [ua.device.brand, ua.device.model] if p and p != "Other"
        ]
        device = " ".join(dict.fromkeys(device_parts))

        if device:
            browser += f" [{device}]"

        return f"{browser} — {first_part}" if first_part else browser

    def formatted_datetime(self):
        """Return formatted local date-time string."""
        local_dt = localtime(self.date_time)
        return (
            local_dt.strftime("%d %b %Y, %I:%M %p")
            .lower()
            .replace("am", "a.m.")
            .replace("pm", "p.m.")
        )

    def is_login_icon(self):
        """Return HTML for login/logout icon based on is_logged_in status."""
        if self.is_logged_in:
            # Green check icon
            return format_html(
                '<span class="flex justify-center items-center inline-block text-green-600">'
                '<i class="{}"></i></span>',
                "fas fa-check-circle fa-lg",
            )
        # Red cross icon
        return format_html(
            '<span class=" flex justify-center items-center inline-block text-red-600">'
            '<i class="{}"></i></span>',
            "fas fa-times-circle fa-lg",
        )

    def get_is_login_icon_display(self):
        """Plain-text ``is_login_icon`` value for export (icon carries no text)."""
        return _("Active") if self.is_logged_in else _("Inactive")
