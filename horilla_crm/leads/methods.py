# Define your leads helper methods here

# Third-party imports (other)
from dateutil.relativedelta import relativedelta

# First party imports (Horilla)
from horilla.core.exceptions import ValidationError
from horilla.db import transaction
from horilla.utils import timezone

# Local imports
from horilla_crm.accounts.models import Account
from horilla_crm.contacts.models import Contact, ContactAccountRelationship
from horilla_crm.opportunities.models import (
    Opportunity,
    OpportunityContactRole,
    OpportunityStage,
)


def convert_lead(
    lead,
    company,
    account_name=None,
    first_name=None,
    last_name=None,
    opportunity_name=None,
):
    """
    Convert a Lead into an Account, a Contact, and an Opportunity, linked via
    ContactAccountRelationship and OpportunityContactRole - the same "create
    new" path LeadConversionView.form_valid() runs for the manual Convert
    button, extracted here so other callers (e.g. the WhatsApp bot's
    is_convert signal) can reuse it instead of duplicating the logic.

    Always creates new Account/Contact/Opportunity records (the "select
    existing" paths are form-driven UI choices with no equivalent input in a
    non-form caller). Any name argument left blank falls back to a value
    derived from the lead itself. Runs atomically so a failure partway
    through (e.g. no OpportunityStage configured) doesn't leave an orphaned
    Account/Contact behind.

    Returns (account, contact, opportunity).
    """
    account_name = (
        account_name
        or lead.lead_company
        or f"{lead.first_name} {lead.last_name}".strip()
    )
    first_name = first_name or lead.first_name
    last_name = last_name or lead.last_name
    opportunity_name = opportunity_name or f"{account_name} Opportunity"

    first_stage = (
        OpportunityStage.objects.filter(company=company).order_by("order").first()
    )
    if not first_stage:
        raise ValidationError(
            "Cannot convert lead: no Opportunity Stage is configured for this company."
        )

    with transaction.atomic():
        account = Account.objects.create(
            name=account_name,
            phone=lead.contact_number,
            annual_revenue=lead.annual_revenue,
            industry=lead.industry,
            number_of_employees=lead.no_of_employees,
            fax=lead.fax,
            account_source=lead.lead_source,
            company=company,
        )

        contact = Contact.objects.create(
            first_name=first_name,
            last_name=last_name,
            email=lead.email,
            phone=lead.contact_number,
            contact_owner=lead.lead_owner,
            company=company,
        )
        ContactAccountRelationship.objects.get_or_create(
            contact=contact, account=account, company=company
        )

        campaign_member = lead.lead_campaign_members.first()
        closed_date = timezone.now().date() + relativedelta(months=1)
        opportunity = Opportunity.objects.create(
            name=opportunity_name,
            account=account,
            owner=lead.lead_owner,
            stage=first_stage,
            primary_campaign_source=(
                campaign_member.campaign if campaign_member else None
            ),
            close_date=closed_date,
            company=company,
        )
        OpportunityContactRole.objects.get_or_create(
            opportunity=opportunity,
            contact=contact,
            defaults={"is_primary": True},
            company=company,
        )

    return account, contact, opportunity


# Define your leads helper methods here
