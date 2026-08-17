"""
AppLauncher for the horilla_jalali extension.

Install via local_settings.py (do not add this app to horilla/settings/base.py):

    INSTALLED_APPS += ["horilla_jalali"]
"""

from horilla.apps import AppLauncher
from horilla.utils.translation import gettext_lazy as _


class HorillaJalaliConfig(AppLauncher):
    """Jalali calendar extension — formatter, forms, views, and calendar assets."""

    default = True

    default_auto_field = "django.db.models.BigAutoField"
    name = "horilla_jalali"
    verbose_name = _("Jalali Calendar")

    auto_import_modules = [
        "models",
        "formatters",
        "forms",
        "details",
        "views",
        "registration",
    ]
