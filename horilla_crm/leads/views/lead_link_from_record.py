"""Connect converted leads to a Contact or an Opportunity, from that record's page."""

# Third-party imports (Django)
from django import forms
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q

# First party imports (Horilla)
from horilla.auth.mixins import LoginRequiredMixin
from horilla.contrib.generics.views.details import (
    check_record_access,
    check_record_change_access,
)
from horilla.shortcuts import get_object_or_404, render
from horilla.utils import timezone
from horilla.utils.decorators import htmx_required, method_decorator
from horilla.utils.translation import gettext_lazy as _
from horilla.views.generic import FormView, View
from horilla.web import JsonResponse, ScriptResponse

# Local imports
from horilla_crm.contacts.models import Contact
from horilla_crm.leads.models import Lead
from horilla_crm.opportunities.models import Opportunity


def _can_link_lead(user, lead):
    """The same users who may convert a lead may connect it to a record."""
    if not check_record_access(user, lead):
        return False
    return user.has_perm("leads.convert_lead") or (
        lead.lead_owner_id == user.pk and user.has_perm("leads.convert_own_lead")
    )


class ConvertedLeadSelect2View(LoginRequiredMixin, View):
    """Select2 source listing the converted leads the user may open."""

    per_page = 20

    def get(self, request, *args, **kwargs):
        """Return a JSON response with the converted leads matching the search term."""
        queryset = Lead.objects.filter(is_convert=True).order_by("-pk")
        term = request.GET.get("q", "").strip()
        if term:
            queryset = queryset.filter(
                Q(title__icontains=term)
                | Q(first_name__icontains=term)
                | Q(last_name__icontains=term)
                | Q(email__icontains=term)
                | Q(lead_company__icontains=term)
            )
        page = Paginator(queryset, self.per_page).get_page(request.GET.get("page", 1))
        results = [
            {"id": lead.pk, "text": str(lead)}
            for lead in page.object_list
            if check_record_access(request.user, lead)
        ]
        return JsonResponse(
            {"results": results, "pagination": {"more": page.has_next()}}
        )


class LinkLeadsForm(forms.Form):
    """The converted leads that belong to the record; clear one to unlink it."""

    leads = forms.ModelMultipleChoiceField(
        queryset=Lead.objects.filter(is_convert=True),
        required=False,
        label=_("Leads"),
    )


class _LinkLeadsToRecordView(LoginRequiredMixin, FormView):
    """Shared behaviour; subclasses set ``model`` and ``lead_field``."""

    template_name = "lead_link_to_record.html"
    form_class = LinkLeadsForm
    model = None
    lead_field = None
    url_name = None

    def dispatch(self, request, *args, **kwargs):
        """Check the user may change the record, and store it for later use."""
        self.record = get_object_or_404(self.model, pk=kwargs["pk"])
        if request.user.is_authenticated and not check_record_change_access(
            request.user, self.record
        ):
            return render(request, "403.html")
        return super().dispatch(request, *args, **kwargs)

    def _linked(self):
        """Return the leads currently linked to the record."""
        return Lead.objects.filter(**{self.lead_field: self.record})

    def get_initial(self):
        """Return the leads currently linked to the record, for the form's initial data."""
        return {"leads": self._linked()}

    def get_context_data(self, **kwargs):
        """Return the leads currently linked to the record, for the template context."""
        context = super().get_context_data(**kwargs)
        form = context["form"]
        if form.is_bound:
            selected = Lead.objects.filter(
                pk__in=[v for v in form.data.getlist("leads") if str(v).isdigit()]
            )
        else:
            selected = self._linked()
        context.update(selected_leads=selected, form_url=self.request.path)
        return context

    def form_valid(self, form):
        """Update the leads linked to the record, if the user may change them."""
        chosen = set(form.cleaned_data["leads"].values_list("pk", flat=True))
        current = set(self._linked().values_list("pk", flat=True))
        changed = Lead.objects.filter(pk__in=chosen ^ current)
        refused = [
            lead for lead in changed if not _can_link_lead(self.request.user, lead)
        ]
        if refused:
            form.add_error(
                "leads",
                _("You cannot change the link for: %(names)s")
                % {"names": ", ".join(str(lead) for lead in refused)},
            )
            return self.form_invalid(form)

        # update() touches only the link columns; the lead itself stays read-only.
        added = Lead.objects.filter(pk__in=chosen - current)
        added.update(**{self.lead_field: self.record})
        added.filter(converted_at__isnull=True).update(converted_at=timezone.now())
        Lead.objects.filter(pk__in=current - chosen).update(**{self.lead_field: None})
        messages.success(self.request, _("Leads linked."))
        return ScriptResponse(reload=True, msgs=True, close=True)


@method_decorator(htmx_required, name="dispatch")
class ContactLinkLeadsView(_LinkLeadsToRecordView):
    """Link converted leads to a Contact."""

    model = Contact
    lead_field = "converted_contact"


@method_decorator(htmx_required, name="dispatch")
class OpportunityLinkLeadsView(_LinkLeadsToRecordView):
    """Link converted leads to an Opportunity."""

    model = Opportunity
    lead_field = "converted_opportunity"
