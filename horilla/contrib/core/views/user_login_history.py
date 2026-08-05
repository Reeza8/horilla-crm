"""
This view handles the methods for user login history view
"""

# Third-party imports (Django)
from django.contrib.auth.mixins import LoginRequiredMixin

from horilla.contrib.generics.views import HorillaListView, HorillaNavView, HorillaView

# First party imports (Horilla)
from horilla.urls import reverse_lazy
from horilla.utils.decorators import (
    htmx_required,
    method_decorator,
    permission_required_or_denied,
)
from horilla.utils.translation import gettext_lazy as _


@method_decorator(
    permission_required_or_denied(
        ["login_history.view_loginhistory", "login_history.view_own_loginhistory"]
    ),
    name="dispatch",
)
class UserLoginHistoryView(LoginRequiredMixin, HorillaView):
    """
    Main login history view of user
    """

    template_name = "settings/users/users_login_history_view.html"
    nav_url = reverse_lazy("core:user_login_history_nav")
    list_url = reverse_lazy("core:user_login_history_list")


@method_decorator(htmx_required, name="dispatch")
class UserLoginHistoryNavbar(LoginRequiredMixin, HorillaNavView):
    """
    user Login history navbar
    """

    from login_history.models import LoginHistory

    nav_title = _("My Login History")
    nav_description = _("Review the sign-in activity on your account.")
    search_url = reverse_lazy("core:user_login_history_list")
    main_url = reverse_lazy("core:user_login_history_view")
    model_name = "LoginHistory"
    model_app_label = "login_history"
    nav_width = False
    all_view_types = False
    recently_viewed_option = False
    filter_option = False
    one_view_only = True
    reload_option = False
    search_option = False


@method_decorator(htmx_required, name="dispatch")
class UserloginHistoryListView(LoginRequiredMixin, HorillaListView):
    """
    Login History list view of the user
    """

    from login_history.models import LoginHistory

    model = LoginHistory
    view_id = "UserLoginHistory"

    search_url = reverse_lazy("core:user_login_history_list")
    main_url = reverse_lazy("core:login_history_view")
    bulk_delete_enabled = False
    bulk_update_option = False
    enable_sorting = False
    table_width = False
    table_height_as_class = "h-[calc(_100vh_-_300px_)]"

    def get_queryset(self):
        user = self.request.user
        opts = self.model._meta
        if user.has_perm(f"{opts.app_label}.view_{opts.model_name}") or user.has_perm(
            f"{opts.app_label}.view_own_{opts.model_name}"
        ):
            return self.model.objects.filter(user_id=user)
        return self.model.objects.none()

    columns = [
        (_("Browser"), "short_user_agent"),
        (_("Login Time"), "formatted_datetime"),
        (_("Is Active"), "is_login_icon"),
        (_("IP"), "ip"),
        (_("Status"), "user_status"),
    ]
