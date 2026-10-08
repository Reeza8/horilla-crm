"""Utility functions for leads module."""

# Third-party imports (Django)
from django.utils.html import format_html

# First party imports (Horilla)
from horilla.utils.translation import gettext as _

# Local imports
from .models import Lead, LeadStatus


def lead_warning_for_mail(incoming_mail, request):
    """
    Inbox action warning: if this sender already has a Contact, say so (with
    a link) without blocking "Add as Lead" - mirrors how Salesforce/HubSpot/
    Zoho warn rather than block when creating a Lead for someone already a
    Contact, since a genuinely new inquiry from an existing customer is a
    normal, allowed case.
    """
    from horilla_crm.contacts.utils import find_duplicate_contact

    company = getattr(request, "active_company", None)
    contact = find_duplicate_contact(incoming_mail.sender_email, company)
    if not contact:
        return None
    # format_html escapes each interpolated value (sender email, contact
    # name/URL) individually, so a maliciously-named Contact can't inject
    # markup into this warning - only the literal template text is trusted.
    return format_html(
        '{} {} <a href="{}" class="underline" target="_blank">{}</a>.',
        incoming_mail.sender_email,
        _("already has a contact:"),
        contact.get_detail_url(),
        str(contact),
    )


def create_lead_from_email(incoming_mail, request, owner=None):
    """
    Create a Lead from a fetched IncomingMail row.

    Thin wrapper around the existing Lead.objects.create(...) shape used by
    the email-to-lead Celery task (leads/tasks.py), extracted here so both
    the automatic pipeline and the interactive "Add as Lead" inbox action
    share the same creation logic.
    """
    owner = owner or request.user
    company = getattr(request, "active_company", None)

    lead = Lead.objects.create(
        title=incoming_mail.subject,
        email=incoming_mail.sender_email,
        requirements=incoming_mail.body,
        lead_owner=owner,
        lead_status=LeadStatus.objects.first(),
        company=company,
        lead_source="email",
        message_id=incoming_mail.message_id,
    )
    return lead
