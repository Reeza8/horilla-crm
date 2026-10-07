"""
AppLauncher for the automations app
"""

# First party imports (Horilla)
from horilla.apps import AppLauncher
from horilla.utils.translation import gettext_lazy as _


class AutomationsConfig(AppLauncher):
    """App configuration class for automations."""

    default = True

    default_auto_field = "django.db.models.BigAutoField"
    name = "horilla.contrib.automations"
    label = "automations"
    verbose_name = _("Automations")

    url_prefix = "automations/"
    url_module = "horilla.contrib.automations.urls"
    url_namespace = "automations"

    auto_import_modules = [
        "registration",
        "menu",
        "signals",
    ]

    celery_schedule_module = "celery_schedules"

    automation_files = ["load_automation/automation.json"]
