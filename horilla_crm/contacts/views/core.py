"""
Views for managing contacts and related accounts in the CRM system.
Includes create, update, list, and relationship views with permission checks.
"""

# Standard library imports
import logging
from functools import cached_property
from urllib.parse import urlencode

# Third-party imports (Django)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import View

from horilla.contrib.activity.views import HorillaActivitySectionView
from horilla.contrib.generics.mixins import RecentlyViewedMixin
from horilla.contrib.generics.views import (
    HorillaChartView,
    HorillaDetailSectionView,
    HorillaDetailTabView,
    HorillaDetailView,
    HorillaGroupByView,
    HorillaHistorySectionView,
    HorillaKanbanView,
    HorillaListView,
    HorillaNavView,
    HorillaNotesAttachementSectionView,
    HorillaRelatedListSectionView,
    HorillaSplitView,
    HorillaView,
)
from horilla.contrib.generics.views.card import HorillaCardView
from horilla.contrib.generics.views.details import check_record_change_access
from horilla.contrib.generics.views.timeline import HorillaTimelineView

# First party imports (Horilla)
from horilla.shortcuts import get_object_or_404, render
from horilla.urls import reverse_lazy
from horilla.utils.decorators import (
    htmx_required,
    method_decorator,
    permission_required,
    permission_required_or_denied,
)
from horilla.utils.translation import gettext_lazy as _

# Local imports
from horilla_crm.contacts.filters import ContactFilter
from horilla_crm.contacts.models import Contact, ContactAccountRelationship

logger = logging.getLogger(__name__)


