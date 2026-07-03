"""
This module contains the views for creating, updating, and deleting campaigns and campaign members.
"""

# Standard library imports
import logging
from functools import cached_property

# Third-party imports (Django)
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.views.generic import FormView, View

# First party imports (Horilla)
from horilla.apps import apps
from horilla.contrib.generics.views import (
    HorillaSingleDeleteView,
    HorillaSingleFormView,
)
from horilla.contrib.generics.views.details import (
    check_record_access,
    check_record_change_access,
    check_record_delete_access,
)
from horilla.contrib.generics.views.multi_form import HorillaMultiStepFormView
from horilla.shortcuts import get_object_or_404, render
from horilla.urls import reverse_lazy
from horilla.utils import timezone
from horilla.utils.decorators import (
    htmx_required,
    method_decorator,
    permission_required_or_denied,
)
from horilla.utils.translation import gettext_lazy as _
from horilla.web import HttpResponse

# Local imports
from horilla_crm.campaigns.forms import (
    CampaignFormClass,
    CampaignMemberForm,
    CampaignSingleForm,
    ChildCampaignForm,
)
from horilla_crm.campaigns.models import Campaign, CampaignMember

logger = logging.getLogger(__name__)


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("campaigns.delete_campaign", modal=True),
    name="dispatch",
)
class CampaignDeleteView(LoginRequiredMixin, HorillaSingleDeleteView):
    """
    Campaign delete view
    """

    model = Campaign

    def get_post_delete_response(self):
        return HttpResponse("<script>htmx.trigger('#reloadButton','click');</script>")


@method_decorator(htmx_required, name="dispatch")
class CampaignFormView(LoginRequiredMixin, HorillaMultiStepFormView):
    """
    form view for campaign
    """

    form_class = CampaignFormClass
    model = Campaign
    fullwidth_fields = ["number_sent", "description"]
    total_steps = 3
    detail_url_name = "campaigns:campaign_detail_view"
    step_titles = {
        "1": _("Campaign Information"),
        "2": _("Financial Information"),
        "3": _("Additional Information"),
    }

    single_step_url_name = {
        "create": "campaigns:campaign_single_create",
        "edit": "campaigns:campaign_single_edit",
    }

    @cached_property
    def form_url(self):
        """
        Return the URL for the form submission
        """
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if pk:
            return reverse_lazy("campaigns:campaign_edit", kwargs={"pk": pk})
        return reverse_lazy("campaigns:campaign_create")


@method_decorator(htmx_required, name="dispatch")
class CampaignSingleFormView(LoginRequiredMixin, HorillaSingleFormView):
    """campaign Create/Update Single Page View"""

    model = Campaign
    form_class = CampaignSingleForm
    full_width_fields = ["description"]
    detail_url_name = "campaigns:campaign_detail_view"
    multi_step_url_name = {
        "create": "campaigns:campaign_create",
        "edit": "campaigns:campaign_edit",
    }

    @cached_property
    def form_url(self):
        """Form URL for lead"""
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if pk:
            return reverse_lazy("campaigns:campaign_single_edit", kwargs={"pk": pk})
        return reverse_lazy("campaigns:campaign_single_create")


@method_decorator(htmx_required, name="dispatch")
class CampaignChangeOwnerForm(LoginRequiredMixin, HorillaSingleFormView):
    """
    Change owner form
    """

    model = Campaign
    fields = ["campaign_owner"]
    full_width_fields = ["campaign_owner"]
    modal_height = False
    form_title = _("Change Owner")

    @cached_property
    def form_url(self):
        """
        Return the URL for the form submission
        """
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if pk:
            return reverse_lazy("campaigns:campaign_change_owner", kwargs={"pk": pk})
        return None


