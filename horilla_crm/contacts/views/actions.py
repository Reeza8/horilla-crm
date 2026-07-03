"""Contact action views for create, relation, and hierarchy workflows."""

# Standard library imports
import logging
from functools import cached_property

# Third-party imports (Django)
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.views.generic import FormView, View

from horilla.contrib.generics.views import (
    HorillaMultiStepFormView,
    HorillaSingleDeleteView,
    HorillaSingleFormView,
)
from horilla.contrib.generics.views.details import (
    check_record_change_access,
    check_record_delete_access,
)
from horilla.shortcuts import get_object_or_404, render
from horilla.urls import reverse_lazy
from horilla.utils import timezone
from horilla.utils.decorators import (
    htmx_required,
    method_decorator,
    permission_required_or_denied,
)
from horilla.utils.translation import gettext_lazy as _

# First party imports (Horilla)
from horilla.web import HttpResponse

# Local imports
from horilla_crm.contacts.forms import (
    ChildContactForm,
    ContactFormClass,
    ContactSingleForm,
)
from horilla_crm.contacts.models import Contact, ContactAccountRelationship
from horilla_crm.contacts.signals import set_contact_account_id

logger = logging.getLogger(__name__)


@method_decorator(htmx_required, name="dispatch")
class ContactFormView(LoginRequiredMixin, HorillaMultiStepFormView):
    """
    Contact form view for create and edit
    """

    form_class = ContactFormClass
    model = Contact
    total_steps = 3
    fullwidth_fields = ["languages", "description"]
    detail_url_name = "contacts:contact_detail_view"
    step_titles = {
        "1": _("Contact Information"),
        "2": _("Address Information"),
        "3": _("Additional Information"),
    }

    single_step_url_name = {
        "create": "contacts:contact_single_create_form",
        "edit": "contacts:contact_single_update_form",
    }

    @cached_property
    def form_url(self):
        """Get the URL for the form, either for creating or editing a contact"""
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if pk:
            return reverse_lazy("contacts:contact_create_form", kwargs={"pk": pk})
        return reverse_lazy("contacts:contact_update_form")


@method_decorator(htmx_required, name="dispatch")
class ContactsSingleFormView(LoginRequiredMixin, HorillaSingleFormView):
    """Account Create/Update Single Page View"""

    model = Contact
    form_class = ContactSingleForm
    full_width_fields = ["description"]
    detail_url_name = "contacts:contact_detail_view"

    multi_step_url_name = {
        "create": "contacts:contact_create_form",
        "edit": "contacts:contact_update_form",
    }

    @cached_property
    def form_url(self):
        """Form URL for lead"""
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if pk:
            return reverse_lazy(
                "contacts:contact_single_update_form", kwargs={"pk": pk}
            )
        return reverse_lazy("contacts:contact_single_create_form")


@method_decorator(htmx_required, name="dispatch")
class RelatedContactFormView(LoginRequiredMixin, HorillaMultiStepFormView):
    """
    Contact form view for create and edit
    """

    form_class = ContactFormClass
    model = Contact
    total_steps = 3
    fullwidth_fields = ["languages", "description"]
    save_and_new = False
    step_titles = {
        "1": _("Contact Information"),
        "2": _("Address Information"),
        "3": _("Additional Information"),
    }

    def form_valid(self, form):
        step = self.get_initial_step()

        if step == self.total_steps:
            account_id = self.request.GET.get("id")
            if account_id:
                set_contact_account_id(
                    account_id=account_id, company=self.request.active_company
                )
            super().form_valid(form)
            return HttpResponse(
                "<script>htmx.trigger('#tab-contact_relationships-btn','click');closeModal();</script>"
            )

        return super().form_valid(form)

    @cached_property
    def form_url(self):
        """Get the URL for the form, either for creating or editing a contact"""
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if pk:
            return reverse_lazy("contacts:contact_create_form", kwargs={"pk": pk})
        return reverse_lazy("contacts:contact_update_form")

    def get(self, request, *args, **kwargs):
        contact_id = self.kwargs.get("pk")
        if request.user.has_perm("contacts.change_contact") or request.user.has_perm(
            "contacts.add_contact"
        ):
            return super().get(request, *args, **kwargs)

        if contact_id:
            contact = get_object_or_404(Contact, pk=contact_id)
            if contact.contact_owner == request.user:
                return super().get(request, *args, **kwargs)

        return render(request, "403.html")


