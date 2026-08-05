"""Helper functions for LoginHistory model display and formatting.

This module provides utility functions that are attached to the LoginHistory model
to enhance its display capabilities. These functions handle:
- User status display (Login/Logout)
- User agent string truncation
- Date-time formatting
- Login/logout icon rendering
"""

# Third-party imports (Django)
from django.utils.timezone import localtime
from login_history.models import LoginHistory
from user_agents import parse

from horilla.utils.html import format_html


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

    device_parts = [p for p in [ua.device.brand, ua.device.model] if p and p != "Other"]
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


LoginHistory.user_status = user_status
LoginHistory.short_user_agent = short_user_agent
LoginHistory.formatted_datetime = formatted_datetime
LoginHistory.is_login_icon = is_login_icon
LoginHistory.PROPERTY_LABELS = {
    "user_status": "Status",
    "short_user_agent": "Browser",
    "formatted_datetime": "Login Time",
    "is_login_icon": "Is Active",
}
