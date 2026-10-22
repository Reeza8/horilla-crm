"""
AppLauncher for the horilla.contrib.mobile app
"""

# First party imports (Horilla)
from horilla.apps import AppLauncher
from horilla.utils.translation import gettext_lazy as _


class MobileConfig(AppLauncher):
    """App configuration class for horilla.contrib.mobile."""

    default = True

    default_auto_field = "django.db.models.BigAutoField"
    name = "horilla.contrib.mobile"
    label = "mobile"
    verbose_name = _("Mobile")

    url_prefix = "m/"
    url_module = "horilla.contrib.mobile.urls"
    url_namespace = "mobile"

    auto_import_modules = [
        "registration",
    ]

    def ready(self):
        """Register URLs and modules, then load every app's ``mobile.py`` settings."""
        super().ready()
        # Outside AppLauncher's own error handling on purpose: a broken
        # ``mobile.py`` should stop startup, not hide a model on the phone.
        from .registry import discover_mobile_modules

        discover_mobile_modules()