@method_decorator(htmx_required, name="dispatch")
class ContactChangeOwnerFormView(LoginRequiredMixin, HorillaSingleFormView):
    """
    Change owner form
    """

    model = Contact
    fields = ["contact_owner"]
    full_width_fields = ["contact_owner"]
    modal_height = False
    form_title = _("Change Owner")

    @cached_property
    def form_url(self):
        """Get the URL for changing the owner of a contact"""
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if pk:
            return reverse_lazy("contacts:contact_change_owner", kwargs={"pk": pk})
        return None

    def has_permission(self):
        user = self.request.user
        if user.is_superuser:
            return True
        if user.has_perm("contacts.change_contact") or user.has_perm(
            "contacts.add_contact"
        ):
            return True
        contact_id = self.kwargs.get("pk")
        if contact_id:
            contact = get_object_or_404(Contact, pk=contact_id)
            return check_record_change_access(user, contact)
        return False


@method_decorator(htmx_required, name="dispatch")
class AddRelatedAccountsFormView(LoginRequiredMixin, HorillaSingleFormView):
    """
    Create and update form for adding related accounts into contacts
    """

    model = ContactAccountRelationship
    modal_height = False
    fields = ["contact", "account", "role"]
    form_title = _("Add Account Contact Relationships")
    full_width_fields = ["account", "contact", "role"]
    hidden_fields = ["contact"]
    save_and_new = False

    def _get_contact(self):
        pk = self.kwargs.get("pk")
        contact_id = self.request.GET.get("id")
        if pk:
            from horilla_crm.contacts.models import ContactAccountRelationship

            rel = get_object_or_404(ContactAccountRelationship, pk=pk)
            return rel.contact
        if contact_id:
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

    def form_valid(self, form):
        super().form_valid(form)
        return HttpResponse(
            "<script>htmx.trigger('#tab-account_relationships-btn', 'click');closeModal();</script>"
        )

    def get_initial(self):
        """Prefill contact relation form from the selected contact id."""
        initial = super().get_initial()
        obj_id = self.request.GET.get("id")
        if obj_id:
            initial["contact"] = obj_id
        return initial

    @cached_property
    def form_url(self):
        """Get the URL for creating or editing a contact-account relationship"""
        if self.kwargs.get("pk"):
            return reverse_lazy(
                "contacts:edit_contact_account_relation",
                kwargs={"pk": self.kwargs.get("pk")},
            )
        return reverse_lazy("contacts:create_contact_account_relation")


@method_decorator(htmx_required, name="dispatch")
class AddChildContactFormView(LoginRequiredMixin, FormView):
    """
    Form view to select an existing campaign and assign it as a child contact.
    """

    template_name = "single_form_view.html"
    form_class = ChildContactForm
    header = True

    def get(self, request, *args, **kwargs):
        """Authorize access to child-contact form based on ownership or permissions."""
        contact_id = request.GET.get("id")
        if contact_id:
            contact = get_object_or_404(Contact, pk=contact_id)
            if check_record_change_access(request.user, contact):
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
        """Prepopulate the form with initial data if needed."""
        initial = super().get_initial()
        parent_id = self.request.GET.get("id")

        if parent_id:
            try:
                parent_contact = Contact.objects.get(pk=parent_id)
                initial["parent_contact"] = parent_contact.id
                company = getattr(self.request, "active_company", None)
                initial["company"] = company
            except Contact.DoesNotExist:
                logger.error("Parent contact with ID %s not found", parent_id)

        return initial

    def get_context_data(self, **kwargs):
        """
        Add context data for the template.
        """
        context = super().get_context_data(**kwargs)
        context["form_title"] = _("Add Child Contact")
        context["full_width_fields"] = ["contact"]

        form_url = self.get_form_url()

        context["form_url"] = str(form_url)
        context["modal_height"] = False
        context["view_id"] = "add-child-contact-form-view"
        context["condition_fields"] = []
        context["header"] = self.header
        context["field_permissions"] = {}

        context["hx_attrs"] = {
            "hx-post": str(form_url),
            "hx-target": "#modalBox",
            "hx-swap": "innerHTML",
        }

        return context

    def form_valid(self, form):
        """
        Update the selected contact's parent_contact field and return HTMX response.
        """

        if not self.request.user.is_authenticated:
            messages.error(
                self.request, _("You must be logged in to perform this action.")
            )
            return self.form_invalid(form)

        selected_contact = form.cleaned_data["contact"]
        parent_contact = form.cleaned_data.get("parent_contact")

        if not parent_contact:
            form.add_error(None, _("No parent contact specified in the request."))
            return self.form_invalid(form)

        try:
            if selected_contact.id == parent_contact.id:
                form.add_error("contact", _("A contact cannot be its own parent."))
                result = self.form_invalid(form)
            elif selected_contact.parent_contact:
                form.add_error(
                    "contact", _("This contact already has a parent contact.")
                )
                result = self.form_invalid(form)
            else:
                selected_contact.parent_contact = parent_contact
                selected_contact.updated_at = timezone.now()
                selected_contact.updated_by = self.request.user
                selected_contact.save()
                messages.success(
                    self.request, _("Child contact assigned successfully.")
                )
                result = HttpResponse(
                    "<script>htmx.trigger('#tab-child_contacts-btn', 'click');closeModal();</script>"
                )
        except ValidationError as e:
            msg = (
                next(iter(e.message_dict.values()))[0]
                if hasattr(e, "message_dict")
                else e.message
            )
            form.add_error("contact", msg)
            result = self.form_invalid(form)
        except ValueError:
            form.add_error(None, _("Invalid parent contact ID format."))
            result = self.form_invalid(form)

        return result

    def get_form_url(self):
        """
        Get the form URL for submission.
        """
        return reverse_lazy("contacts:create_child_contact")


