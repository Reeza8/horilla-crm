"""
This module registers Floating, Settings, My Settings, and Main Section menus
for the Horilla CRM Accounts app
"""

# First party imports (Horilla)
from horilla.menu import (
    MAIN_CONTENT_HX_ATTRS,
    floating_menu,
    main_section_menu,
    sub_section_menu,
)
from horilla.urls import reverse_lazy
from horilla.utils.translation import gettext_lazy as _

# Local imports
from horilla_crm.accounts.models import Account


@floating_menu.register
class AccountFloating:
    """
    Configuration for the Account floating menu.

    Defines the title, URL, icon, HTMX behavior, and permissions
    for creating a new Account via the floating menu.
    """

    title = Account()._meta.verbose_name
    url = reverse_lazy("accounts:account_create_form_view")
    icon = "/assets/icons/account.svg"
    items = {
        "hx-target": "#modalBox",
        "hx-swap": "innerHTML",
        "onclick": "openModal()",
        "perm": ["accounts.add_account", "accounts.add_own_account"],
    }


@main_section_menu.register
class PeopleSection:
    """
    Registers the People section in the main sidebar.
    """

    section = "people"
    name = _("People")
    icon = "/assets/icons/customer.svg"
    position = 2


@sub_section_menu.register
class AccountsSubSection:
    """
    Registers the accounts menu to sub section in the main sidebar.
    """

    # Identity / placement
    section = "people"
    app_label = "accounts"
    position = 1

    # Display
    verbose_name = _("Accounts")
    icon = "/assets/icons/account.svg"

    # Behavior
    url = reverse_lazy("accounts:accounts_view")
    attrs = MAIN_CONTENT_HX_ATTRS

    # Access control
    perm = ["accounts.view_account", "accounts.view_own_account"]
