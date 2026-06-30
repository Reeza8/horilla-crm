"""
A generic class-based view for rendering the home page.
"""

# Standard library imports
import json
import logging
import os

# Third-party imports (other)
import pycountry

# Third-party imports (Django)
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.cache import cache
from django.utils._os import safe_join
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.views import View
from django.views.generic import TemplateView
from django.views.generic.base import RedirectView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import UntypedToken

# First party imports (Horilla)
from horilla import settings
from horilla.contrib.mail.models import HorillaMailConfiguration
from horilla.shortcuts import redirect, render
from horilla.urls import reverse_lazy
from horilla.utils.branding import load_branding
from horilla.utils.choices import BLOCKED_EXTENSIONS
from horilla.utils.decorators import (
    htmx_required,
    method_decorator,
    permission_required_or_denied,
)
from horilla.utils.translation import gettext_lazy as _
from horilla.web import (
    FileResponse,
    HttpNotFound,
    HttpResponse,
    JsonResponse,
    RedirectResponse,
    safe_url,
)

from ..models import ActiveTab, Company
from ..signals import pre_login_render_signal, pre_logout_signal

# Local imports
from .initialiaze_database import InitializeDatabaseConditionView

logger = logging.getLogger(__name__)


def is_jwt_token_valid(auth_header):
    """Check if the provided JWT token is valid and return the associated user."""
    if not auth_header or not auth_header.startswith("Bearer "):
        return None  # No token

    token = auth_header.split("Bearer ")[1].strip()
    try:
        UntypedToken(token)  # Will raise if invalid
        validated_token = JWTAuthentication().get_validated_token(token)
        user = JWTAuthentication().get_user(validated_token)
        return user
    except (InvalidToken, TokenError):
        return None


def protected_media(request, path):
    """Serve protected media files with access control."""
    try:
        media_path = safe_join(settings.MEDIA_ROOT, path)
    except ValueError as exc:
        raise HttpNotFound("Invalid file path") from exc

    if not os.path.isfile(media_path):
        raise HttpNotFound("File not found")

    # Block dangerous extensions
    _, ext = os.path.splitext(media_path)
    if ext.lower() in BLOCKED_EXTENSIONS:
        raise HttpNotFound("Access denied")

    # Otherwise require authentication
    jwt_user = is_jwt_token_valid(request.META.get("HTTP_AUTHORIZATION", ""))

    if not request.user.is_authenticated and not jwt_user:
        return redirect("core:login")

    response = FileResponse(open(media_path, "rb"))
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private"

    return response


class HomePageView(LoginRequiredMixin, View):
    """
    Redirect to default home page
    """

    def get(self, request, *args, **kwargs):
        """
        Redirect to default home page
        """

        return redirect(settings.DEFAULT_HOME_REDIRECT)


@method_decorator(htmx_required, name="dispatch")
class ReloadMessages(LoginRequiredMixin, TemplateView):
    """
    Reload messages
    """

    template_name = "messages.html"

    def get_context_data(self, **kwargs):
        """
        Get context data for reloading messages.
        """

        context = super().get_context_data(**kwargs)
        return context


class SaveActiveTabView(LoginRequiredMixin, View):
    """
    View to save the active tab for a user.
    """

    def post(self, request, *args, **kwargs):
        """
        Save the active tab for the user.
        """
        tab_target = request.POST.get("tab_target")
        path = request.POST.get("path")
        user = request.user if request.user.is_authenticated else None
        company = getattr(request, "active_company", None)

        if user and tab_target and path:
            ActiveTab.objects.update_or_create(
                created_by=user,
                path=path,
                company=company if company else user.company,
                defaults={"tab_target": tab_target},
            )
            return JsonResponse({"status": "success"})

        return JsonResponse({"status": "error", "message": "Invalid data"}, status=400)

    def get(self, request, *args, **kwargs):
        """
        Handle GET requests with an error response.
        """

        return JsonResponse(
            {"status": "error", "message": "Invalid method"}, status=405
        )


class LoginUserView(View):
    """
    Class-based view to handle user login.
    """

    def get(self, request):
        """
        Render login page with an optional 'next' param preserved.
        """
        next_url = safe_url(request, request.GET.get("next", "/"))
        condition_view = InitializeDatabaseConditionView()
        initialize_database = condition_view.get_initialize_condition()
        show_forgot_password = False
        hq_company = Company.objects.filter(hq=True).first()

        if hq_company:
            show_forgot_password = HorillaMailConfiguration.objects.filter(
                company=hq_company
            ).exists()

        context = {
            "next": next_url,
            "initialize_database": initialize_database,
            "show_forgot_password": show_forgot_password,
        }

        _responses = pre_login_render_signal.send(
            sender=self.__class__, request=request, context=context
        )

        return render(request, "login.html", context=context)

    def post(self, request):
        """
        Handle login attempt
        """
        identifier = request.POST.get("username")
        secret = request.POST.get("password")
        next_url = safe_url(request, request.POST.get("next", "/"))

        ip = (
            request.META.get(
                "HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "")
            )
            .split(",")[0]
            .strip()
        )
        lockout_key = f"login_lockout_{ip}"
        attempt_key = f"login_attempts_{ip}"

        # Block IP if currently locked out
        if cache.get(lockout_key):
            messages.error(
                request,
                _("Too many failed login attempts. Please try again in 15 minutes."),
            )
            return redirect(reverse_lazy("core:login") + f"?next={next_url}")

        user = authenticate(request, username=identifier, password=secret)

        if not user:
            attempts = cache.get(attempt_key, 0) + 1
            if attempts >= 5:
                cache.set(lockout_key, True, timeout=900)  # lock for 15 minutes
                cache.delete(attempt_key)
                logger.warning("Brute force lockout triggered for IP %s", ip)
                messages.error(
                    request,
                    _(
                        "Too many failed login attempts. Please try again in 15 minutes."
                    ),
                )
            else:
                cache.set(attempt_key, attempts, timeout=900)
                messages.error(
                    request, _("Invalid credentials. Please check and try again.")
                )
            return redirect(reverse_lazy("core:login") + f"?next={next_url}")

        if not user.is_active:
            messages.warning(
                request,
                _("This user is archived or blocked. Please contact support."),
            )
            return redirect(reverse_lazy("core:login") + f"?next={next_url}")

        # Clear failed attempt counters on successful login
        cache.delete(attempt_key)
        cache.delete(lockout_key)

        login(request, user)
        messages.success(request, _("Login successful."))
        next_url = safe_url(request, next_url)
        return redirect(next_url)


