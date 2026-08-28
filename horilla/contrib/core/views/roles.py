"""
Views related to Role management in Horilla Core.
"""

# Standard library imports
from functools import cached_property
from urllib.parse import urlencode

# Third-party imports (Django)
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Permission
from django.db.models import Count
from django.template.loader import render_to_string
from django.utils.html import escapejs
from django.views import View

from horilla.auth.models import User
from horilla.contrib.generics.views import (
    HorillaListView,
    HorillaNavView,
    HorillaSingleDeleteView,
    HorillaSingleFormView,
)
from horilla.contrib.generics.views.core import HorillaView
from horilla.contrib.utils.middlewares import _thread_local
from horilla.shortcuts import get_object_or_404
from horilla.urls import reverse_lazy
from horilla.utils.decorators import (
    htmx_required,
    method_decorator,
    permission_required,
    permission_required_or_denied,
)
from horilla.utils.translation import gettext_lazy as _

# First party imports (Horilla)
from horilla.views.generic import TemplateView
from horilla.web import HttpResponse, HxTriggerResponse, ScriptResponse

# Local imports
from ..filters import RoleFilter, UserFilter
from ..forms import AddUsersToRoleForm
from ..models import Role


@method_decorator(
    permission_required_or_denied("core.view_role"),
    name="dispatch",
)
class RolesView(LoginRequiredMixin, HorillaView):
    """
    Template view for team role page
    """

    template_name = "settings/settings_list_shell.html"
    view_id = "role-view"
    nav_url = reverse_lazy("core:roles_nav_bar")
    list_url = reverse_lazy("core:role_list_view")
    kanban_url = reverse_lazy("core:roles_hierarchy_view")


@method_decorator(htmx_required, name="dispatch")
class AddRole(LoginRequiredMixin, HorillaSingleFormView):
    """
    View to create or edit a Role
    """

    model = Role
    fields = ["role_name", "parent_role", "description"]
    full_width_fields = ["role_name", "parent_role", "description"]
    modal_height = False
    # hidden_fields = ["parent_role"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = getattr(_thread_local, "request", None)
        role_id = request.GET.get("role_id")
        role_count = Role.objects.all().count()
        if role_id or role_count == 0:
            self.hidden_fields = ["parent_role"]

    @cached_property
    def form_url(self):
        """
        Determine the form URL based on whether editing or creating a role.
        """
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if pk:
            return reverse_lazy("core:edit_roles_view", kwargs={"pk": pk})
        return reverse_lazy("core:create_roles_view")

    def get(self, request, *args, **kwargs):
        """
        Handle GET request to display the role form.
        """
        pk = kwargs.get("pk")
        if pk:
            try:
                self.model.objects.get(pk=pk)
            except self.model.DoesNotExist:
                messages.error(request, _("The requested role does not exist."))
                return ScriptResponse(reload=True)

        return super().get(request, *args, **kwargs)

    def get_initial(self):
        """
        Set initial data for the form, particularly the parent_role if provided.
        """
        initial = super().get_initial()
        role_id = self.request.GET.get("role_id")
        role = Role.objects.filter(pk=role_id).first()
        if role:
            initial["parent_role"] = role
        return initial


