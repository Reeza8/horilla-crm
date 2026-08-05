"""
Models for the keys app
"""

# Third-party imports (Django)
from django.conf import settings

from horilla.contrib.core.models import HorillaCoreModel
from horilla.contrib.utils.middlewares import _thread_local

# First party imports (Horilla)
from horilla.db import models
from horilla.menu.main_section_menu import get_main_section_menu
from horilla.menu.sub_section_menu import get_sub_section_menu
from horilla.urls import reverse_lazy
from horilla.utils.html import format_html
from horilla.utils.translation import gettext_lazy as _

from .utils import normalize_page_url, resolve_page_title


class ShortcutKey(HorillaCoreModel):
    """
    Model to store user-specific keyboard shortcut mappings.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shortcut_keys",
        verbose_name=_("User"),
    )
    page = models.CharField(max_length=100, verbose_name=_("Page"))
    key = models.CharField(max_length=1, verbose_name=_("Key"))
    command = models.CharField(
        max_length=20,
        verbose_name=_("Command Key"),
    )

    OWNER_FIELDS = ["user"]

    class Meta:
        """
        Meta options for the ShortcutKey model.
        """

        unique_together = ("user", "key", "command")
        verbose_name = _("Shortcut Key")
        verbose_name_plural = _("Shortcut Keys")

    def __str__(self):
        return str(self.page)

    def get_edit_url(self):
        """
        This method to get edit url
        """
        return reverse_lazy("keys:short_key_update", kwargs={"pk": self.pk})

    def custom_key_col(self):
        """Display formatted key combination based on OS."""
        request = getattr(_thread_local, "request", None)
        command_lower = self.command.lower()

        is_modifier = command_lower == "alt"

        if request and is_modifier:
            user_agent = request.META.get("HTTP_USER_AGENT", "").lower()
            is_mac = "mac" in user_agent or "darwin" in user_agent

            if is_mac:
                display_command = "OPTION (⌥)"
            else:
                display_command = "ALT"
        else:
            display_command = self.command.upper()

        return format_html(
            '<span style="color:red;">{}</span> + {}', display_command, self.key.upper()
        )

    def get_delete_url(self):
        """
        This method to get delete url
        """

        return reverse_lazy("keys:short_key_delete", kwargs={"pk": self.pk})

    def get_page_title(self):
        """
        Returns the human-readable title or label for this page.
        Uses full menu registry (ignores permissions) so admin-only pages
        still show friendly names for every user in the shortcut list.
        """
        return resolve_page_title(self.page)

    def page_display(self):
        """List column helper for the Page field."""
        return self.get_page_title()

    def get_section(self):
        """
        Returns the main or sub-section for this page.
        Only returns 'home' if the page is '/'.
        Otherwise, returns None if no section is found.
        """
        page = normalize_page_url(self.page)

        if page == "/":
            return "home"

        for item in get_main_section_menu(None):
            if normalize_page_url(item.get("url")) == page:
                return item.get("section")

        sub_sections = get_sub_section_menu(None)
        for section_name, items in sub_sections.items():
            for item in items:
                if normalize_page_url(item.get("url")) == page:
                    return section_name

        return None
