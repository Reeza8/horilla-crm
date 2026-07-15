"""
mail Outlook mail server views.
"""

# Standard library imports
from datetime import datetime
from functools import cached_property

# Third-party imports (Django)
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core import cache
from django.views import View
from requests_oauthlib import OAuth2Session

from horilla.contrib.generics.views import HorillaSingleFormView
from horilla.shortcuts import redirect
from horilla.urls import reverse_lazy

# First party imports (Horilla)
from horilla.utils import timezone
from horilla.utils.decorators import (
    htmx_required,
    method_decorator,
    permission_required_or_denied,
)
from horilla.utils.translation import gettext_lazy as _
from horilla.web import RedirectResponse, ScriptResponse

# Local imports
from ..forms import OutlookMailConfigurationForm
from ..models import HorillaMailConfiguration


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(["mail.add_horillamailconfiguration"]),
    name="dispatch",
)
class OutlookMailServerFormView(LoginRequiredMixin, HorillaSingleFormView):
    """
    create and update from view for mail server
    """

    model = HorillaMailConfiguration
    modal_height = False
    form_class = OutlookMailConfigurationForm
    hidden_fields = ["company", "type", "mail_channel"]
    save_and_new = False

    def get_initial(self):
        """Set initial form data for Outlook mail configuration (OAuth URLs and channel)."""
        initial = super().get_initial()
        pk = self.kwargs.get("pk")
        company = getattr(self.request, "active_company", None)
        if not pk:
            initial["outlook_authorization_url"] = (
                "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
            )
            initial["outlook_token_url"] = (
                "https://login.microsoftonline.com/common/oauth2/v2.0/token"
            )
            initial["outlook_api_endpoint"] = "https://graph.microsoft.com/v1.0"
            initial["company"] = company
            initial["type"] = "outlook"
            initial["mail_channel"] = "outgoing"
            if self.request.GET.get("type") == "incoming":
                initial["mail_channel"] = "incoming"
        return initial

    @cached_property
    def form_url(self):
        """Get the URL for the form view."""
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if pk:
            return reverse_lazy(
                "mail:outlook_mail_server_update_view", kwargs={"pk": pk}
            )
        return reverse_lazy("mail:outlook_mail_server_form_view")

    def form_valid(self, form):
        super().form_valid(form)
        return ScriptResponse(reload=True, close=True, extra="closehorillaModal();")


@method_decorator(
    permission_required_or_denied(["mail.view_horillamailconfiguration"]),
    name="dispatch",
)
class OutlookLoginView(View):
    """
    Handles Outlook login OAuth flow
    """

    def get(self, request, *args, pk=None, **kwargs):
        """Get the Outlook login URL."""
        selected_company = request.active_company

        if pk:
            api = HorillaMailConfiguration.objects.filter(pk=pk).first()
        else:
            api = HorillaMailConfiguration.objects.filter(
                company=selected_company
            ).first()

        if not api:
            messages.info(request, _("Not configured outlook"))
            return redirect("/")  # redirect somewhere safe if no config

        # Validate required fields before proceeding
        if not api.outlook_client_id:
            messages.error(request, _("Outlook Client ID is not configured"))
            return redirect("/")

        if not api.outlook_redirect_uri:
            messages.error(request, _("Outlook Redirect URI is not configured"))
            return redirect("/")

        if not api.outlook_authorization_url:
            messages.error(request, _("Outlook Authorization URL is not configured"))
            return redirect("/")

        oauth = OAuth2Session(
            api.outlook_client_id,
            redirect_uri=api.outlook_redirect_uri,
            scope=["Mail.Read", "Mail.Send", "offline_access"],
        )
        authorization_url, state = oauth.authorization_url(
            api.outlook_authorization_url
        )

        self.request.session["outlook_pk"] = pk
        self.request.session.modified = True
        self.request.session.save()

        api.oauth_state = state
        api.save()

        cache.cache.set("oauth_state", state)

        return redirect(authorization_url)


