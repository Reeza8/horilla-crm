"""
App configuration for the scoring_rules app.
"""

from horilla.apps import AppLauncher
from horilla.utils.translation import gettext_lazy as _


class ScoringRulesConfig(AppLauncher):
    """
    Configuration class for the scoring_rules app in Horilla.
    """

    default = True

    default_auto_field = "django.db.models.BigAutoField"
    name = "horilla_crm.scoring_rules"
    verbose_name = _("Scoring Rules")

    url_prefix = "crm/scoring/"
    url_module = "horilla_crm.scoring_rules.urls"
    url_namespace = "scoring_rules"

    auto_import_modules = [
        "registration",
        "signals",
        "menu",
    ]

    demo_data = {
        "files": [
            (19, "load_data/scoring_rule.json"),
        ],
        "order": 7,
        "configurable": False,
    }

    def get_api_paths(self):
        """Return API path configurations for this app."""
        return [
            {
                "pattern": "crm/scoring/",
                "view_or_include": "horilla_crm.scoring_rules.api.urls",
                "name": "horilla_crm_scoring_rules_api",
                "namespace": "horilla_crm_scoring_rules",
            }
        ]
