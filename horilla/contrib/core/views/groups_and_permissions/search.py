"""
Views for searching and filtering models in role and user permissions management.
"""

# Third-party imports (Django)
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator

from horilla.auth.models import User
from horilla.db.models import Q
from horilla.shortcuts import get_object_or_404, render
from horilla.utils.decorators import (
    htmx_required,
    method_decorator,
    permission_required_or_denied,
)
from horilla.utils.translation import gettext_lazy as _

# First party imports (Horilla)
from horilla.views.generic import TemplateView
from horilla.web import ScriptResponse

from ...models import Role

# Local imports
from .permission_utils import PermissionUtils


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        [
            "auth.view_permission",
            "auth.view_group",
            "auth.change_permission",
            "auth.change_group",
        ]
    ),
    name="dispatch",
)
class SearchRoleModelsView(LoginRequiredMixin, TemplateView):
    """
    View to search and filter models in role permissions view
    """

    template_name = "permissions/search_permission/role_models_list.html"

    def get(self, request, role_id, *args, **kwargs):
        """Return filtered role models list HTML for search; reload script on invalid role."""
        try:
            role = get_object_or_404(Role, id=role_id)
        except Exception:
            messages.error(request, _("Role does not exist"))
            return ScriptResponse(reload=True)

        search_query = request.GET.get("search", "").strip()

        context = {
            "role": role,
            "all_models": PermissionUtils.get_all_models_data(
                role=role, search_query=search_query
            ),
        }
        return render(request, self.template_name, context)


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        [
            "auth.view_permission",
            "auth.view_group",
            "auth.change_permission",
            "auth.change_group",
        ]
    ),
    name="dispatch",
)
class SearchUserModelsView(LoginRequiredMixin, TemplateView):
    """
    View to search and filter models in role permissions view
    """

    template_name = "permissions/search_permission/user_models_list.html"

    def get(self, request, user_id, *args, **kwargs):
        """Return filtered user models list HTML for search; reload script on invalid user."""
        try:
            user = get_object_or_404(User, id=user_id)
        except Exception:
            messages.error(request, _("User does not exist"))
            return ScriptResponse(reload=True)

        search_query = request.GET.get("search", "").strip()

        context = {
            "user": user,
            "all_models": PermissionUtils.get_all_models_data(
                user=user, search_query=search_query
            ),
        }
        return render(request, self.template_name, context)


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        [
            "auth.view_permission",
            "auth.view_group",
            "auth.change_permission",
            "auth.change_group",
        ]
    ),
    name="dispatch",
)
class SearchAssignModelsView(LoginRequiredMixin, TemplateView):
    """
    Search view for assign permissions form (no specific user/role)
    """

    template_name = "permissions/search_permission/assign_models_list.html"

    def get(self, request, *args, **kwargs):
        """Return assign models list HTML filtered by search query."""
        search_query = request.GET.get("search", "").strip()

        context = {
            "all_models": PermissionUtils.get_all_models_data(
                search_query=search_query
            ),
        }
        return render(request, self.template_name, context)


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        [
            "auth.view_permission",
            "auth.view_group",
            "auth.change_permission",
            "auth.change_group",
        ]
    ),
    name="dispatch",
)
class LoadUserPermissionsView(LoginRequiredMixin, TemplateView):
    """
    View to load permissions for a specific user
    """

    template_name = "permissions/user_permissions.html"

    def get(self, request, user_id, *args, **kwargs):
        """Load permissions for a specific user."""
        try:
            user = get_object_or_404(User, id=user_id)
        except Exception:
            messages.error(self.request, _("User Does not Exist"))
            return ScriptResponse(reload=True)
        context = {
            "user": user,
            "all_models": PermissionUtils.get_all_models_data(user=user),
        }
        return render(request, self.template_name, context)


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        [
            "auth.view_permission",
            "auth.view_group",
            "auth.change_permission",
            "auth.change_group",
        ]
    ),
    name="dispatch",
)
class LoadMoreUsersView(LoginRequiredMixin, TemplateView):
    """
    View to load more users for infinite scrolling with search functionality
    """

    template_name = "permissions/user_list.html"

    def get(self, request, *args, **kwargs):
        """Return paginated user list HTML, optionally filtered by search."""
        search_query = request.GET.get("search", "").strip()

        users = User.objects.filter(is_superuser=False)

        if search_query:
            search_words = search_query.split()

            q_object = Q()
            for word in search_words:
                q_object &= (
                    Q(username__icontains=word)
                    | Q(first_name__icontains=word)
                    | Q(last_name__icontains=word)
                )

            users = users.filter(q_object)

        paginator = Paginator(users, 10)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context = {
            "users": page_obj,
            "page_obj": page_obj,
            "search_query": search_query,
        }

        return render(request, self.template_name, context)