@method_decorator(
    permission_required_or_denied(["mail.view_horillamailconfiguration"]),
    name="dispatch",
)
class OutlookCallbackView(View):
    """
    Handles Outlook OAuth callback
    """

    def get(self, request, *args, **kwargs):
        """Handle the OAuth callback and fetch the token."""
        selected_company = request.active_company
        pk = self.request.session.get("outlook_pk")

        if pk:
            api = HorillaMailConfiguration.objects.filter(pk=pk).first()
        else:
            api = HorillaMailConfiguration.objects.filter(
                company=selected_company
            ).first()

        if not api or api.type != "outlook":
            messages.error(request, _("Invalid Outlook configuration"))
            return redirect("/")

        # Validate required fields before proceeding
        if not api.outlook_client_id:
            messages.error(request, _("Outlook Client ID is not configured"))
            return redirect("/")

        if not api.outlook_redirect_uri:
            messages.error(request, _("Outlook Redirect URI is not configured"))
            return redirect("/")

        if not api.outlook_token_url:
            messages.error(request, _("Outlook Token URL is not configured"))
            return redirect("/")

        client_secret = api.get_decrypted_client_secret()
        if not client_secret:
            messages.error(request, _("Outlook Client Secret is not configured"))
            return redirect("/")

        state = api.oauth_state

        oauth = OAuth2Session(
            api.outlook_client_id,
            state=state,
            redirect_uri=api.outlook_redirect_uri,
        )

        authorization_response_uri = request.build_absolute_uri()
        if not authorization_response_uri:
            messages.error(request, _("Unable to build authorization response URI"))
            return redirect("/")

        authorization_response_uri = authorization_response_uri.replace(
            "http://", "https://"
        )

        api.last_refreshed = datetime.now()
        token = oauth.fetch_token(
            api.outlook_token_url,
            client_secret=client_secret,
            authorization_response=authorization_response_uri,
        )
        api.token = token
        api.save()

        return redirect("/")


def refresh_outlook_token(api: HorillaMailConfiguration):
    """
    Refresh Outlook token
    """
    # Check if token exists and has refresh_token
    if not api.token or not isinstance(api.token, dict):
        raise ValueError("Token is missing or invalid")

    refresh_token = api.token.get("refresh_token")
    if not refresh_token:
        raise ValueError("Refresh token is missing. Please re-authenticate.")

    oauth = OAuth2Session(
        api.outlook_client_id,
        token=api.token,
        auto_refresh_kwargs={
            "client_id": api.outlook_client_id,
            "client_secret": api.get_decrypted_client_secret(),
        },
        auto_refresh_url=api.outlook_token_url,
    )
    new_token = oauth.refresh_token(
        api.outlook_token_url,
        refresh_token=refresh_token,
        client_id=api.outlook_client_id,
        client_secret=api.get_decrypted_client_secret(),
    )
    api.token = new_token
    api.last_refreshed = timezone.now()
    api.save()
    return api


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(["mail.view_horillamailconfiguration"]),
    name="dispatch",
)
class OutlookRefreshTokenView(View):
    """
    Refresh Outlook token
    """

    def get(self, request, pk, *args, **kwargs):
        """Refresh the Outlook token for the given configuration."""
        try:
            api = HorillaMailConfiguration.objects.get(pk=pk)
        except Exception as e:
            messages.error(
                request,
                str(e),
            )
            return ScriptResponse(reload=True, close=True)

        try:
            old_token = api.token.get("access_token") if api.token else None

            api = refresh_outlook_token(api)

            if api.token.get("access_token") == old_token:
                messages.info(request, _("Token not refreshed, Login required"))
            else:
                messages.success(request, _("Token refreshed successfully"))
        except ValueError as e:
            messages.error(
                request,
                _("Token refresh failed: {error}. Please re-authenticate.").format(
                    error=str(e)
                ),
            )
        except Exception as e:
            messages.error(
                request,
                _("Token refresh failed: {error}").format(error=str(e)),
            )

        return RedirectResponse(request)
