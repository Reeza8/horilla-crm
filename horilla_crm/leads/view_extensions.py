"""
Ask for the owner (and whether to use the assignment rules) when an inbox
email is added as a Lead, by extending the mail app's InboxRunActionView, so
the mail app needs no Lead code.
"""

from horilla.extension.view import ViewExtension

from .forms import InboxAddAsLeadForm
from .utils import create_lead_from_email


class InboxAddAsLeadExtension(ViewExtension):
    """Owner picker and "Assign using rules" for the inbox "Add as Lead" action."""

    _inherit_view = "horilla.contrib.mail.views.inbox.InboxRunActionView"

    def get_action_form(self, action, incoming_mail, data=None):
        """Offer the owner form for the lead action only."""
        if action["key"] != "lead":
            return super().get_action_form(action, incoming_mail, data)
        return InboxAddAsLeadForm(
            data, request=self.request, incoming_mail=incoming_mail
        )

    def run_action(self, action, incoming_mail, form=None):
        """Create the lead with the chosen owner and rule option."""
        if action["key"] != "lead" or form is None:
            return super().run_action(action, incoming_mail, form)
        return create_lead_from_email(
            incoming_mail,
            self.request,
            owner=form.cleaned_data["lead_owner"],
            apply_assignment_rule=form.cleaned_data.get("apply_assignment_rule", False),
            assignment_decision=form._assignment_decision,
        )