class ContactView(LoginRequiredMixin, HorillaView):
    """
    Render the contact page
    """

    nav_url = reverse_lazy("contacts:contacts_navbar")
    list_url = reverse_lazy("contacts:contact_list_view")
    kanban_url = reverse_lazy("contacts:contact_kanban_view")
    group_by_url = reverse_lazy("contacts:contact_group_by_view")
    card_url = reverse_lazy("contacts:contact_card_view")
    split_view_url = reverse_lazy("contacts:contact_split_view")
    chart_url = reverse_lazy("contacts:contact_chart_view")
    timeline_url = reverse_lazy("contacts:contacts_timeline")


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required(["contacts.view_contact", "contacts.view_own_contact"]),
    name="dispatch",
)
class ContactNavbar(LoginRequiredMixin, HorillaNavView):
    """
    Navbar View for Contact page
    """

    search_url = reverse_lazy("contacts:contact_list_view")
    main_url = reverse_lazy("contacts:contacts_view")
    kanban_url = reverse_lazy("contacts:contact_kanban_view")
    group_by_url = reverse_lazy("contacts:contact_group_by_view")
    card_url = reverse_lazy("contacts:contact_card_view")
    model_str = "contacts.Contact"
    model_name = "Contact"
    model_app_label = "contacts"
    filterset_class = ContactFilter
    exclude_kanban_fields = "company"
    enable_actions = True
    enable_quick_filters = True
    split_view_url = reverse_lazy("contacts:contact_split_view")
    chart_url = reverse_lazy("contacts:contact_chart_view")
    timeline_url = reverse_lazy("contacts:contacts_timeline")

    @cached_property
    def new_button(self):
        """Create a new contact button"""
        if self.request.user.has_perm(
            "contacts.add_contact"
        ) or self.request.user.has_perm("contacts.add_own_contact"):
            return {
                "url": f"""{reverse_lazy("contacts:contact_create_form")}?new=true""",
                "attrs": {"id": "contact-create"},
            }
        return None


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        ["contacts.view_contact", "contacts.view_own_contact"]
    ),
    name="dispatch",
)
class ContactListView(LoginRequiredMixin, HorillaListView):
    """
    Contact List View
    """

    model = Contact
    paginate_by = 20
    view_id = "contact-list"
    filterset_class = ContactFilter
    search_url = reverse_lazy("contacts:contact_list_view")
    main_url = reverse_lazy("contacts:contacts_view")
    enable_quick_filters = True

    def no_record_add_button(self):
        """Button to add a new contact if no records exist"""
        if self.request.user.has_perm(
            "contacts.add_contact"
        ) or self.request.user.has_perm("contacts.add_own_contact"):
            return {
                "url": f"""{reverse_lazy("contacts:contact_create_form")}?new=true""",
                "attrs": 'id="contact-create"',
            }
        return None

    bulk_update_fields = [
        "title",
        "contact_source",
        "languages",
        "address_city",
        "address_state",
        "address_zip",
        "address_country",
        "is_primary",
    ]

    header_attrs = [
        {"email": {"style": "width: 250px;"}, "title": {"style": "width: 250px;"}},
    ]

    columns = ["first_name", "last_name", "title", "email", "phone", "contact_source"]

    contact_permissions = {
        "permission": "contacts.change_contact",
        "own_permission": "contacts.change_own_contact",
        "owner_field": "contact_owner",
    }
    actions = [
        {
            **contact_permissions,
            "action": _("Edit"),
            "src": "assets/icons/edit.svg",
            "img_class": "w-4 h-4",
            "attrs": """
                            hx-get="{get_edit_url}?new=true"
                            hx-target="#modalBox"
                            hx-swap="innerHTML"
                            onclick="openModal()"
                            """,
        },
        {
            **contact_permissions,
            "action": _("Change Owner"),
            "src": "assets/icons/a2.svg",
            "img_class": "w-4 h-4",
            "attrs": """
                        hx-get="{get_change_owner_url}"
                        hx-target="#modalBox"
                        hx-swap="innerHTML"
                        onclick="openModal()"
                        """,
        },
        {
            "action": "Delete",
            "src": "assets/icons/a4.svg",
            "img_class": "w-4 h-4",
            "permission": "contacts.delete_contact",
            "own_permission": "contacts.delete_own_contact",
            "owner_field": "contact_owner",
            "attrs": """
                        hx-post="{get_delete_url}"
                        hx-target="#deleteModeBox"
                        hx-swap="innerHTML"
                        hx-trigger="click"
                        hx-vals='{{"check_dependencies": "true"}}'
                        onclick="openDeleteModeModal()"
                    """,
        },
        {
            "action": _("Duplicate"),
            "src": "assets/icons/duplicate.svg",
            "img_class": "w-4 h-4",
            "permission": "contacts.add_contact",
            "own_permission": "contacts.add_own_contact",
            "owner_field": "contact_owner",
            "attrs": """
                            hx-get="{get_duplicate_url}?duplicate=true"
                            hx-target="#modalBox"
                            hx-swap="innerHTML"
                            onclick="openModal()"
                            """,
        },
    ]

    @cached_property
    def col_attrs(self):
        """Attributes for columns in the contact list"""
        query_params = self.request.GET.dict()
        query_params = {}
        if "section" in self.request.GET:
            query_params["section"] = self.request.GET.get("section")
        query_string = urlencode(query_params)

        attrs = {
            "hx-get": f"{{get_detail_url}}?{query_string}",
            "hx-target": "#mainContent",
            "hx-swap": "outerHTML",
            "hx-push-url": "true",
            "hx-select": "#mainContent",
            "permission": "contacts.view_contact",
            "own_permission": "contacts.view_own_contact",
            "owner_field": "contact_owner",
        }
        return [
            {
                "first_name": {
                    **attrs,
                }
            }
        ]


