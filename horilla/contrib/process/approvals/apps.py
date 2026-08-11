"""
App configuration for the approvals app.
"""

# First party imports (Horilla)
from horilla.apps import AppLauncher
from horilla.utils.translation import gettext_lazy as _


class ApprovalsConfig(AppLauncher):
    """
    Configuration class for the approvals app in Horilla.
    """

    default = True

    default_auto_field = "django.db.models.BigAutoField"
    name = "horilla.contrib.process.approvals"
    label = "approvals"
    verbose_name = _("Approvals")

    url_prefix = "approvals/"
    url_module = "horilla.contrib.process.approvals.urls"
    url_namespace = "approvals"

    auto_import_modules = [
        "registration",
        "signals",
        "menu",
    ]

    demo_data = {
        "files": [
            (24, "load_data/approval_rule.json"),
        ],
        "order": 7,
        "configurable": False,
    }
