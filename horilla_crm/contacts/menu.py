"""
This module registers Floating, Settings, My Settings, and Main Section menus
for the Horilla CRM Contacts app
"""

# First party imports (Horilla)
from horilla.menu import MAIN_CONTENT_HX_ATTRS, floating_menu, sub_section_menu
from horilla.urls import reverse_lazy
from horilla.utils.translation import gettext_lazy as _

# Local imports
from .models import Contact


@floating_menu.register
class ContactFloating:
    """Configuration for the Contact floating menu."""

    title = Contact()._meta.verbose_name
    url = reverse_lazy("contacts:contact_create_form")
    icon = "/assets/icons/contact.svg"
    items = {
        "hx-target": "#modalBox",
        "hx-swap": "innerHTML",
        "onclick": "openModal()",
        "perm": ["contacts.add_contact", "contacts.add_own_contact"],
    }


@sub_section_menu.register
class ContactsSubSection:
    """
    Registers the contacts menu to sub section in the main sidebar.
    """

    # Identity / placement
    section = "people"
    app_label = "contacts"
    position = 2

    # Display
    verbose_name = _("Contacts")
    icon = "/assets/icons/contact.svg"

    # Behavior
    url = reverse_lazy("contacts:contacts_view")
    attrs = MAIN_CONTENT_HX_ATTRS

    # Access control
    perm = ["contacts.view_contact", "contacts.view_own_contact"]