@method_decorator(htmx_required, name="dispatch")
class AddChildCampaignFormView(LoginRequiredMixin, FormView):
    """
    Form view to select an existing campaign and assign it as a child campaign.
    """

    template_name = "single_form_view.html"
    header = True
    form_class = ChildCampaignForm

    def get(self, request, *args, **kwargs):
        """Authorize child-campaign form access and render the form."""

        campaign_id = request.GET.get("id")
        if request.user.has_perm("campaigns.change_campaign") or request.user.has_perm(
            "campaigns.create_campaign"
        ):
            return super().get(request, *args, **kwargs)

        if campaign_id:
            campaign = get_object_or_404(Campaign, pk=campaign_id)
            if campaign.campaign_owner == request.user:
                return super().get(request, *args, **kwargs)

        return render(request, "403.html")

    def get_form_kwargs(self):
        """
        Pass the request to the form for queryset filtering and validation.
        """
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_initial(self):
        """
        Prepopulate the form with initial data if needed.
        """
        initial = super().get_initial()
        parent_id = self.request.GET.get("id")

        if parent_id:
            try:
                parent_campaign = Campaign.objects.get(pk=parent_id)
                initial["parent_campaign"] = parent_campaign
            except Exception as e:
                logger.error(e)  # Debug

        return initial

    def get_context_data(self, **kwargs):
        """
        Add context data for the template.
        """
        context = super().get_context_data(**kwargs)
        context["form_title"] = _("Add Child Campaign")
        context["full_width_fields"] = ["campaign"]  # Make sure campaign is full width
        context["form_url"] = self.get_form_url()

        form_url = self.get_form_url()

        context["hx_attrs"] = {
            "hx-post": str(form_url),
            "hx-target": "#modalBox",
            "hx-swap": "innerHTML",
        }
        context["modal_height"] = False
        context["view_id"] = "add-child-campaign-form-view"
        context["condition_fields"] = []
        context["header"] = self.header
        context["field_permissions"] = {}
        return context

    def form_valid(self, form):
        """
        Update the selected campaign's parent_campaign field and return HTMX response.
        """
        if not self.request.user.is_authenticated:
            messages.error(
                self.request, _("You must be logged in to perform this action.")
            )
            return self.form_invalid(form)

        selected_campaign = form.cleaned_data["campaign"]
        parent_campaign = form.cleaned_data[
            "parent_campaign"
        ]  # Get from form data instead of GET

        if not parent_campaign:
            form.add_error(None, _("No parent campaign specified in the request."))
            return self.form_invalid(form)

        try:
            if selected_campaign.id == parent_campaign.id:
                form.add_error("campaign", _("A campaign cannot be its own parent."))
                return self.form_invalid(form)

            if selected_campaign.parent_campaign:
                form.add_error(
                    "campaign", _("This campaign already has a parent campaign.")
                )
                return self.form_invalid(form)

            # Update the selected campaign
            selected_campaign.parent_campaign = parent_campaign
            selected_campaign.updated_at = timezone.now()
            selected_campaign.updated_by = self.request.user
            selected_campaign.save()

            messages.success(self.request, _("Child campaign assigned successfully."))

        except ValidationError as e:
            msg = (
                next(iter(e.message_dict.values()))[0]
                if hasattr(e, "message_dict")
                else e.message
            )
            form.add_error("campaign", msg)
            return self.form_invalid(form)
        except ValueError:
            form.add_error(None, _("Invalid parent campaign ID format."))
            return self.form_invalid(form)

        return HttpResponse(
            "<script>htmx.trigger('#tab-child_campaigns-btn', 'click');closeModal();</script>"
        )

    def get_form_url(self):
        """
        Get the form URL for submission.
        """
        return reverse_lazy("campaigns:create_child_campaign")


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("campaigns.delete_campaign"), name="dispatch"
)
class ChildCampaignDeleteView(LoginRequiredMixin, View):
    """
    View to remove parent-child relationship from a campaign.
    """

    def delete(self, request, pk, *args, **kwargs):
        """
        Handle DELETE request to remove parent campaign relationship.
        """

        child_campaign = get_object_or_404(Campaign, pk=pk)

        has_permission = (
            request.user.has_perm("campaigns.change_campaign")
            or child_campaign.campaign_owner == request.user
            or (
                child_campaign.parent_campaign
                and child_campaign.parent_campaign.campaign_owner == request.user
            )
        )

        if not has_permission:
            messages.error(
                request, _("You don't have permission to perform this action.")
            )
            return HttpResponse(
                "<script>htmx.trigger('#tab-child_campaigns-btn', 'click');</script>",
                status=403,
            )

        parent_campaign = child_campaign.parent_campaign

        if not parent_campaign:
            messages.warning(
                request, _("This campaign doesn't have a parent campaign.")
            )
            return HttpResponse(
                "<script>htmx.trigger('#tab-child_campaigns-btn', 'click');</script>"
            )

        try:
            child_campaign.parent_campaign = None
            child_campaign.updated_at = timezone.now()
            child_campaign.updated_by = request.user
            child_campaign.save()

            messages.success(
                request,
                _(
                    f"Successfully removed {child_campaign.campaign_name} from {parent_campaign.campaign_name}'s child campaigns."
                ),
            )

            return HttpResponse(
                "<script>htmx.trigger('#tab-child_campaigns-btn', 'click');</script>"
            )

        except Exception as e:
            print(f"Error removing child campaign: {e}")
            messages.error(
                request, _("An error occurred while removing the child campaign.")
            )
            return HttpResponse(
                "<script>htmx.trigger('#tab-child_campaigns-btn', 'click');</script>",
            )


