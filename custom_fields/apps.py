"""Django AppConfig for the Custom Fields settings app."""

from horilla.apps import AppLauncher
from horilla.utils.translation import gettext_lazy as _


class CustomFieldsConfig(AppLauncher):
    """App config for Custom Fields settings and extension auto-imports."""

    default = True
    default_auto_field = "django.db.models.BigAutoField"
    name = "custom_fields"
    verbose_name = _("Custom Fields")

    url_prefix = "custom-fields/"
    url_module = "custom_fields.urls"
    url_namespace = "custom_fields"
    auto_import_modules = [
        "menu",
        "registration",
        "extensions.view",
        "extensions.forms",
        "extensions.condition_field",
        "extensions.detail",
        "extensions.filter",
        "extensions.mixin",
        "extensions.list",
    ]
