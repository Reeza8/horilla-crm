"""
Feature registration for the cadences app.
"""

# Standard library imports
import logging

from horilla.registry.feature import register_feature

# First party imports (Horilla)
from horilla.urls import path

logger = logging.getLogger(__name__)

# each app calls register_cadence_tab() from its own registration.py)
register_feature(
    "cadence",
    "cadence_models",
    auto_register_all=False,
)


_CADENCE_TAB_URLS = {}


def register_cadence_tab(app_label, model_name, url_prefix, url_name):
    """
    Register a cadence record tab for any model.

    Creates a CadenceRecordTabView subclass for the given model, adds its
    URL to the cadences urlpatterns, and records the URL name so the
    cadence tab can be added to that model's detail view automatically
    (see view_extensions.py's CadenceTabExtension). Call this from the
    model's own app registration.py — the cadences app stays free of any
    app-specific imports.
    """
    try:
        import horilla.contrib.cadences.urls as cadences_urls
        from horilla.contrib.cadences.views.record_tab import (
            CadenceRecordListView,
            CadenceRecordNavbar,
            CadenceRecordTabView,
        )
        from horilla.registry.feature import register_model_for_feature

        # Dynamically create the tab, navbar and list classes — no hardcoded model references
        record_attrs = {
            "record_app_label": app_label,
            "record_model_name": model_name,
            "record_url_name": url_name,
        }
        view_class = type(
            f"{model_name}CadenceTab", (CadenceRecordTabView,), record_attrs
        )
        nav_class = type(
            f"{model_name}CadenceNav", (CadenceRecordNavbar,), record_attrs
        )
        list_class = type(
            f"{model_name}CadenceList", (CadenceRecordListView,), record_attrs
        )
        record_path = f"{app_label.lower()}/{model_name.lower()}/<int:pk>/"

        # Register the model for the cadence feature so CadenceTabExtension can find it
        register_model_for_feature(
            app_label=app_label,
            model_name=model_name,
            features=["cadence"],
        )

        # Append the URL pattern to cadences urlpatterns at runtime
        # The tab URL is the HorillaView; it loads the navbar and list URLs below.
        cadences_urls.urlpatterns.append(
            path(url_prefix, view_class.as_view(), name=url_name)
        )
        cadences_urls.urlpatterns.append(
            path(
                f"cadence-record-nav/{record_path}",
                nav_class.as_view(),
                name=f"{url_name}_nav",
            )
        )
        cadences_urls.urlpatterns.append(
            path(
                f"cadence-record-list/{record_path}",
                list_class.as_view(),
                name=f"{url_name}_list",
            )
        )

        # Record the URL name so the detail-tab injection can build a link
        # for this model without the caller (or generics) referencing
        # "cadences:..." URLs directly.
        _CADENCE_TAB_URLS[(app_label.lower(), model_name.lower())] = (
            f"cadences:{url_name}"
        )

    except Exception as e:
        logger.warning(
            "register_cadence_tab failed for %s.%s: %s", app_label, model_name, e
        )


def get_cadence_tab_url_name(app_label, model_name):
    """Return the registered cadence tab URL name for a model, or ``None``."""
    return _CADENCE_TAB_URLS.get((app_label.lower(), model_name.lower()))