@method_decorator(htmx_required, name="dispatch")
class AddToCampaignFormview(LoginRequiredMixin, HorillaSingleFormView):
    """
    Add lead to campaign form view
    """

    model = CampaignMember
    fields = ["lead", "campaign", "member_status"]
    full_width_fields = ["campaign", "member_status"]
    modal_height = False
    form_title = _("Add to Campaign")
    hidden_fields = ["lead"]
    save_and_new = False

    def _get_lead(self):
        pk = self.kwargs.get("pk")
        lead_id = self.request.GET.get("id")
        if pk:
            campaign_member = get_object_or_404(CampaignMember, pk=pk)
            return campaign_member.lead
        elif lead_id:
            Lead = apps.get_model("leads", "Lead")
            return get_object_or_404(Lead, pk=lead_id)
        return None

    def has_permission(self):
        user = self.request.user
        if user.is_superuser:
            return True
        lead = self._get_lead()
        if lead:
            return check_record_change_access(user, lead)
        return False

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if "campaign" in form.fields:
            form.fields["campaign"].queryset = Campaign.objects.all()
            form._unrestricted_fields = getattr(form, "_unrestricted_fields", set()) | {
                "campaign"
            }
        return form

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        super().form_valid(form)
        return HttpResponse(
            "<script>htmx.trigger('#tab-campaigns-btn', 'click');closeModal();</script>"
        )

    def get_initial(self):
        """Prefill lead field from query params for create mode."""
        initial = super().get_initial()
        lead_id = self.request.GET.get("id")
        if lead_id:
            initial["lead"] = lead_id
        return initial

    @cached_property
    def form_url(self):
        """
        Return the form URL for submission.
        """
        if self.kwargs.get("pk"):
            return reverse_lazy(
                "campaigns:edit_campaign_member", kwargs={"pk": self.kwargs.get("pk")}
            )
        return reverse_lazy("campaigns:add_to_campaign")


@method_decorator(htmx_required, name="dispatch")
class AddCampaignMemberFormview(LoginRequiredMixin, HorillaSingleFormView):
    """
    Form view to craete and edit campaign member
    """

    model = CampaignMember
    form_class = CampaignMemberForm
    modal_height = False
    form_title = _("Add Campaign Members")
    full_width_fields = ["member_status", "member_type", "lead", "contact"]
    save_and_new = False

    def has_permission(self):
        user = self.request.user
        if user.is_superuser:
            return True
        campaign_id = (
            self.request.GET.get("id")
            or self.request.GET.get("campaign")
            or self.request.POST.get("campaign")
        )
        if campaign_id:
            try:
                from horilla_crm.campaigns.models import Campaign

                campaign = Campaign.objects.get(pk=campaign_id)
                return check_record_change_access(user, campaign)
            except Exception:
                pass
        return False

    def get_initial(self):
        """Initialize campaign member form fields from request parameters."""
        initial = super().get_initial()
        campaign_id = (
            self.request.GET.get("id")
            if self.request.GET.get("id")
            else self.request.GET.get("campaign")
        )
        member_type = self.request.GET.get("member_type") or "lead"
        initial["member_type"] = member_type
        if campaign_id:
            initial["campaign"] = campaign_id
        return initial

    def form_valid(self, form):
        super().form_valid(form)
        return HttpResponse(
            "<script>htmx.trigger('#tab-members-btn', 'click');closeModal();</script>"
        )

    @cached_property
    def form_url(self):
        """
        Return the form URL for submission.
        """
        if self.kwargs.get("pk"):
            return reverse_lazy(
                "campaigns:edit_added_campaign_members",
                kwargs={"pk": self.kwargs.get("pk")},
            )
        return reverse_lazy("campaigns:add_campaign_members")


