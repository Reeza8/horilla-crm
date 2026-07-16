"""Lead Conversion View for Horilla CRM"""

# Third-party imports (other)
from dateutil.relativedelta import relativedelta

# Third-party imports (Django)
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import FormView

# First party imports (Horilla)
from horilla.db import transaction
from horilla.shortcuts import get_object_or_404, render
from horilla.urls import reverse
from horilla.utils import timezone
from horilla.utils.decorators import htmx_required, method_decorator
from horilla.utils.translation import gettext_lazy as _
from horilla.web import Http404, ScriptResponse

# Local imports
from horilla_crm.accounts.models import Account
from horilla_crm.contacts.models import Contact, ContactAccountRelationship
from horilla_crm.leads.forms import LeadConversionForm
from horilla_crm.leads.models import Lead, LeadStatus
from horilla_crm.opportunities.models import (
    Opportunity,
    OpportunityContactRole,
    OpportunityStage,
)


@method_decorator(htmx_required, name="dispatch")
class LeadConversionView(LoginRequiredMixin, FormView):
    """View to handle lead conversion to account, contact, and opportunity."""

    template_name = "lead_convert.html"
    form_class = LeadConversionForm

    def dispatch(self, request, *args, **kwargs):
        """Load the lead and short-circuit with an HTMX error response if missing."""
        try:
            self.lead = Lead.objects.get(pk=self.kwargs["pk"])
        except Exception as e:
            messages.error(self.request, str(e))
            return ScriptResponse(reload=True, extra="closeContentModal();")

        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        """Return redirect target after successful conversion."""
        return reverse("leads:leads_detail", kwargs={"pk": self.lead.pk})

    def get_form_kwargs(self):
        """Inject lead and optional selected account into form kwargs."""
        kwargs = super().get_form_kwargs()
        kwargs["lead"] = self.lead

        # Get selected account for filtering opportunities
        selected_account_id = self.request.GET.get("existing_account")
        if selected_account_id:
            try:
                kwargs["selected_account"] = Account.objects.get(pk=selected_account_id)
            except Account.DoesNotExist:
                pass

        return kwargs

    def get_context_data(self, **kwargs):
        """Populate template context with lead and selected conversion actions."""
        context = super().get_context_data(**kwargs)
        context["lead"] = self.lead
        context["account_action"] = self.request.GET.get(
            "account_action", self.get_initial().get("account_action", "create_new")
        )
        context["contact_action"] = self.request.GET.get(
            "contact_action", self.get_initial().get("contact_action", "create_new")
        )
        context["opportunity_action"] = self.request.GET.get(
            "opportunity_action",
            self.get_initial().get("opportunity_action", "create_new"),
        )
        context["selected_account_id"] = self.request.GET.get("existing_account")
        return context

    def get(self, request, *args, **kwargs):
        """Handle permission checks and HTMX partial rendering for conversion form."""
        pk = self.kwargs.get("pk")
        if pk:
            try:
                lead = get_object_or_404(Lead, pk=pk)
            except Http404:
                messages.error(request, _("Lead not found or no longer exists."))
                return ScriptResponse(reload=True, close=True)

            if lead.lead_owner != request.user and not request.user.has_perm(
                "leads.change_lead"
            ):
                return render(request, "403.html")

        if "HTTP_HX_REQUEST" in request.META:
            hx_target = request.META.get("HTTP_HX_TARGET", "").replace("#", "")

            if "existing_account" in request.GET and hx_target == "opportunity-field":
                context = self.get_context_data()
                return render(request, "lead_convert_opportunity.html", context)

            if hx_target:
                action = request.GET.get(f"{hx_target}_action", "create_new")
                context = self.get_context_data()
                context[f"{hx_target}_action"] = action
                if hx_target == "account-field":
                    return render(request, "lead_convert_account.html", context)
                if hx_target == "contact-field":
                    return render(request, "lead_convert_contact.html", context)
                if hx_target == "opportunity-field":
                    return render(request, "lead_convert_opportunity.html", context)

        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        """Convert lead entities in a transaction and return success response."""
        with transaction.atomic():
            try:
                lead_status = LeadStatus.objects.filter(is_final=True).first()
                company = getattr(self.request, "active_company", None)
                account = self._process_account(form, company)
                contact = self._process_contact(form, account, company)
                opportunity = self._process_opportunity(form, account, contact, company)

                # Update only the Lead's conversion status. This view already
                # created the Account/Contact/Opportunity above, so tell the
                # is_convert signal (leads/signals.py handle_lead_conversion)
                # not to run the same conversion a second time.
                self.lead.is_convert = True
                self.lead.updated_at = timezone.now()
                self.lead.lead_status = lead_status
                self.lead._skip_conversion_signal = True
                self.lead.save()

                messages.success(
                    self.request,
                    f'Lead "{self.lead.title}" has been successfully converted!',
                )
                self.conversion_data = {
                    "account": account,
                    "contact": contact,
                    "opportunity": opportunity,
                    "lead": self.lead,
                }
            except Exception as e:
                messages.error(self.request, f"Error converting lead: {str(e)}")
                return self.form_invalid(form)

        response = super().form_valid(form)
        if "HTTP_HX_REQUEST" in self.request.META:
            return self._render_success_modal()
        return response

    def _render_success_modal(self):
        """Render the success modal with conversion data"""
        context = {
            "account": self.conversion_data["account"],
            "contact": self.conversion_data["contact"],
            "opportunity": self.conversion_data["opportunity"],
            "lead": self.conversion_data["lead"],
        }
        return render(self.request, "lead_convert_success_modal.html", context)

    def _process_account(self, form, company):
        if form.cleaned_data["account_action"] == "create_new":
            return Account.objects.create(
                name=form.cleaned_data["account_name"],
                account_owner=form.cleaned_data.get("owner"),
                phone=self.lead.contact_number,
                annual_revenue=self.lead.annual_revenue,
                industry=self.lead.industry,
                number_of_employees=self.lead.no_of_employees,
                fax=self.lead.fax,
                account_source=self.lead.lead_source,
                company=company,
            )
        return form.cleaned_data["existing_account"]

    def _process_contact(self, form, account, company):
        if form.cleaned_data["contact_action"] == "create_new":
            contact = Contact.objects.create(
                first_name=form.cleaned_data["first_name"],
                last_name=form.cleaned_data["last_name"],
                email=self.lead.email,
                phone=self.lead.contact_number,
                contact_owner=form.cleaned_data.get("owner"),
                company=company,
            )
            ContactAccountRelationship.objects.get_or_create(
                contact=contact, account=account, company=company
            )
            return contact
        contact = form.cleaned_data["existing_contact"]
        relationship, created = ContactAccountRelationship.objects.get_or_create(
            contact=contact, defaults={"account": account}, company=company
        )
        if not created and relationship.account != account:
            relationship.account = account
            relationship.save()
        return contact

    def _process_opportunity(self, form, account, contact, company):
        if form.cleaned_data["opportunity_action"] == "create_new":
            first_stage = OpportunityStage.objects.filter(order=1).first()
            campaign_member = self.lead.lead_campaign_members.first()
            closed_date = timezone.now().date() + relativedelta(months=1)
            opportunity = Opportunity.objects.create(
                name=form.cleaned_data["opportunity_name"],
                account=account,
                owner=self.lead.lead_owner,
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
            return opportunity
        opportunity = form.cleaned_data["existing_opportunity"]
        if opportunity.account != account:
            opportunity.account = account
        role, created = OpportunityContactRole.objects.get_or_create(
            opportunity=opportunity,
            contact=contact,
            defaults={"is_primary": True},
            company=company,
        )
        if not created and role.contact != contact:
            role.contact = contact
            role.save()
        opportunity.save()
        return opportunity

    def get_initial(self):
        """Provide default create-new options for conversion sections."""
        return {
            "account_action": "create_new",
            "contact_action": "create_new",
            "opportunity_action": "create_new",
        }

    def form_invalid(self, form):
        """Re-render form with validation errors, including HTMX responses."""
        if "HTTP_HX_REQUEST" in self.request.META:
            # Re-render the entire form with errors for HTMX requests
            context = self.get_context_data(form=form)
            return render(self.request, self.template_name, context)
        return super().form_invalid(form)
