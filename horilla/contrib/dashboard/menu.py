"""
This module registers Floating, Settings, My Settings, and Main Section menus
for the Horilla Dashboard app
"""

from horilla.menu import (
    MAIN_CONTENT_HX_ATTRS,
    MAIN_SECTION_HX_ATTRS,
    main_section_menu,
    sub_section_menu,
)

# First party imports (Horilla)
from horilla.urls import reverse_lazy
from horilla.utils.translation import gettext_lazy as _


@main_section_menu.register
class HomeSection:
    """
    Registers the Home section in the main sidebar.
    """

    section = "home"
    name = _("Home")
    icon = "/assets/icons/home.svg"
    position = 0
    url = reverse_lazy("dashboard:home_view")
    attrs = MAIN_SECTION_HX_ATTRS


@sub_section_menu.register
class DashboardSubSection:
    """
    Registers the dashboard to sub section in the main sidebar.
    """

    # Identity / placement
    section = "analytics"
    app_label = "dashboard"
    position = 2

    # Display
    verbose_name = _("Dashboards")
    icon = "/assets/icons/dashboards.svg"

    # Behavior
    url = reverse_lazy("dashboard:dashboard_list_view")
    attrs = MAIN_CONTENT_HX_ATTRS

    # Access control
    perm = ["dashboard.view_dashboard", "dashboard.view_own_dashboard"]