@method_decorator(htmx_required, name="dispatch")
class CampaignMemberDeleteView(LoginRequiredMixin, HorillaSingleDeleteView):
    """
    Campaign member delete view
    """

    model = CampaignMember

    def dispatch(self, request, *args, **kwargs):
        member = get_object_or_404(CampaignMember, pk=self.kwargs.get("pk"))
        parent = member.campaign
        if not check_record_delete_access(request.user, parent):
            return render(request, "403.html", {"modal": True})
        return super().dispatch(request, *args, **kwargs)

    def get_post_delete_response(self):
        return HttpResponse(
            "<script>htmx.trigger('#tab-members-btn','click');$('#reloadButton').click();</script>"
        )


@method_decorator(htmx_required, name="dispatch")
class AddContactToCampaignFormView(LoginRequiredMixin, HorillaSingleFormView):
    """
    Form iew for adding contacts into campaigns
    """

    model = CampaignMember
    fields = ["contact", "campaign", "member_status"]
    full_width_fields = ["campaign", "member_status"]
    modal_height = False
    form_title = _("Add to Campaign")
    hidden_fields = ["contact"]
    save_and_new = False

    def _get_contact(self):
        pk = self.kwargs.get("pk")
        contact_id = self.request.GET.get("id")
        if pk:
            member = get_object_or_404(CampaignMember, pk=pk)
            return member.contact
        if contact_id:
            from horilla_crm.contacts.models import Contact

            return get_object_or_404(Contact, pk=contact_id)
        return None

    def has_permission(self):
        user = self.request.user
        if user.is_superuser:
            return True
        contact = self._get_contact()
        if contact:
            return check_record_change_access(user, contact)
        return False

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if "campaign" in form.fields:
            form.fields["campaign"].queryset = Campaign.objects.all()
            form._unrestricted_fields = getattr(form, "_unrestricted_fields", set()) | {
                "campaign"
            }
        return form

    def form_valid(self, form):
        form.instance.member_type = "contact"
        super().form_valid(form)
        return HttpResponse(
            "<script>htmx.trigger('#tab-campaigns-btn', 'click');closeModal();</script>"
        )

    def get_initial(self):
        """Prefill contact field from query params for create mode."""
        initial = super().get_initial()
        contact_id = self.request.GET.get("id")
        if contact_id:
            initial["contact"] = contact_id
        return initial

    @cached_property
    def form_url(self):
        """
        Return the form URL for submission.
        """
        if self.kwargs.get("pk"):
            return reverse_lazy(
                "campaigns:edit_contact_to_campaign",
                kwargs={"pk": self.kwargs.get("pk")},
            )
        return reverse_lazy("campaigns:add_contact_to_campaign")


@method_decorator(htmx_required, name="dispatch")
class CampaignContactMemberDeleteView(LoginRequiredMixin, HorillaSingleDeleteView):
    """
    Campaign contact member delete view
    """

    model = CampaignMember

    def dispatch(self, request, *args, **kwargs):
        member = get_object_or_404(CampaignMember, pk=self.kwargs.get("pk"))
        parent = member.contact
        if not check_record_delete_access(request.user, parent):
            return render(request, "403.html", {"modal": True})
        return super().dispatch(request, *args, **kwargs)

    def get_post_delete_response(self):
        return HttpResponse(
            "<script>htmx.trigger('#tab-campaigns-btn','click');</script>"
        )