@method_decorator(
    permission_required_or_denied(
        ["contacts.view_contact", "contacts.view_own_contact"]
    ),
    name="dispatch",
)
class ContactGroupByView(LoginRequiredMixin, HorillaGroupByView):
    """
    Contact Group By view
    """

    model = Contact
    view_id = "contacts-group-by"
    filterset_class = ContactFilter
    search_url = reverse_lazy("contacts:contact_list_view")
    main_url = reverse_lazy("contacts:contacts_view")
    enable_quick_filters = True
    group_by_field = "contact_source"

    columns = ["first_name", "last_name", "title", "email", "phone", "contact_source"]
    actions = ContactListView.actions

    def no_record_add_button(self):
        """Button to add a new contact if no records exist"""
        if self.request.user.has_perm(
            "contacts.add_contact"
        ) or self.request.user.has_perm("contacts.add_own_contact"):
            return {
                "url": f"""{reverse_lazy("contacts:contact_create_form")}?new=true""",
                "attrs": 'id="contact-create"',
            }
        return None

    @cached_property
    def col_attrs(self):
        """Attributes for columns in the contact group-by view"""
        query_params = {}
        if "section" in self.request.GET:
            query_params["section"] = self.request.GET.get("section")
        query_string = urlencode(query_params)
        attrs = {
            "hx-get": f"{{get_detail_url}}?{query_string}",
            "hx-target": "#mainContent",
            "hx-swap": "outerHTML",
            "hx-push-url": "true",
            "hx-select": "#mainContent",
            "permission": "contacts.view_contact",
            "own_permission": "contacts.view_own_contact",
            "owner_field": "contact_owner",
        }
        return [
            {
                "first_name": {
                    **attrs,
                }
            }
        ]


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        ["contacts.view_contact", "contacts.view_own_contact"]
    ),
    name="dispatch",
)
class ContactSplitView(LoginRequiredMixin, HorillaSplitView):
    """
    Contact Split view: left = tile list, right = simple details on click.
    """

    model = Contact
    view_id = "contact-split"
    filterset_class = ContactFilter
    search_url = reverse_lazy("contacts:contact_list_view")
    main_url = reverse_lazy("contacts:contacts_view")
    enable_quick_filters = True
    split_view_permission = "contacts.view_contact"
    split_view_own_permission = "contacts.view_own_contact"
    split_view_owner_field = "contact_owner"

    columns = ["first_name", "email"]

    no_record_add_button = ContactListView.no_record_add_button
    actions = ContactListView.actions


@method_decorator(
    permission_required_or_denied(
        ["contacts.view_contact", "contacts.view_own_contact"]
    ),
    name="dispatch",
)
class ContactKanbanView(LoginRequiredMixin, HorillaKanbanView):
    """
    Kanban view for Contact
    """

    model = Contact
    view_id = "contact-kanban"
    filterset_class = ContactFilter
    search_url = reverse_lazy("contacts:contact_list_view")
    main_url = reverse_lazy("contacts:contacts_view")
    group_by_field = "contact_source"
    actions = ContactListView.actions

    columns = ["first_name", "title", "email", "phone", "birth_date"]

    @cached_property
    def kanban_attrs(self):
        """Attributes for columns in the contact kanban"""
        query_params = self.request.GET.dict()
        query_params = {}
        if "section" in self.request.GET:
            query_params["section"] = self.request.GET.get("section")
        query_string = urlencode(query_params)
        if self.request.user.has_perm(
            "contacts.view_contact"
        ) or self.request.user.has_perm("contacts.view_own_contact"):
            return f"""
                    hx-get="{{get_detail_url}}?{query_string}"
                    hx-target="#mainContent"
                    hx-swap="outerHTML"
                    hx-push-url="true"
                    hx-select="#mainContent"
                    style ="cursor:pointer",
                    """
        return None


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        ["contacts.view_contact", "contacts.view_own_contact"]
    ),
    name="dispatch",
)
class ContactCardView(LoginRequiredMixin, HorillaCardView):
    """
    Card view for Contact
    """

    model = Contact
    view_id = "contact-card"
    filterset_class = ContactFilter
    search_url = reverse_lazy("contacts:contact_list_view")
    main_url = reverse_lazy("contacts:contacts_view")

    columns = ["first_name", "title", "email", "phone", "birth_date"]

    actions = ContactListView.actions

    col_attrs = ContactListView.col_attrs

    no_record_add_button = ContactListView.no_record_add_button


