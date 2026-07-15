"""Lead Actions Views for Horilla CRM"""

# Third-party imports (Django)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.functional import cached_property

from horilla.contrib.generics.views import (
    HorillaMultiStepFormView,
    HorillaSingleDeleteView,
    HorillaSingleFormView,
)
from horilla.urls import reverse_lazy
from horilla.utils.decorators import (
    htmx_required,
    method_decorator,
    permission_required_or_denied,
)
from horilla.utils.translation import gettext_lazy as _

# First party imports (Horilla)
from horilla.web import HttpResponse, HxTriggerResponse

# Local imports
from horilla_crm.leads.forms import LeadFormClass, LeadSingleForm
from horilla_crm.leads.models import Lead, LeadStatus


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("leads.delete_lead", modal=True), name="dispatch"
)
class LeadDeleteView(LoginRequiredMixin, HorillaSingleDeleteView):
    """Lead Delete View"""

    model = Lead

    def get_post_delete_response(self):
        return HxTriggerResponse()


@method_decorator(htmx_required, name="dispatch")
class LeadFormView(LoginRequiredMixin, HorillaMultiStepFormView):
    """Lead Create/Update View"""

    form_class = LeadFormClass
    model = Lead
    fullwidth_fields = ["requirements"]
    dynamic_create_fields = ["lead_status"]
    detail_url_name = "leads:leads_detail"
    dynamic_create_field_mapping = {
        "lead_status": {
            "fields": ["name", "order", "color", "probability"],
            "initial": {
                "order": LeadStatus.get_next_order_for_company,
            },
        },
    }

    single_step_url_name = {
        "create": "leads:leads_create_single",
        "edit": "leads:leads_edit_single",
    }

    @cached_property
    def form_url(self):
        """Form URL for lead"""
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if pk:
            return reverse_lazy("leads:leads_edit", kwargs={"pk": pk})
        return reverse_lazy("leads:leads_create")

    step_titles = {
        "1": _("Basic Information"),
        "2": _("Company Details"),
        "3": _("Location"),
        "4": _("Requirements"),
    }

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs


@method_decorator(htmx_required, name="dispatch")
class LeadsSingleFormView(LoginRequiredMixin, HorillaSingleFormView):
    """Lead Create/Update Single Page View"""

    model = Lead
    form_class = LeadSingleForm
    full_width_fields = ["requirements"]
    dynamic_create_fields = ["lead_status"]
    dynamic_create_field_mapping = {
        "lead_status": {
            "fields": ["name", "order", "color", "probability", "is_final"],
            "initial": {
                "order": LeadStatus.get_next_order_for_company,
            },
        },
    }

    multi_step_url_name = {"create": "leads:leads_create", "edit": "leads:leads_edit"}
    detail_url_name = "leads:leads_detail"

    @cached_property
    def form_url(self):
        """Form URL for lead"""
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if pk:
            return reverse_lazy("leads:leads_edit_single", kwargs={"pk": pk})
        return reverse_lazy("leads:leads_create_single")


@method_decorator(htmx_required, name="dispatch")
class LeadChangeOwnerForm(LoginRequiredMixin, HorillaSingleFormView):
    """
    change owner form for lead
    """

    model = Lead
    fields = ["lead_owner"]
    full_width_fields = ["lead_owner"]
    modal_height = False
    form_title = _("Change Owner")

    @cached_property
    def form_url(self):
        """Form URL for lead change owner"""
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if pk:
            return reverse_lazy("leads:lead_change_owner", kwargs={"pk": pk})
        return None
