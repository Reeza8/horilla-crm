"""Processes module (approvals and review process), grouped like horilla.contrib."""

# First party imports (Horilla)
from horilla.menu import MAIN_SECTION_HX_ATTRS, main_section_menu, settings_menu
from horilla.utils.translation import gettext_lazy as _


@settings_menu.register
class ProcessSettings:
    """Settings menu entry for Review Processes."""

    title = _("Process Builder")
    icon = "/assets/icons/process-management.svg"
    order = 5
    items = []


@main_section_menu.register
class MyJobsSection:
    """Main sidebar section for user jobs."""

    section = "my_jobs"
    name = _("My Jobs")
    icon = "/assets/icons/jobs.svg"
    position = 5
    attrs = MAIN_SECTION_HX_ATTRS
