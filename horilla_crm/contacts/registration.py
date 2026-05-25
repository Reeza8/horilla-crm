"""
Feature registration for Contacts app.
"""

from calls.registration import register_callable_model
from horilla.contrib.cadences.registration import register_cadence_tab
from horilla.registry.feature import register_model_for_feature

register_model_for_feature(
    app_label="contacts",
    model_name="Contact",
    all=True,
    features=[
        "duplicate_models",
        "approval_models",
        "reviews_models",
        "scoring",
        "workflow_models",
    ],
)

register_cadence_tab(
    app_label="contacts",
    model_name="Contact",
    url_prefix="contact-cadences-tab/<int:pk>/",
    url_name="contact_cadences_tab",
)

register_callable_model("contacts", "Contact", "phone")