class LogoutView(View):
    """
    Class-based view to logout the user and clear local storage.
    All preservation logic is handled by signal receivers.
    """

    def get(self, request, *args, **kwargs):
        """
        Logout the user and clear local storage.
        """

        # Collect data from all registered signal receivers
        storage_data = {}

        if request.user.is_authenticated:
            responses = pre_logout_signal.send(sender=self.__class__, request=request)

            for _receiver, response in responses:
                if response and isinstance(response, tuple) and len(response) == 2:
                    storage_key, data = response
                    if storage_key and data:
                        storage_data[storage_key] = data

        if request.user.is_authenticated:
            logout(request)

        storage_data_json = json.dumps(storage_data) if storage_data else "{}"

        script_content = f"""
        <script>
            // Save theme mode before clearing (always preserved)
            const theme = localStorage.getItem('theme');

            // Clear everything
            localStorage.clear();

            // Always restore theme mode if it existed
            if (theme !== null) {{
                localStorage.setItem('theme', theme);
            }}

            const storageData = {storage_data_json};
            for (const [key, value] of Object.entries(storageData)) {{
                localStorage.setItem(key, JSON.stringify(value));
            }}
        </script>

        <meta http-equiv="refresh" content="0;url=/login">
        """

        response = HttpResponse()
        response.content = script_content
        return response


@method_decorator(
    permission_required_or_denied("core.can_view_horilla_settings"),
    name="dispatch",
)
class SettingView(LoginRequiredMixin, TemplateView):
    """
    TemplateView for settings page.
    """

    template_name = "settings/settings.html"


class MySettingView(LoginRequiredMixin, TemplateView):
    """
    TemplateView for settings page.
    """

    template_name = "settings/my_settings.html"


@method_decorator(
    permission_required_or_denied("core.can_switch_company"), name="dispatch"
)
class SwitchCompanyView(LoginRequiredMixin, View):
    """
    View to switch active company for the user.
    """

    def post(self, request, company_id):
        """
        Switch the active company for the user.
        """
        if request.user.is_authenticated and (
            request.user.has_perm("core.can_switch_company")
            or request.user.company_id == company_id
        ):
            request.session["active_company_id"] = company_id
        return RedirectResponse(self.request)


@method_decorator(htmx_required, name="dispatch")
class ToggleAllCompaniesView(LoginRequiredMixin, View):
    """
    View to toggle "show all companies" mode globally via session.
    """

    def post(self, request):
        """
        Toggle the all_companies setting in session.
        """
        current_value = request.session.get("show_all_companies", False)
        request.session["show_all_companies"] = not current_value
        request.session.save()

        # Return HX-Redirect to refresh the page
        referer = request.META.get("HTTP_REFERER", "/")
        response = HttpResponse(status=200)
        response["HX-Redirect"] = referer
        return response


@method_decorator(htmx_required, name="dispatch")
@method_decorator(permission_required_or_denied("core.view_company"), name="dispatch")
class CompanyDetailsTab(LoginRequiredMixin, TemplateView):
    """
    TemplateView for company details tab.
    """

    template_name = "settings/company_details_tab.html"

    def get_context_data(self, **kwargs):
        """
        Get context data for company details tab.
        """
        context = super().get_context_data(**kwargs)
        company = getattr(self.request, "active_company", None)
        if company:
            obj = company
        else:
            obj = self.request.user.company
        context["obj"] = obj
        return context


@method_decorator(htmx_required, name="dispatch")
class GetCountrySubdivisionsView(LoginRequiredMixin, View):
    """
    View to get country subdivisions (states/provinces) based on country code.
    """

    def get(self, request, *args, **kwargs):
        """
        Get HTML options for country subdivisions based on country code.

        Args:
            request: The HTTP request object.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            HttpResponse: HTML string containing option elements for subdivisions.
        """
        country_code = request.GET.get("country")
        options = mark_safe('<option value="">Select State</option>')

        if country_code:
            subdivisions = pycountry.subdivisions.get(country_code=country_code.upper())
            if subdivisions:
                for subdivision in subdivisions:
                    options += (
                        f'<option value="{escape(subdivision.code)}">'
                        f"{escape(subdivision.name)}</option>"
                    )

        return HttpResponse(options)


class FaviconRedirectView(RedirectView):
    """Redirect to the configured favicon."""

    branding = load_branding()
    favicon_path = branding.get("FAVICON_PATH", "favicon.ico")
    url = staticfiles_storage.url(favicon_path)
