"""
App configuration for the field settings app.
"""

# First party imports (Horilla)
from horilla.apps import AppLauncher
from horilla.utils.translation import gettext_lazy as _


class FieldSettingsConfig(AppLauncher):
    """App configuration for Custom Fields, Field Requirements and Form Layouts."""

    default = True

    default_auto_field = "django.db.models.BigAutoField"
    name = "horilla.contrib.field_management"
    label = "field_management"
    verbose_name = _("Field Management")

    url_prefix = "field-management/"
    url_module = "horilla.contrib.field_management.urls"
    url_namespace = "field_management"

    auto_import_modules = [
        "menu",
        "registration",
        # Package whose __init__ imports every extension submodule.
        "extensions",
    ]