@method_decorator(htmx_required, name="dispatch")
class AddUserToRole(LoginRequiredMixin, HorillaSingleFormView):
    """
    View to add users to a Role
    """

    model = User
    form_class = AddUsersToRoleForm
    full_width_fields = ["role", "users"]
    modal_height = False
    form_url = reverse_lazy("core:add_user_to_roles_view")
    hidden_fields = ["role"]
    save_and_new = False

    def get_initial(self):
        """
        Set initial data for the form, particularly the role if provided.
        """
        initial = super().get_initial()
        role_id = self.request.GET.get("role_id")
        role = Role.objects.filter(pk=role_id).first()  # Get the first object or None
        if role:
            initial["role"] = role
        return initial

    def form_valid(self, form):
        """
        Handle valid form submission to add users to the role.
        """
        users = form.save(commit=True)
        messages.success(
            self.request,
            _(
                f"Successfully assigned {len(users)} user(s) to the role '{form.cleaned_data['role']}'."
            ),
        )
        return ScriptResponse(reload=True, close=True)


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        f"{User._meta.app_label}.view_{User._meta.model_name}"
    ),
    name="dispatch",
)
class RoleUsersListView(LoginRequiredMixin, HorillaListView):
    """
    List view to display users in a specific role
    """

    model = User
    filterset_class = UserFilter
    table_width = False
    view_id = "user-roles"
    filter_url_push = False
    search_url = reverse_lazy("core:view_user_in_role_list_view")
    main_url = reverse_lazy("core:view_user_in_role")
    bulk_delete_enabled = False
    bulk_update_fields = ["role"]
    save_to_list_option = False
    filter_url_push = False
    main_session_id = "role-user-list"

    def get_queryset(self):
        """
        Filter the queryset to only include users in the specified role.
        """
        queryset = super().get_queryset()
        role_id = self.request.GET.get("role_id")
        if role_id:
            try:
                Role.objects.get(pk=role_id)
                queryset = queryset.filter(role=role_id)
                return queryset
            except Exception:
                messages.error(self.request, _("The requested role does not exist."))
                return ScriptResponse(reload=True, extra="closeContentModal();")
        return queryset.none()

    @cached_property
    def col_attrs(self):
        """
        Define column attributes, including HTMX attributes for interactivity.
        """
        query_params = self.request.GET.dict()
        query_params = {}
        if "section" in self.request.GET:
            query_params["section"] = self.request.GET.get("section")
        query_string = urlencode(query_params)
        if self.request.user.has_perm(
            f"{User._meta.app_label}.view_{User._meta.model_name}"
        ):
            htmx_attrs = {
                "hx-get": f"{{get_detail_view_url}}?{query_string}",
                "hx-target": "#role-container",
                "hx-swap": "outerHTML",
                "hx-push-url": "true",
                "hx-select": "#users-view",
                "hx-on:click": "closeContentModal()",
            }
        return [
            {
                "get_avatar_with_name": {
                    "style": "cursor:pointer",
                    "class": "hover:text-primary-600",
                    **htmx_attrs,
                }
            }
        ]

    columns = [
        (_("Users"), "get_avatar_with_name"),
    ]

    @cached_property
    def actions(self):
        """
        Return the delete-user-from-role action configuration.
        """
        confirm_msg = escapejs(
            _("Are you sure you want to delete the user from this role?")
        )
        return [
            {
                "action": "Delete",
                "src": "assets/icons/a4.svg",
                "img_class": "w-4 h-4",
                "permission": "core.delete_role",
                "attrs": f"""
                hx-post="{{get_delete_user_from_role}}"
                hx-target="#deleteModeBox"
                hx-swap="innerHTML"
                hx-trigger="confirmed"
                hx-on:click="hxConfirm(this,'{confirm_msg}')"
                hx-on::after-request="$('#reloadMessagesButton').click();"
            """,
            }
        ]


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        f"{User._meta.app_label}.view_{User._meta.model_name}"
    ),
    name="dispatch",
)
class UsersInRoleView(LoginRequiredMixin, TemplateView):
    """
    Detail view to display users in a specific role
    """

    template_name = "role/view_user.html"

    def get(self, request, *args, **kwargs):
        """
        Handle GET request and validate role_id.

        When called with search or filter params (i.e. a navbar search request),
        delegate to RoleUsersListView and return the list HTML wrapped in a
        #mainSession div so HTMX hx-select="#mainSession" works correctly without
        triggering a second load via hx-trigger="load".
        """
        role_id = request.GET.get("role_id")

        if not role_id:
            messages.error(request, _("Please select a role to continue."))
            return ScriptResponse(reload=True, extra="closeContentModal();")

        try:
            Role.objects.get(pk=role_id)
        except Exception:
            messages.error(request, _("The requested role does not exist."))
            return ScriptResponse(reload=True, extra="closeContentModal();")

        # If this is a search/filter request from the navbar, render the list
        # directly wrapped in #mainSession to avoid hx-trigger="load" re-firing.
        is_search_request = bool(
            request.GET.get("search")
            or request.GET.get("apply_filter")
            or request.GET.get("field")
        )
        if is_search_request:
            list_view = RoleUsersListView()
            list_view.request = request
            list_view.args = args
            list_view.kwargs = kwargs
            list_view.object_list = list_view.get_queryset()
            list_context = list_view.get_context_data()
            list_html = render_to_string(
                "list_view.html", list_context, request=request
            )
            # Re-render the navbar with current request params so the
            # filter count badge updates (OOB swap targets #navbar-roles).
            nav_view = RoleUsersNavView()
            nav_view.request = request
            nav_view.args = args
            nav_view.kwargs = kwargs
            nav_context = nav_view.get_context_data()
            nav_html = render_to_string("navbar.html", nav_context, request=request)
            navbar_oob = f'<div id="navbar-roles" class="p-5 pb-0 w-full" hx-swap-oob="true">{nav_html}</div>'
            wrapped = (
                f'<div id="role-user-list" class="pl-5 pb-5 pr-7 pt-0">{list_html}</div>'
                f"{navbar_oob}"
            )
            return HttpResponse(wrapped)

        return super().get(request, *args, **kwargs)


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        f"{User._meta.app_label}.view_{User._meta.model_name}"
    ),
    name="dispatch",
)
class RoleUsersNavView(LoginRequiredMixin, HorillaNavView):
    """
    Nav view to display users in a specific role
    """

    search_url = reverse_lazy("core:view_user_in_role_list_view")
    main_url = reverse_lazy("core:view_user_in_role")
    filterset_class = UserFilter
    model_name = str(User.__name__)
    model_app_label = "core"
    nav_width = False
    all_view_types = False
    recently_viewed_option = False
    one_view_only = True
    reload_option = False
    border_enabled = False
    navbar_indication = True
    search_push_url = False
    main_session_id = "role-user-list"

    def get_context_data(self, **kwargs):
        """
        Add role information to the context data.
        """
        context = super().get_context_data(**kwargs)
        role_id = self.request.GET.get("role_id")
        role = Role.objects.filter(pk=role_id).first()
        self.nav_title = role

        context["nav_title"] = self.nav_title
        return context

    def get_navbar_indication_attrs(self):

        return {"onclick": "closeContentModal()"}


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("core.change_role", modal=True),
    name="dispatch",
)
class DeleteUserFromRole(LoginRequiredMixin, View):
    """
    Remove role from a user (without deleting the user)
    """

    def post(self, request, *args, **kwargs):
        """
        Handle POST request to remove a user from a role.
        """
        user_id = kwargs.get("pk")
        try:
            user = get_object_or_404(User, pk=user_id)
        except Exception:
            messages.error(request, _("The requested user does not exist."))
            return ScriptResponse(
                reload=True, extra="closeDeleteModeModal();closeContentModal();"
            )

        role = user.role
        if role is not None:
            default_perm_ids = set(
                Permission.objects.filter(codename__startswith="view_own_").values_list(
                    "id", flat=True
                )
            )
            role_perm_ids = set(role.permissions.values_list("id", flat=True))
            perms_to_remove_ids = role_perm_ids - default_perm_ids
            if perms_to_remove_ids:
                perms_to_remove = Permission.objects.filter(id__in=perms_to_remove_ids)
                user.user_permissions.remove(*perms_to_remove)

        user.role = None
        user.save()

        messages.success(request, f"{user.username} removed from role")

        return HxTriggerResponse(extra="closeDeleteModeModal();closeContentModal();")


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("core.delete_role", modal=True),
    name="dispatch",
)
class RoleDeleteView(LoginRequiredMixin, HorillaSingleDeleteView):
    """
    View to delete a Role
    """

    model = Role

    def get_post_delete_response(self):
        """
        Handle post-delete response to refresh the role list.
        """
        return ScriptResponse(reload=True, extra="closeDeleteModeModal();")