@method_decorator(
    permission_required_or_denied(
        ["contacts.view_contact", "contacts.view_own_contact"]
    ),
    name="dispatch",
)
class ContactTimelineView(LoginRequiredMixin, HorillaTimelineView):
    """Timeline from created_at to updated_at; rows by contact_source."""

    model = Contact
    view_id = "contacts-timeline"
    filterset_class = ContactFilter
    search_url = reverse_lazy("contacts:contact_list_view")
    main_url = reverse_lazy("contacts:contacts_view")
    enable_quick_filters = True
    timeline_start_field = "created_at"
    timeline_end_field = "updated_at"
    timeline_group_by_field = "contact_source"
    timeline_title_field = "first_name"
    columns = ["first_name", "last_name", "title", "email", "contact_source"]
    actions = ContactListView.actions
    col_attrs = ContactListView.col_attrs


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        ["contacts.view_contact", "contacts.view_own_contact"]
    ),
    name="dispatch",
)
class ContactChartView(LoginRequiredMixin, HorillaChartView):
    """Contact chart view: counts by group-by field using same filters as list/kanban."""

    model = Contact
    view_id = "contacts-chart"
    filterset_class = ContactFilter
    search_url = reverse_lazy("contacts:contact_list_view")
    main_url = reverse_lazy("contacts:contacts_view")
    group_by_field = "contact_source"
    exclude_kanban_fields = "company"


@method_decorator(
    permission_required_or_denied(
        ["contacts.view_contact", "contacts.view_own_contact"]
    ),
    name="dispatch",
)
class ContactDetailView(RecentlyViewedMixin, LoginRequiredMixin, HorillaDetailView):
    """
    Detail view for contact
    """

    model = Contact
    breadcrumbs = [
        ("People", "contacts:contacts_view"),
        ("Contacts", "contacts:contacts_view"),
    ]
    body = [
        "first_name",
        "title",
        "email",
        "phone",
        "birth_date",
        "contact_owner",
        "assistant",
    ]

    tab_url = reverse_lazy("contacts:contact_detail_view_tabs")
    actions = ContactListView.actions


@method_decorator(
    permission_required_or_denied(
        ["contacts.view_contact", "contacts.view_own_contact"]
    ),
    name="dispatch",
)
class ContactDetailViewTabs(LoginRequiredMixin, HorillaDetailTabView):
    """
    Tab Views for Contact Detail view
    """

    def _prepare_detail_tabs(self):
        self.object_id = self.request.GET.get("object_id")
        self.model = Contact
        super()._prepare_detail_tabs()

    urls = {
        "details": "contacts:contact_details_tab",
        "activity": "contacts:contact_activity_tab",
        "cadences": "cadences:contact_cadences_tab",
        "related_lists": "contacts:contact_related_list_tab",
        "notes_attachments": "contacts:contacts_notes_attachements",
        "history": "contacts:contact_history_tab",
    }


@method_decorator(
    permission_required_or_denied(
        ["contacts.view_contact", "contacts.view_own_contact"]
    ),
    name="dispatch",
)
class ContactDetailTab(LoginRequiredMixin, HorillaDetailSectionView):
    """
    Details tab of contact detail view
    """

    model = Contact
    excluded_fields = [
        "company",
        "id",
        "is_active",
        "additional_info",
        "created_at",
        "created_by",
        "updated_at",
        "updated_by",
        "history",
    ]


@method_decorator(
    permission_required_or_denied(
        ["contacts.view_contact", "contacts.view_own_contact"]
    ),
    name="dispatch",
)
class ContactActivityTab(LoginRequiredMixin, HorillaActivitySectionView):
    """
    Activity tab for contact detail view
    """

    model = Contact


