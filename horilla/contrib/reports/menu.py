"""
This module registers Floating, Settings, My Settings, and Main Section menus
for the Horilla Reports app
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
class AnalyticsSection:
    """
    Registers the Analytics section in the main sidebar.
    """

    section = "analytics"
    name = _("Analytics")
    icon = "/assets/icons/data-analytics.svg"
    position = 3
    attrs = MAIN_SECTION_HX_ATTRS


@sub_section_menu.register
class ReportsSubSection:
    """
    Registers the reports menu to sub section in the main sidebar.
    """

    # Identity / placement
    section = "analytics"
    app_label = "reports"
    position = 1

    # Display
    verbose_name = _("Reports")
    icon = "/assets/icons/reports.svg"

    # Behavior
    url = reverse_lazy("reports:reports_list_view")
    attrs = MAIN_CONTENT_HX_ATTRS

    # Access control
    perm = ["reports.view_report", "reports.view_own_report"]
