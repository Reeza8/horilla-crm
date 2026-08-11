"""
AppConfig for the duplicates app
"""

# First party imports (Horilla)
from horilla.apps import AppLauncher
from horilla.utils.translation import gettext_lazy as _


class DuplicatesConfig(AppLauncher):
    """App configuration class for duplicates."""

    default = True

    default_auto_field = "django.db.models.BigAutoField"
    name = "horilla.contrib.duplicates"
    label = "duplicates"
    verbose_name = _("Clone Management")

    url_prefix = "duplicates/"
    url_module = "horilla.contrib.duplicates.urls"

    auto_import_modules = ["menu", "registration", "inject"]

    demo_data = {
        "files": [
            (26, "load_data/duplicate_control.json"),
        ],
        "order": 7,
        "configurable": False,
    }
