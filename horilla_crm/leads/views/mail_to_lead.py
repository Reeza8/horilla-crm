"""Views and utilities for email-to-lead functionality."""

# Standard library imports
from functools import cached_property

# Third-party imports (Django)
from django.contrib.auth.mixins import LoginRequiredMixin

from horilla.contrib.generics.views import (
    HorillaListView,
    HorillaNavView,
    HorillaSingleDeleteView,
    HorillaSingleFormView,
    HorillaView,
)
from horilla.urls import reverse_lazy
from horilla.utils.decorators import (
    htmx_required,
    method_decorator,
    permission_required,
    permission_required_or_denied,
)
from horilla.utils.translation import gettext_lazy as _

# First party imports (Horilla)
from horilla.web import HttpResponse

# Local imports
from horilla_crm.leads.forms import EmailToLeadForm
from horilla_crm.leads.models import EmailToLeadConfig


class MailToLeadView(LoginRequiredMixin, HorillaView):
    """
    TemplateView for company information settings page.
    """

    template_name = "mail_to_lead/mail_to_lead.html"
    nav_url = reverse_lazy("leads:mail_to_lead_nav_bar")
    list_url = reverse_lazy("leads:mail_to_lead_list_view")


@method_decorator(htmx_required, name="dispatch")
@method_decorator(permission_required("leads.view_emailtoleadconfig"), name="dispatch")
class MailToLeadNavbar(LoginRequiredMixin, HorillaNavView):
    """Navbar for Mail to lead"""

    nav_title = _("Mail to Lead")
    search_url = reverse_lazy("leads:mail_to_lead_list_view")
    main_url = reverse_lazy("leads:mail_to_lead_view")
    nav_width = False
    search_option = False
    gap_enabled = False
    all_view_types = False
    recently_viewed_option = False
    filter_option = False
    one_view_only = True
    reload_option = False
    border_enabled = False

    @cached_property
    def new_button(self):
        """New button configuration"""
        if self.request.user.has_perm("leads.add_emailtoleadconfig"):
            return {
                "url": f"""{reverse_lazy("leads:mail_to_lead_create_view")}?new=true""",
                "attrs": {"id": "mail-to-lead-create"},
            }
        return None


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("leads.view_emailtoleadconfig"), name="dispatch"
)
class MailToLeadListView(LoginRequiredMixin, HorillaListView):
    """
    Mail to lead list view
    """

    model = EmailToLeadConfig
    view_id = "mail-to-lead-list"
    search_url = reverse_lazy("leads:mail_to_lead_list_view")
    main_url = reverse_lazy("leads:mail_to_lead_view")
    save_to_list_option = False
    bulk_select_option = False
    table_width = False
    enable_sorting = False
    table_height_as_class = "h-[calc(_100vh_-_260px_)]"
    list_column_visibility = False

    def no_record_add_button(self):
        """Button to show when no records exist"""
        if self.request.user.has_perm("leads.add_emailtoleadconfig"):
            return {
                "url": f"""{reverse_lazy("leads:mail_to_lead_create_view")}?new=true""",
                "attrs": 'id="mail-to-lead-create"',
            }
        return None

    @cached_property
    def columns(self):
        """Define columns for the list view"""
        instance = self.model()
        return [
            (instance._meta.get_field("mail").verbose_name, "mail"),
            (
                instance._meta.get_field("mail")
                .related_model._meta.get_field("type")
                .verbose_name,
                "mail__get_type_display",
            ),
            (instance._meta.get_field("lead_owner").verbose_name, "lead_owner"),
        ]

    actions = [
        {
            "action": "Edit",
            "src": "assets/icons/edit.svg",
            "img_class": "w-4 h-4",
            "permission": "leads.change_emailtoleadconfig",
            "attrs": """
                    hx-get="{get_edit_url}?new=true"
                    hx-target="#modalBox"
                    hx-swap="innerHTML"
                    onclick="openModal()"
                    """,
        },
        {
            "action": "Delete",
            "src": "assets/icons/a4.svg",
            "img_class": "w-4 h-4",
            "permission": "leads.delete_emailtoleadconfig",
            "attrs": """
                hx-post="{get_delete_url}"
                hx-target="#deleteModeBox"
                hx-swap="innerHTML"
                hx-trigger="click"
                hx-vals='{{"check_dependencies": "true"}}'
                onclick="openDeleteModeModal()"
            """,
        },
    ]


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("leads.add_emailtoleadconfig"), name="dispatch"
)
class MailToLeadFormView(LoginRequiredMixin, HorillaSingleFormView):
    """View to create or edit a mail to lead configuration instance."""

    model = EmailToLeadConfig
    form_class = EmailToLeadForm
    modal_height = False

    @cached_property
    def form_url(self):
        """URL to load the form"""
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if pk:
            return reverse_lazy("leads:mail_to_lead_update_view", kwargs={"pk": pk})
        return reverse_lazy("leads:mail_to_lead_create_view")


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("leads.delete_emailtoleadconfig", modal=True),
    name="dispatch",
)
class EmailToLeadConfigDeleteView(LoginRequiredMixin, HorillaSingleDeleteView):
    """View for deleting email-to-lead configuration."""

    model = EmailToLeadConfig

    def get_post_delete_response(self):
        return HxTriggerResponse(id="reloadButton")
