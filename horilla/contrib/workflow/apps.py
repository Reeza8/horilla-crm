"""
App configuration for the workflow app.
"""

from horilla.apps import AppLauncher
from horilla.utils.translation import gettext_lazy as _


class WorkflowConfig(AppLauncher):
    """
    Configuration class for the workflow app in Horilla.
    """

    default = True

    default_auto_field = "django.db.models.BigAutoField"
    name = "horilla.contrib.workflow"
    label = "workflow"
    verbose_name = _("Workflow")

    url_prefix = "workflow/"
    url_module = "horilla.contrib.workflow.urls"
    url_namespace = "workflow"

    celery_schedule_module = "celery_schedules"

    auto_import_modules = [
        "registration",
        "signals",
        "menu",
    ]
