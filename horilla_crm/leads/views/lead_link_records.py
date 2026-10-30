"""Link a converted lead to the Contact and Opportunity it relates to."""

# Third-party imports (Django)
from django import forms
from django.contrib import messages

# First party imports (Horilla)
from horilla.auth.mixins import LoginRequiredMixin
from horilla.contrib.generics.views.details import check_record_access
from horilla.shortcuts import get_object_or_404, render
from horilla.utils import timezone
from horilla.utils.decorators import htmx_required, method_decorator
from horilla.utils.translation import gettext_lazy as _
from horilla.views.generic import FormView
from horilla.web import ScriptResponse

# Local imports
from horilla_crm.contacts.models import Contact
from horilla_crm.leads.models import Lead
from horilla_crm.opportunities.models import Opportunity

_SELECT_ATTRS = {"class": "select2-pagination w-full text-sm"}


class LeadLinkRecordsForm(forms.Form):
    """Pick the Contact and Opportunity a converted lead belongs to; each is optional."""

    contact = forms.ModelChoiceField(
        queryset=Contact.objects.all(),
        required=False,
        label=_("Contact"),
        widget=forms.Select(attrs=_SELECT_ATTRS),
    )
    opportunity = forms.ModelChoiceField(
        queryset=Opportunity.objects.all(),
        required=False,
        label=_("Opportunity"),
        widget=forms.Select(attrs=_SELECT_ATTRS),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def _check_visible(self, field_name):
        record = self.cleaned_data.get(field_name)
        if record is not None and not check_record_access(self.user, record):
            self.add_error(field_name, _("You do not have access to this record."))

    def clean(self):
        """Check that the user may see the selected records, if any. The form is valid even if both are empty."""
        cleaned = super().clean()
        for field_name in ("contact", "opportunity"):
            self._check_visible(field_name)
        return cleaned


@method_decorator(htmx_required, name="dispatch")
class LeadLinkRecordsView(LoginRequiredMixin, FormView):
    """
    Modal to connect a converted lead with existing records, for leads that were
    converted before links were stored or outside the Convert button.

    Only the link fields change; the lead itself stays read-only.
    """

    template_name = "lead_link_records.html"
    form_class = LeadLinkRecordsForm

    def dispatch(self, request, *args, **kwargs):
        """Load the lead; only a converted lead can be linked, by users who may convert it."""
        self.lead = get_object_or_404(Lead, pk=kwargs["pk"])
        user = request.user
        if not user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        if not (
            user.has_perm("leads.convert_lead")
            or (
                self.lead.lead_owner_id == user.pk
                and user.has_perm("leads.convert_own_lead")
            )
        ):
            return render(request, "403.html")
        if not self.lead.is_convert:
            messages.error(
                request,
                _("Convert the lead first, or pick existing records when converting."),
            )
            return ScriptResponse(reload=True, msgs=True, close=True)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        """Pass the user to the form, so it can check access to the selected records."""
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_initial(self):
        """Return the lead's current links, for the form's initial data."""
        return {
            "contact": self.lead.converted_contact,
            "opportunity": self.lead.converted_opportunity,
        }

    def get_context_data(self, **kwargs):
        """Add the lead and per-field data for the select boxes to the template context."""
        context = super().get_context_data(**kwargs)
        context["lead"] = self.lead
        context["link_fields"] = self._link_fields(context["form"])
        return context

    @staticmethod
    def _link_fields(form):
        """Per-field data for the select boxes: ajax source and the current choice."""
        fields = []
        for bound in form:
            model = bound.field.queryset.model
            selected = form.initial.get(bound.name) if not form.is_bound else None
            if form.is_bound and bound.value():
                selected = bound.field.queryset.filter(pk=bound.value()).first()
            fields.append(
                {
                    "name": bound.name,
                    "label": bound.label,
                    "app_label": model._meta.app_label,
                    "model_name": model.__name__,
                    "selected": selected,
                    "errors": bound.errors,
                }
            )
        return fields

    def form_valid(self, form):
        """Store the links without touching the (locked) lead's other fields."""
        data = form.cleaned_data
        Lead.objects.filter(pk=self.lead.pk).update(
            converted_contact=data["contact"],
            converted_opportunity=data["opportunity"],
            converted_at=self.lead.converted_at or timezone.now(),
        )
        messages.success(self.request, _("Lead linked."))
        return ScriptResponse(reload=True, msgs=True, close=True)
