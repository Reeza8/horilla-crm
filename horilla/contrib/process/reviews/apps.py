"""App configuration for the `reviews` app."""

# First party imports (Horilla)
from horilla.apps import AppLauncher
from horilla.utils.translation import gettext_lazy as _


class ReviewProcessConfig(AppLauncher):
    """Review Process app configuration."""

    default = True
    default_auto_field = "django.db.models.BigAutoField"

    name = "horilla.contrib.process.reviews"
    label = "reviews"
    verbose_name = _("Review Process")

    # Mounted under this prefix by AppLauncher
    url_prefix = "review-process/"
    url_module = "horilla.contrib.process.reviews.urls"
    url_namespace = "reviews"

    auto_import_modules = ["registration", "signals", "menu"]

    demo_data = {
        "files": [
            (25, "load_data/review_process.json"),
        ],
        "order": 7,
        "configurable": False,
    }
