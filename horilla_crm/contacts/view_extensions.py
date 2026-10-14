"""
Ask for the owner when an inbox email is added as a Contact, by extending the
mail app's InboxRunActionView, so the mail app needs no Contact code.
"""

from horilla.extension.view import ViewExtension

from .forms import InboxAddAsContactForm
from .utils import create_contact_from_email


class InboxAddAsContactExtension(ViewExtension):
    """Owner picker for the inbox "Add as Contact" action."""

    _inherit_view = "horilla.contrib.mail.views.inbox.InboxRunActionView"

    def get_action_form(self, action, incoming_mail, data=None):
        """Offer the owner form for the contact action only."""
        if action["key"] != "contact":
            return super().get_action_form(action, incoming_mail, data)
        return InboxAddAsContactForm(data, request=self.request)

    def run_action(self, action, incoming_mail, form=None):
        """Create (or reuse) the contact with the chosen owner."""
        if action["key"] != "contact" or form is None:
            return super().run_action(action, incoming_mail, form)
        return create_contact_from_email(
            incoming_mail, self.request, owner=form.cleaned_data["contact_owner"]
        )