@method_decorator(
    permission_required_or_denied(
        ["contacts.view_contact", "contacts.view_own_contact"]
    ),
    name="dispatch",
)
@method_decorator(
    permission_required_or_denied(
        ["contacts.view_contact", "contacts.view_own_contact"]
    ),
    name="dispatch",
)
class ContactsNotesAndAttachments(
    LoginRequiredMixin, HorillaNotesAttachementSectionView
):
    """Notes and Attachments tab for contact detail view"""

    model = Contact


@method_decorator(
    permission_required_or_denied(
        ["contacts.view_contact", "contacts.view_own_contact"]
    ),
    name="dispatch",
)
class ContactHistorytab(LoginRequiredMixin, HorillaHistorySectionView):
    """
    History tab for contact detail view
    """

    model = Contact


@method_decorator(
    permission_required_or_denied(
        ["contacts.view_contact", "contacts.view_own_contact"]
    ),
    name="dispatch",
)
class ContactRelatedListsTab(LoginRequiredMixin, HorillaRelatedListSectionView):
    """
    Related lists ab for contact detail view
    """

    model = Contact
    excluded_related_lists = [
        "opportunity_roles",
        "contact_campaign_members",
        "account_relationships",
        "bookings",
    ]

    def _can_add_to_related(self):
        """True if the user can add/edit records in the related tabs of this contact."""
        pk = self.request.GET.get("object_id")
        try:
            obj = Contact.objects.get(pk=pk)
            return check_record_change_access(self.request.user, obj)
        except Contact.DoesNotExist:
            return False

    @cached_property
    def related_list_config(self):
        """Configuration for related lists in the contact detail view"""
        query_params = {}
        if "section" in self.request.GET:
            query_params["section"] = self.request.GET.get("section")
        query_string = urlencode(query_params)
        pk = self.request.GET.get("object_id")
        referrer_url = "contact_detail_view"

        return {
            "custom_related_lists": {
                "campaigns": {
                    "app_label": "campaigns",
                    "model_name": "Campaign",
                    "intermediate_model": "CampaignMember",
                    "intermediate_field": "members",
                    "related_field": "contact",
                    "config": {
                        "title": _("Related Campaigns"),
                        "columns": [
                            (
                                Contact._meta.get_field("contact_campaign_members")
                                .related_model._meta.get_field("campaign")
                                .related_model._meta.get_field("campaign_name")
                                .verbose_name,
                                "campaign_name",
                            ),
                            (
                                Contact._meta.get_field("contact_campaign_members")
                                .related_model._meta.get_field("campaign")
                                .related_model._meta.get_field("status")
                                .verbose_name,
                                "get_status_display",
                            ),
                            (
                                Contact._meta.get_field("contact_campaign_members")
                                .related_model._meta.get_field("campaign")
                                .related_model._meta.get_field("start_date")
                                .verbose_name,
                                "start_date",
                            ),
                            (
                                Contact._meta.get_field("contact_campaign_members")
                                .related_model._meta.get_field("member_status")
                                .verbose_name,
                                "members__get_member_status_display",
                            ),
                        ],
                        "can_add": self._can_add_to_related(),
                        "add_url": reverse_lazy("campaigns:add_contact_to_campaign"),
                        "actions": [
                            {
                                "action": "edit",
                                "src": "/assets/icons/edit.svg",
                                "img_class": "w-4 h-4",
                                "permission": "campaigns.change_campaignmember",
                                "own_permission": "campaigns.change_own_campaignmember",
                                "owner_field": "created_by",
                                "intermediate_model": "CampaignMember",
                                "intermediate_field": "campaign",
                                "parent_field": "contact",
                                "attrs": """
                                        hx-get="{get_edit_contact_to_campaign_url_for_contact}?new=true"
                                        hx-target="#modalBox"
                                        hx-swap="innerHTML"
                                        onclick="event.stopPropagation();openModal()"
                                        hx-indicator="#modalBox"
                                        """,
                            },
                            (
                                {
                                    "action": "Delete",
                                    "src": "assets/icons/a4.svg",
                                    "img_class": "w-4 h-4",
                                    "permission": "campaigns.delete_campaignmember",
                                    "attrs": """
                                        hx-post="{get_delete_contact_to_campaign_url_for_contact}"
                                        hx-target="#deleteModeBox"
                                        hx-swap="innerHTML"
                                        hx-trigger="click"
                                        hx-vals='{{"check_dependencies": "true"}}'
                                        onclick="openDeleteModeModal()"
                                    """,
                                }
                            ),
                        ],
                        "col_attrs": [
                            (
                                {
                                    "campaign_name": {
                                        "hx-get": f"{{get_detail_view_url}}?referrer_app={self.model._meta.app_label}&referrer_model={self.model._meta.model_name}&referrer_id={pk}&referrer_url={referrer_url}&{query_string}",
                                        "hx-target": "#mainContent",
                                        "hx-swap": "outerHTML",
                                        "hx-push-url": "true",
                                        "hx-select": "#mainContent",
                                        "permission": "campaigns.view_campaign",
                                        "own_permission": "campaigns.view_own_campaign",
                                        "owner_field": "campaign_owner",
                                    }
                                }
                                if self.request.user.has_perm("campaigns.view_campaign")
                                else {}
                            )
                        ],
                    },
                },
                "opportunities": {
                    "app_label": "opportunities",
                    "model_name": "Opportunity",
                    "intermediate_model": "OpportunityContactRole",
                    "intermediate_field": "opportunity",
                    "related_field": "contact",
                    "config": {
                        "title": _("Related Opportunities"),
                        "columns": [
                            (
                                Contact._meta.get_field("opportunity_roles")
                                .related_model._meta.get_field("opportunity")
                                .related_model._meta.get_field("name")
                                .verbose_name,
                                "name",
                            ),
                            (
                                Contact._meta.get_field("opportunity_roles")
                                .related_model._meta.get_field("opportunity")
                                .related_model._meta.get_field("account")
                                .verbose_name,
                                "account__name",
                            ),
                            (
                                Contact._meta.get_field("opportunity_roles")
                                .related_model._meta.get_field("opportunity")
                                .related_model._meta.get_field("stage")
                                .verbose_name,
                                "stage__name",
                            ),
                            (
                                Contact._meta.get_field("opportunity_roles")
                                .related_model._meta.get_field("opportunity")
                                .related_model._meta.get_field("amount")
                                .verbose_name,
                                "amount",
                            ),
                            (
                                Contact._meta.get_field("opportunity_roles")
                                .related_model._meta.get_field("opportunity")
                                .related_model._meta.get_field("close_date")
                                .verbose_name,
                                "close_date",
                            ),
                            (
                                Contact._meta.get_field("opportunity_roles")
                                .related_model._meta.get_field("opportunity")
                                .related_model._meta.get_field("probability")
                                .verbose_name,
                                "probability",
                            ),
                        ],
                        "can_add": self._can_add_to_related(),
                        "add_url": reverse_lazy(
                            "opportunities:related_contact_opportunity_create"
                        ),
                        "actions": [
                            {
                                "action": "edit",
                                "src": "/assets/icons/edit.svg",
                                "img_class": "w-4 h-4",
                                "permission": "opportunities.change_opportunitycontactrole",
                                "own_permission": "opportunities.change_own_opportunitycontactrole",
                                "owner_field": "created_by",
                                "intermediate_model": "OpportunityContactRole",
                                "intermediate_field": "opportunity",
                                "parent_field": "contact",
                                "attrs": """
                                    hx-get="{get_edit_url}?new=true"
                                    hx-target="#modalBox"
                                    hx-swap="innerHTML"
                                    onclick="event.stopPropagation();openModal()"
                                    hx-indicator="#modalBox"
                                    """,
                            },
                            (
                                {
                                    "action": "Delete",
                                    "src": "assets/icons/a4.svg",
                                    "img_class": "w-4 h-4",
                                    "permission": "opportunities.delete_opportunitycontactrole",
                                    "attrs": """
                                        hx-post="{get_delete_url}"
                                        hx-target="#deleteModeBox"
                                        hx-swap="innerHTML"
                                        hx-trigger="click"
                                        hx-vals='{{"check_dependencies": "true"}}'
                                        onclick="openDeleteModeModal()"
                                    """,
                                }
                            ),
                        ],
                        "col_attrs": [
                            {
                                "name": {
                                    "hx-get": f"{{get_detail_url}}?referrer_app={self.model._meta.app_label}&referrer_model={self.model._meta.model_name}&referrer_id={pk}&referrer_url={referrer_url}&{query_string}",
                                    "hx-target": "#mainContent",
                                    "hx-swap": "outerHTML",
                                    "hx-push-url": "true",
                                    "hx-select": "#mainContent",
                                    "permission": "opportunities.view_opportunity",
                                    "own_permission": "opportunities.view_own_opportunity",
                                    "owner_field": "owner",
                                }
                            }
                        ],
                    },
                },
                "account_relationships": {
                    "app_label": "accounts",
                    "model_name": "Account",
                    "intermediate_model": "ContactAccountRelationship",
                    "intermediate_field": "contact_relationships",
                    "related_field": "contact",
                    "config": {
                        "title": _("Related Accounts"),
                        "can_add": self._can_add_to_related(),
                        "add_url": reverse_lazy(
                            "contacts:create_contact_account_relation"
                        ),
                        "columns": [
                            (
                                ContactAccountRelationship._meta.get_field("account")
                                .related_model._meta.get_field("name")
                                .verbose_name,
                                "name",
                            ),
                            (
                                ContactAccountRelationship._meta.get_field("account")
                                .related_model._meta.get_field("account_number")
                                .verbose_name,
                                "account_number",
                            ),
                            (
                                ContactAccountRelationship._meta.get_field("account")
                                .related_model._meta.get_field("annual_revenue")
                                .verbose_name,
                                "annual_revenue",
                            ),
                            (
                                ContactAccountRelationship._meta.get_field(
                                    "role"
                                ).verbose_name,
                                "contact_relationships__role",
                            ),
                        ],
                        "actions": [
                            {
                                "action": _("Edit"),
                                "src": "assets/icons/edit.svg",
                                "img_class": "w-4 h-4",
                                "permission": "contacts.change_contactaccountrelationship",
                                "own_permission": "contacts.change_own_contactaccountrelationship",
                                "owner_field": "created_by",
                                "intermediate_model": "ContactAccountRelationship",
                                "intermediate_field": "account",
                                "parent_field": "contact",
                                "attrs": """
                                    hx-get="{get_edit_contact_account_relation_url}?new=true"
                                    hx-target="#modalBox"
                                    hx-swap="innerHTML"
                                    onclick="openModal()"
                                    """,
                            },
                            (
                                {
                                    "action": "Delete",
                                    "src": "assets/icons/a4.svg",
                                    "img_class": "w-4 h-4",
                                    "permission": "contacts.delete_contactaccountrelationship",
                                    "attrs": """
                                        hx-post="{get_delete_related_accounts_url}"
                                        hx-target="#deleteModeBox"
                                            hx-swap="innerHTML"
                                            hx-trigger="click"
                                            hx-vals='{{"check_dependencies": "true"}}'
                                            onclick="openDeleteModeModal()"
                                    """,
                                }
                            ),
                        ],
                        "col_attrs": [
                            {
                                "name": {
                                    "hx-get": f"{{get_detail_url}}?referrer_app={self.model._meta.app_label}&referrer_model={self.model._meta.model_name}&referrer_id={pk}&referrer_url={referrer_url}&{query_string}",
                                    "hx-target": "#mainContent",
                                    "hx-swap": "outerHTML",
                                    "hx-push-url": "true",
                                    "hx-select": "#mainContent",
                                    "permission": "accounts.view_account",
                                    "own_permission": "accounts.view_own_account",
                                    "owner_field": "account_owner",
                                }
                            }
                        ],
                    },
                },
            },
            "child_contacts": {
                "title": _("Child Contacts"),
                "can_add": self._can_add_to_related(),
                "add_url": reverse_lazy("contacts:create_child_contact"),
                "columns": [
                    (Contact._meta.get_field("title").verbose_name, "title"),
                    (Contact._meta.get_field("first_name").verbose_name, "first_name"),
                    (Contact._meta.get_field("last_name").verbose_name, "last_name"),
                    (Contact._meta.get_field("email").verbose_name, "email"),
                ],
                "actions": [
                    (
                        {
                            "action": "Delete",
                            "src": "assets/icons/a4.svg",
                            "img_class": "w-4 h-4",
                            "permission": "contacts.change_contact",
                            "own_permission": "contacts.change_own_contact",
                            "owner_field": "contact_owner",
                            "attrs": """
                            hx-delete="{get_child_contact_delete_url}"
                            hx-on:click="hxConfirm(this,'Are you sure you want to remove this child contact relationship?')"
                            hx-target="#deleteModeBox"
                            hx-swap="innerHTML"
                            hx-trigger="confirmed"
                    """,
                        }
                    ),
                ],
                "col_attrs": [
                    {
                        "title": {
                            "hx-get": f"{{get_detail_url}}?referrer_app={self.model._meta.app_label}&referrer_model={self.model._meta.model_name}&referrer_id={pk}&referrer_url={referrer_url}&{query_string}",
                            "hx-target": "#mainContent",
                            "hx-swap": "outerHTML",
                            "hx-push-url": "true",
                            "hx-select": "#mainContent",
                            "permission": "contacts.view_contact",
                            "own_permission": "contacts.view_own_contact",
                            "owner_field": "contact_owner",
                        }
                    }
                ],
                "custom_buttons": [
                    {
                        "label": _("View Hierarchy"),
                        "url": reverse_lazy("contacts:contact_hierarchy"),
                        "attrs": """
                                        hx-target="#modalBox"
                                        hx-swap="innerHTML"
                                        onclick="openModal()"
                                        hx-indicator="#modalBox"
                                    """,
                        "icon": "fa-solid fa-sitemap",
                        "class": "text-xs px-4 py-1.5 bg-white border border-primary-600 text-primary-600 rounded-md transition duration-300",
                    },
                ],
            },
        }


def _build_contact_tree(contact):
    """Build tree of contact and descendants for <details> hierarchy."""
    return {
        "contact": contact,
        "children": [_build_contact_tree(c) for c in contact.child_contacts.all()],
    }


def _get_root_contact(contact):
    """Traverse up to the topmost ancestor of a contact."""
    while contact.parent_contact is not None:
        contact = contact.parent_contact
    return contact


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        ["contacts.view_contact", "contacts.view_own_contact"]
    ),
    name="dispatch",
)
class ContactHierarchyView(LoginRequiredMixin, View):
    """Modal view showing contact hierarchy with expand/collapse (no JS)."""

    def get(self, request, *args, **kwargs):
        """Get method for contact hierarchy"""

        contact_id = request.GET.get("id")
        if not contact_id:
            return render(request, "403.html", {"modal": True})
        contact = get_object_or_404(Contact, pk=contact_id)
        root_contact = _get_root_contact(contact)
        root = _build_contact_tree(root_contact)
        return render(
            request,
            "contact_hierarchy_modal.html",
            {"root": root, "active_contact_id": contact.pk},
        )