@method_decorator(htmx_required, name="dispatch")
@method_decorator(permission_required("core.view_role"), name="dispatch")
class RoleNavbar(LoginRequiredMixin, HorillaNavView):
    """
    Navbar for team role. Default layout is kanban (hierarchy view).
    """

    nav_title = Role._meta.verbose_name_plural
    nav_description = _(
        "Define roles and their position in your organization's hierarchy."
    )
    search_url = reverse_lazy("core:role_list_view")
    main_url = reverse_lazy("core:roles_view")
    kanban_url = reverse_lazy("core:roles_hierarchy_view")
    default_layout = "kanban"
    filterset_class = RoleFilter
    all_view_types = False
    reload_option = False
    nav_width = False
    url_name = "role_list_view"
    border_enabled = False

    def get_context_data(self, **kwargs):
        """Show search option only when in list view, not in hierarchy view."""
        context = super().get_context_data(**kwargs)
        effective = context.get("effective_layout", "list")
        context["search_option"] = effective == "list"
        context["filter_option"] = effective == "list"
        return context

    @cached_property
    def new_button(self):
        """
        Get the configuration for the "New" button in the navbar.
        """
        if self.request.user.has_perm("core.add_role"):
            return {
                "title": _("Add Role"),
                "url": f"""{reverse_lazy("core:create_roles_view")}?new=true""",
                "attrs": {"id": "role-create"},
            }
        return None


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("core.view_role"),
    name="dispatch",
)
class RolesHierarchyView(LoginRequiredMixin, TemplateView):
    """
    TemplateView for role settings page.
    """

    template_name = "role/role.html"

    def get_context_data(self, **kwargs):
        """Add role tree, companies, and show_all_companies to context."""
        context = super().get_context_data(**kwargs)
        show_all_companies = self.request.session.get("show_all_companies", False)

        def build_role_tree(roles_by_parent, parent_id):
            """Build role hierarchy in-memory from a preloaded, pre-annotated role list."""
            role_tree = []
            for role in roles_by_parent.get(parent_id, []):
                role_tree.append(
                    {
                        "id": role.id,
                        "name": role.role_name,
                        "description": getattr(role, "description", ""),
                        "user_count": role.user_count,
                        "children": build_role_tree(roles_by_parent, role.id),
                    }
                )
            return role_tree

        def group_roles_by_parent(roles_queryset):
            """Annotate user counts once and group roles by parent_role_id in memory."""
            roles_by_parent = {}
            for role in roles_queryset.select_related(
                "company", "parent_role"
            ).annotate(user_count=Count("users", distinct=True)):
                roles_by_parent.setdefault(role.parent_role_id, []).append(role)
            return roles_by_parent

        if show_all_companies:
            # Group roles by company when "all company" is activated
            all_roles = list(Role.all_objects.all().select_related("company"))
            companies_with_roles = {}

            # Group roles by company
            for role in all_roles:
                company = role.company
                if company:
                    if company not in companies_with_roles:
                        companies_with_roles[company] = []
                    companies_with_roles[company].append(role)

            # Build company-grouped structure
            companies_data = []
            for company, company_roles in companies_with_roles.items():
                # Build role tree for this company's roles only
                company_roles_queryset = Role.all_objects.filter(company=company)
                roles_by_parent = group_roles_by_parent(company_roles_queryset)
                roles_tree = build_role_tree(roles_by_parent, None)

                companies_data.append(
                    {
                        "company": company,
                        "company_id": company.id,
                        "company_name": company.name,
                        "roles": roles_tree,
                        "roles_count": len(company_roles),
                    }
                )

            # Also include roles without company
            roles_without_company = [role for role in all_roles if not role.company]
            if roles_without_company:
                roles_without_company_queryset = Role.all_objects.filter(
                    company__isnull=True
                )
                roles_by_parent = group_roles_by_parent(roles_without_company_queryset)
                roles_tree = build_role_tree(roles_by_parent, None)
                companies_data.append(
                    {
                        "company": None,
                        "company_id": None,
                        "company_name": "No Company",
                        "roles": roles_tree,
                        "roles_count": len(roles_without_company),
                    }
                )

            context["companies_data"] = companies_data
            context["show_all_companies"] = True
            context["roles_count"] = len(all_roles)
        else:
            # Original behavior: filter by active company
            company = getattr(self.request, "active_company", None)
            if not company and hasattr(self.request.user, "company"):
                company = self.request.user.company
            roles = (
                Role.objects.filter(company=company)
                if company
                else Role.objects.filter(company__isnull=True)
            )
            roles_by_parent = group_roles_by_parent(roles)
            roles_data = build_role_tree(roles_by_parent, None)
            context["roles_data"] = roles_data
            context["show_all_companies"] = False
            context["roles_count"] = sum(len(v) for v in roles_by_parent.values())

        return context


@method_decorator(htmx_required, name="dispatch")
@method_decorator(permission_required_or_denied("core.view_teamrole"), name="dispatch")
class RoleListView(LoginRequiredMixin, HorillaListView):
    """
    List view of team role
    """

    model = Role
    view_id = "role_list"
    filterset_class = RoleFilter
    search_url = reverse_lazy("core:role_list_view")
    main_url = reverse_lazy("core:roles_view")
    bulk_select_option = False

    @cached_property
    def no_record_add_button(self):
        """
        Get the configuration for the "Add" button when no record exist.
        """
        if self.request.user.has_perm("core.add_role"):
            return {
                "url": f"""{reverse_lazy("core:create_roles_view")}?new=true""",
                "attrs": 'id="role-create"',
            }
        return None

    columns = ["role_name", "parent_role"]

    actions = [
        {
            "action": "Edit",
            "src": "assets/icons/edit.svg",
            "img_class": "w-4 h-4",
            "permission": "core.change_role",
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
            "permission": "core.delete_role",
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
