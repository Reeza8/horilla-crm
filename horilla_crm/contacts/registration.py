"""
Feature registration for Contacts app.
"""

from calls.registration import register_callable_model
from horilla.contrib.cadences.registration import register_cadence_tab
from horilla.contrib.mail.actions import register_incoming_mail_action

# First party imports (Horilla)
from horilla.registry.feature import register_model_for_feature
from horilla.utils.translation import gettext_lazy as _

# Local imports
from .utils import contact_already_exists_for_mail, create_contact_from_email

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

register_callable_model("contacts", "Contact", "contact_number")


def _add_as_contact(incoming_mail, request):
    """Inbox action handler: create (or reuse) a Contact from an incoming email."""
    contact, _created = create_contact_from_email(incoming_mail, request)
    return contact


register_incoming_mail_action(
    key="contact",
    label=_("Add as Contact"),
    handler=_add_as_contact,
    icon="assets/icons/add_as_contact.svg",
    permission="contacts.add_contact",
    already_exists_check=contact_already_exists_for_mail,
)