@method_decorator(htmx_required, name="dispatch")
class ChildContactDeleteView(LoginRequiredMixin, View):
    """
    View to remove parent-child relationship from a contact.
    """

    def delete(self, request, pk, *args, **kwargs):
        """
        Handle DELETE request to remove parent contact relationship.
        """
        child_contact = get_object_or_404(Contact, pk=pk)

        parent_contact = child_contact.parent_contact or child_contact
        has_permission = check_record_delete_access(request.user, parent_contact)

        if not has_permission:
            messages.error(
                request, _("You don't have permission to perform this action.")
            )
            return HttpResponse(
                "<script>htmx.trigger('#tab-child_contacts-btn', 'click');</script>",
                status=403,
            )

        parent_contact = child_contact.parent_contact

        if not parent_contact:
            messages.warning(request, _("This contact doesn't have a parent contact."))
            return HttpResponse(
                "<script>htmx.trigger('#tab-child_contacts-btn', 'click');</script>"
            )

        try:
            child_contact.parent_contact = None
            child_contact.updated_at = timezone.now()
            child_contact.updated_by = request.user
            child_contact.save()

            messages.success(
                request,
                _(
                    f"Successfully removed {child_contact} from {parent_contact}'s child contacts."
                ),
            )

            return HttpResponse(
                "<script>htmx.trigger('#tab-child_contacts-btn', 'click');</script>"
            )
        except Exception:
            messages.error(
                request, _("An error occurred while removing the child contact.")
            )
            return HttpResponse(
                "<script>htmx.trigger('#tab-child_contacts-btn', 'click');</script>",
            )


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("contacts.delete_contact", modal=True),
    name="dispatch",
)
class ContactDeleteView(LoginRequiredMixin, HorillaSingleDeleteView):
    """Delete a contact"""

    model = Contact

    def get_post_delete_response(self):
        """Response after a contact is deleted"""
        return HttpResponse("<script>htmx.trigger('#reloadButton','click');</script>")


@method_decorator(htmx_required, name="dispatch")
class RelatedContactDeleteView(LoginRequiredMixin, HorillaSingleDeleteView):
    """View for deleting related contact account relationships."""

    model = ContactAccountRelationship

    def dispatch(self, request, *args, **kwargs):
        rel = get_object_or_404(ContactAccountRelationship, pk=self.kwargs.get("pk"))
        if not check_record_delete_access(request.user, rel.contact):
            return render(request, "403.html", {"modal": True})
        return super().dispatch(request, *args, **kwargs)

    def get_post_delete_response(self):
        return HttpResponse(
            "<script>htmx.trigger('#tab-account_relationships-btn','click');</script>"
            "<script>htmx.trigger('#tab-contact_relationships-btn','click');</script>"
        )
