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
    name = "horilla.contrib.field_settings"
    label = "field_settings"
    verbose_name = _("Field Settings")

    url_prefix = "field-settings/"
    url_module = "horilla.contrib.field_settings.urls"
    url_namespace = "field_settings"

    auto_import_modules = [
        "menu",
        "registration",
        # Package whose __init__ imports every extension submodule.
        "extensions",
    ]
