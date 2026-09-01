"""
App configuration for the field requirements app.
"""

# First party imports (Horilla)
from horilla.apps import AppLauncher
from horilla.utils.translation import gettext_lazy as _


class FieldRequirementsConfig(AppLauncher):
    """App configuration class for field requirements."""

    default = True

    default_auto_field = "django.db.models.BigAutoField"
    name = "horilla.contrib.field_requirements"
    label = "field_requirements"
    verbose_name = _("Field Requirements")

    auto_import_modules = [
        "registration",
    ]
