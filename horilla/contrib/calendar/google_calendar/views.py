"""
Views for Google Calendar integration.

5 class-based views, all requiring login:

1. GoogleCalendarSettingsView  — GET/POST: upload credentials JSON, show status
2. GoogleCalendarAuthorizeView — GET: start OAuth2 flow (redirects to Google)
3. GoogleCalendarCallbackView  — GET: handle OAuth2 callback from Google
4. GoogleCalendarDisconnectView — POST: revoke connection
"""

# Standard library imports
import hmac
import logging
import os
import threading
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

# Third-party imports (Django)
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from requests_oauthlib import OAuth2Session

from horilla.shortcuts import redirect, render
from horilla.urls import reverse, reverse_lazy

# First party imports (Horilla)
from horilla.utils import timezone
from horilla.utils.decorators import method_decorator, permission_required_or_denied
from horilla.utils.translation import gettext_lazy as _
from horilla.web import HttpResponse

# Local imports
from ..forms import GoogleCredentialsUploadForm, GoogleSyncDirectionForm
from ..models import GoogleCalendarConfig, GoogleIntegrationSetting
from .client_settings import GOOGLE_SCOPES
from .service import (
    GOOGLE_API_TIMEOUT,
    create_watch_channel,
    get_google_user_email,
    stop_watch_channel,
)

logger = logging.getLogger(__name__)

_SETTINGS_TEMPLATE = "google_calendar/google_calendar_settings.html"


def _get_or_create_config(user):
    """Get or create a GoogleCalendarConfig for a user.

    Uses all_objects (unfiltered manager) because GoogleCalendarConfig is a
    per-user singleton — one row per user regardless of company. The default
    CompanyFilteredManager would hide the row when an admin switches to a
    different company, causing spurious DoesNotExist / UNIQUE constraint errors.
    """
    try:
        config, _ = GoogleCalendarConfig.all_objects.get_or_create(
            user=user,
            defaults={"company": user.company},
        )
    except IntegrityError:
        # Concurrent request already created the row; just fetch it.
        config = GoogleCalendarConfig.all_objects.get(user=user)
    return config


def _is_integration_enabled(request):
    """Return True if the admin has enabled Google Calendar integration for this company."""
    company = request.user.company
    setting = GoogleIntegrationSetting.all_objects.filter(company=company).first()
    return bool(setting and setting.is_google_calendar_enabled)


class GoogleCalendarSettingsView(LoginRequiredMixin, View):
    """
    My Settings page for Google Calendar.

    GET  — renders the settings template with current status + upload form.
    POST — processes the credentials JSON upload; saves to GoogleCalendarConfig.
    """

    def _render(self, request, form=None, sync_direction_form=None):

        config = _get_or_create_config(request.user)
        # Compute the exact redirect URI the user should register in Google Cloud Console
        suggested_redirect_uri = request.build_absolute_uri(
            reverse_lazy("calendar:google_calendar_callback")
        )
        if form is None:
            form = GoogleCredentialsUploadForm(
                initial={"redirect_uri": config.redirect_uri or suggested_redirect_uri}
            )
        if sync_direction_form is None:
            sync_direction_form = GoogleSyncDirectionForm(instance=config)

        # Derive webhook URL from the current request — works with dev tunnels without SITE_URL.
        webhook_url = request.build_absolute_uri(
            reverse("calendar:google_calendar_webhook")
        )
        can_register_webhook = webhook_url.startswith("https://")
        watch_active = bool(
            config.watch_channel_id
            and config.watch_expiration
            and config.watch_expiration > timezone.now()
        )

        # Lazy webhook renewal: if connected + HTTPS + watch is expired or expiring
        # within 24 hours, silently re-register without needing a scheduler or Celery.
        # This piggybacks on the user opening their settings page.
        if config.is_connected() and can_register_webhook and not watch_active:
            try:
                stop_watch_channel(config)
            except Exception as exc:
                logger.warning(
                    "Failed to stop old watch channel for user %s before renewal: %s",
                    request.user,
                    exc,
                )
            try:
                result = create_watch_channel(config, webhook_url=webhook_url)
                if result:
                    # Re-fetch to pick up the updated watch_expiration
                    config = _get_or_create_config(request.user)
                    watch_active = bool(
                        config.watch_channel_id
                        and config.watch_expiration
                        and config.watch_expiration > timezone.now()
                    )
                    logger.info(
                        "Lazy webhook renewal succeeded for user %s", request.user
                    )
            except Exception as exc:
                logger.warning(
                    "Lazy webhook renewal failed for user %s: %s", request.user, exc
                )

        context = {
            "form": form,
            "sync_direction_form": sync_direction_form,
            "google_config": config,
            "is_configured": config.is_configured(),
            "is_connected": config.is_connected(),
            "suggested_redirect_uri": suggested_redirect_uri,
            "webhook_url": webhook_url,
            "can_register_webhook": can_register_webhook,
            "watch_active": watch_active,
        }
        return render(request, _SETTINGS_TEMPLATE, context)

    def _check_integration_enabled(self, request):
        """
        Return a response blocking access when Google integration is disabled, else None.
        For HTMX requests: HX-Redirect so the full page navigates away instead of
        injecting a bare 403 page into the settings content area.
        For normal requests: standard 403 render.
        """
        if not _is_integration_enabled(request):
            if request.headers.get("HX-Request") == "true":
                messages.error(
                    request, _("Google Calendar integration is not enabled.")
                )
                response = HttpResponse(status=204)
                response["HX-Redirect"] = reverse("core:my_settings_view")
                return response
            return render(
                request,
                "403.html",
                {
                    "message": _(
                        "Google Calendar integration has not been enabled by your administrator."
                    )
                },
                status=403,
            )
        return None

    def get(self, request, *args, **kwargs):
        """Render credentials form and connection status when integration is enabled."""
        blocked = self._check_integration_enabled(request)
        if blocked:
            return blocked
        return self._render(request)

    def post(self, request, *args, **kwargs):
        """Validate and store uploaded Google OAuth client JSON and redirect URI."""
        blocked = self._check_integration_enabled(request)
        if blocked:
            return blocked
        form = GoogleCredentialsUploadForm(request.POST, request.FILES)
        if form.is_valid():
            config = _get_or_create_config(request.user)
            config.credentials_json = form.cleaned_data["credentials_file"]
            config.redirect_uri = form.cleaned_data["redirect_uri"]
            # Reset connection when credentials are re-uploaded
            config.token = {}
            config.google_email = None
            config.google_sync_token = None
            config.oauth_state = None
            config.save()
            messages.success(
                request,
                _(
                    "Google credentials saved. Click 'Connect Google Account' to authorize."
                ),
            )
            return self._render(request)
        return self._render(request, form=form)


class GoogleCalendarAuthorizeView(LoginRequiredMixin, View):
    """
    Redirect the user to Google's OAuth2 consent screen.

    This is a regular browser redirect — NOT an HTMX request — because
    Google's consent screen blocks cross-origin iframe embedding.
    """

    def get(self, request, *args, **kwargs):
        """Redirect to Google consent when credentials JSON is present."""
        config = _get_or_create_config(request.user)

        if not config.is_configured():
            messages.error(
                request,
                _("Please upload your Google OAuth credentials first."),
            )
            return redirect(reverse_lazy("calendar:google_calendar_settings"))

        # Allow HTTP in development (oauthlib rejects non-HTTPS by default)
        if not request.is_secure():
            os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
        # Google normalises scope names on return — suppress the mismatch error
        os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

        # Use the stored redirect_uri; fall back to the auto-computed one so
        # the flow still works even if the user skipped filling in the field.
        redirect_uri = config.redirect_uri or request.build_absolute_uri(
            reverse_lazy("calendar:google_calendar_callback")
        )

        oauth = OAuth2Session(
            client_id=config.get_client_id(),
            redirect_uri=redirect_uri,
            scope=GOOGLE_SCOPES,
        )
        authorization_url, state = oauth.authorization_url(
            config.get_auth_uri(),
            access_type="offline",
            prompt="consent",
        )

        config.oauth_state = state
        config.save(update_fields=["oauth_state"])

        return redirect(authorization_url)


class GoogleCalendarCallbackView(View):
    """
    Handle the OAuth2 callback from Google.

    Validates state, exchanges the code for tokens, fetches the user's
    Google email, saves everything to GoogleCalendarConfig, then redirects
    back to My Settings.

    LoginRequiredMixin is intentionally omitted here: some OAuth flows can
    briefly lose the Django session cookie during the redirect. The user is
    instead identified by matching the state against the database.
    """

    def get(self, request, *args, **kwargs):
        """Finish OAuth: validate state, exchange code, optionally register webhook channel."""
        state = request.GET.get("state")
        code = request.GET.get("code")
        error = request.GET.get("error")

        if error:
            messages.error(
                request,
                _("Google authorization was denied: %(error)s") % {"error": error},
            )
            return redirect(reverse_lazy("core:my_settings_view"))

        if not state or not code:
            messages.error(request, _("Invalid OAuth2 callback parameters."))
            return redirect(reverse_lazy("core:my_settings_view"))

        try:
            config = GoogleCalendarConfig.all_objects.get(oauth_state=state)
        except GoogleCalendarConfig.DoesNotExist:
            messages.error(request, _("OAuth state mismatch. Please try again."))
            return redirect(reverse_lazy("core:my_settings_view"))

        if not request.is_secure():
            os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

        # Build the full callback URL (oauthlib needs the exact URL including code).
        # Do NOT rewrite http→https here — it must match what was sent to Google.
        authorization_response = request.build_absolute_uri()

        # The redirect_uri in fetch_token MUST match what was used in the authorize step
        redirect_uri = config.redirect_uri or request.build_absolute_uri(
            reverse_lazy("calendar:google_calendar_callback")
        )

        oauth = OAuth2Session(
            client_id=config.get_client_id(),
            redirect_uri=redirect_uri,
            state=state,
            scope=GOOGLE_SCOPES,
        )

        try:
            os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
            token = oauth.fetch_token(
                config.get_token_uri(),
                client_secret=config.get_client_secret(),
                authorization_response=authorization_response,
                timeout=GOOGLE_API_TIMEOUT,
            )
        except Exception as exc:
            logger.error(
                "Google token exchange failed for user %s: %s",
                config.user,
                exc,
            )
            messages.error(
                request,
                _("Failed to connect Google Calendar. Please try again."),
            )
            return redirect(reverse_lazy("core:my_settings_view"))

        config.token = token
        config.oauth_state = None  # Clear state after use

        # Fetch the connected Google account email
        try:
            config.google_email = get_google_user_email(config)
        except Exception:
            config.google_email = ""

        config.save()

        # Register a push-notification watch channel so changes arrive within seconds.
        # Derive the webhook URL from the current request so dev tunnels work without SITE_URL.
        # Never let watch failure break the OAuth flow — polling is the fallback.
        try:
            webhook_url = request.build_absolute_uri(
                reverse("calendar:google_calendar_webhook")
            )
            create_watch_channel(config, webhook_url=webhook_url)
        except Exception as exc:
            logger.warning(
                "Failed to create Google watch channel for %s: %s",
                config.user,
                exc,
            )

        messages.success(
            request,
            _("Google Calendar connected as %(email)s.")
            % {"email": config.google_email or "your Google account"},
        )
        return redirect(reverse_lazy("calendar:google_calendar_settings"))


class GoogleCalendarSyncDirectionView(LoginRequiredMixin, View):
    """Save the user's chosen sync direction (one-way or two-way)."""

    def post(self, request, *args, **kwargs):
        """Persist sync direction posted from the radio form."""
        config = _get_or_create_config(request.user)
        form = GoogleSyncDirectionForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, _("Sync direction saved."))
            return GoogleCalendarSettingsView()._render(request)
        return GoogleCalendarSettingsView()._render(request, sync_direction_form=form)


class GoogleCalendarDisconnectView(LoginRequiredMixin, View):
    """Clear the Google OAuth token and reset the connection."""

    def post(self, request, *args, **kwargs):
        """Revoke locally stored tokens, stop watch channels, and re-render settings."""
        if not _is_integration_enabled(request):
            response = HttpResponse(status=204)
            response["HX-Redirect"] = reverse("calendar:google_calendar_settings")
            return response

        config = _get_or_create_config(request.user)

        if not config.is_connected():
            messages.info(request, _("Google Calendar is already disconnected."))
            form = GoogleCredentialsUploadForm(
                initial={"redirect_uri": config.redirect_uri or ""}
            )
            context = {
                "form": form,
                "google_config": config,
                "is_configured": config.is_configured(),
                "is_connected": False,
            }
            return render(request, _SETTINGS_TEMPLATE, context)

        # Stop the push-notification watch channel before clearing credentials.
        try:
            stop_watch_channel(config)
        except Exception as exc:
            logger.warning("stop_watch_channel failed for %s: %s", config.user, exc)

        config.token = {}
        config.google_email = None
        config.google_sync_token = None
        config.oauth_state = None
        config.save()
        messages.success(request, _("Google Calendar disconnected."))
        # Re-render the settings fragment for HTMX swap
        form = GoogleCredentialsUploadForm(
            initial={"redirect_uri": config.redirect_uri or ""}
        )
        context = {
            "form": form,
            "google_config": config,
            "is_configured": config.is_configured(),
            "is_connected": False,
        }
        return render(request, _SETTINGS_TEMPLATE, context)


class GoogleCalendarRegisterWebhookView(LoginRequiredMixin, View):
    """(Re-)register the Google Calendar push-notification watch channel."""

    def post(self, request, *args, **kwargs):
        """Stop any prior channel and create a new push subscription for this user."""
        config = _get_or_create_config(request.user)
        if not config.is_connected():
            messages.error(request, _("Google Calendar is not connected."))
            return GoogleCalendarSettingsView()._render(request)

        # Stop the old channel first so Google doesn't keep sending to a stale one.
        try:
            stop_watch_channel(config)
        except Exception as exc:
            logger.warning("stop_watch_channel failed for %s: %s", config.user, exc)

        try:
            webhook_url = request.build_absolute_uri(
                reverse("calendar:google_calendar_webhook")
            )
            result = create_watch_channel(config, webhook_url=webhook_url)
            if result:
                messages.success(
                    request,
                    _(
                        "Webhook registered. Google Calendar will now push changes automatically."
                    ),
                )
            else:
                messages.error(
                    request,
                    _(
                        "Webhook registration failed: the URL %(url)s is not HTTPS. "
                        "Access the app via an HTTPS URL (e.g. your dev tunnel) and try again."
                    )
                    % {"url": webhook_url},
                )
        except Exception as exc:
            logger.error(
                "create_watch_channel failed for user %s: %s", request.user, exc
            )
            messages.error(
                request,
                _("Failed to register webhook: %(error)s") % {"error": str(exc)},
            )

        return GoogleCalendarSettingsView()._render(request)


def _maybe_renew_watch(config, webhook_url, expiration_ms_str):
    """
    Renew the watch channel if it expires within 24 hours.

    Called from inside the webhook sync thread so renewal happens automatically
    without a scheduler or Celery job.

    expiration_ms_str — X-Goog-Channel-Expiration header value (epoch ms string).
    Falls back to config.watch_expiration if the header is absent or unparseable.
    """

    expiry = None
    if expiration_ms_str:
        try:
            expiry = datetime.fromtimestamp(
                int(expiration_ms_str) / 1000, tz=dt_timezone.utc
            )
        except (ValueError, OSError):
            pass
    if expiry is None:
        expiry = config.watch_expiration

    now = timezone.now()
    if expiry and expiry > now + timedelta(hours=24):
        return  # plenty of time left — nothing to do

    # Expired or expiring within 24 h → renew silently
    logger.info(
        "Auto-renewing watch channel for user %s (expiry=%s)", config.user, expiry
    )
    try:
        stop_watch_channel(config)
    except Exception as exc:
        logger.warning(
            "Failed to stop old watch channel for user %s before auto-renewal: %s",
            config.user,
            exc,
        )
    try:
        create_watch_channel(config, webhook_url=webhook_url)
        logger.info("Auto-renewed watch channel for user %s", config.user)
    except Exception as exc:
        logger.warning("Auto-renewal failed for user %s: %s", config.user, exc)


@method_decorator(csrf_exempt, name="dispatch")
class GoogleCalendarWebhookView(View):
    """
    Receive Google Calendar push notifications.

    Google POSTs to this endpoint whenever a watched calendar changes.
    The body is always empty — all information comes from HTTP headers.

    Security:
    - channel_id is a lookup key only; watch_token is the authenticator.
    - resource_id cross-check prevents replay across channels.
    - Token comparison uses hmac.compare_digest (constant-time).

    No LoginRequiredMixin — this endpoint is called by Google, not a user.
    """

    def post(self, request, *args, **kwargs):
        """Validate push headers, dispatch incremental sync in a background thread."""
        channel_id = request.META.get("HTTP_X_GOOG_CHANNEL_ID", "")
        resource_id = request.META.get("HTTP_X_GOOG_RESOURCE_ID", "")
        resource_state = request.META.get("HTTP_X_GOOG_RESOURCE_STATE", "")
        token = request.META.get("HTTP_X_GOOG_CHANNEL_TOKEN", "")
        message_number = request.META.get("HTTP_X_GOOG_MESSAGE_NUMBER", "?")
        channel_expiration_ms = request.META.get("HTTP_X_GOOG_CHANNEL_EXPIRATION", "")

        logger.debug(
            "Webhook received: channel_id=%r state=%r msg#=%s",
            channel_id,
            resource_state,
            message_number,
        )

        if not channel_id:
            logger.warning("Webhook rejected: no channel_id in headers")
            return HttpResponse(status=404)

        config = GoogleCalendarConfig.all_objects.filter(
            watch_channel_id=channel_id
        ).first()
        if config is None:
            # Expected for channels Horilla already renewed/replaced — Google keeps
            # delivering to the old channel_id until it naturally expires (up to 7
            # days). Not an error on its own; info level avoids log spam while
            # stop_watch_channel failures are now logged where they actually occur.
            logger.info(
                "Webhook rejected: no config found for channel_id=%r (likely a superseded channel)",
                channel_id,
            )
            return HttpResponse(status=404)

        logger.debug("Webhook config found: user=%s", config.user)

        stored_token = config.watch_token or ""
        if stored_token and not hmac.compare_digest(stored_token, token or ""):
            logger.warning("Webhook rejected: token mismatch for user=%s", config.user)
            return HttpResponse(status=401)

        if config.watch_resource_id != resource_id:
            logger.warning(
                "Webhook rejected: resource_id mismatch for user=%s (stored=%r incoming=%r)",
                config.user,
                config.watch_resource_id,
                resource_id,
            )
            return HttpResponse(status=401)

        if resource_state == "sync":
            logger.debug("Webhook handshake received for user=%s", config.user)
            return HttpResponse(status=200)

        if resource_state == "exists":
            logger.info(
                "Webhook: calendar changed for user=%s, dispatching sync", config.user
            )
            config_pk = config.pk
            # Capture webhook URL now (request not available inside the thread)
            webhook_url_for_renewal = request.build_absolute_uri(
                reverse("calendar:google_calendar_webhook")
            )

            def _do_sync():
                from horilla.contrib.activity.models import Activity

                from ..models import GoogleCalendarConfig as _Cfg
                from .sync import pull_google_events_to_horilla as _pull

                try:
                    fresh_config = _Cfg.objects.get(pk=config_pk)
                    logger.info(
                        "Webhook sync: starting pull for user=%s", fresh_config.user
                    )
                    before = Activity.objects.count()
                    # If no sync token exists yet, bootstrap first (captures the
                    # nextSyncToken without importing old history), then do a normal
                    # pull so only the triggering change is imported.
                    # If a sync token already exists, go straight to incremental pull.
                    if not fresh_config.google_sync_token:
                        _pull(fresh_config, initial_sync_only=True)
                        # Re-fetch config so we have the newly saved sync token
                        fresh_config = _Cfg.objects.get(pk=config_pk)
                    _pull(fresh_config)
                    after = Activity.objects.count()
                    logger.info(
                        "Webhook sync: pull done for user=%s (created=%d)",
                        fresh_config.user,
                        after - before,
                    )
                    # Auto-renew watch channel if expiring within 24 h
                    fresh_config = _Cfg.objects.get(pk=config_pk)
                    _maybe_renew_watch(
                        fresh_config, webhook_url_for_renewal, channel_expiration_ms
                    )
                except Exception as exc:
                    logger.error(
                        "Webhook sync error for config pk=%s: %s",
                        config_pk,
                        exc,
                        exc_info=True,
                    )

            t = threading.Thread(target=_do_sync, daemon=True)
            t.start()
            return HttpResponse(status=200)

        # Any other resource_state — acknowledge and ignore
        return HttpResponse(status=200)


_INTEGRATION_SETTINGS_TEMPLATE = "google_calendar/google_integration_settings.html"


@method_decorator(
    permission_required_or_denied("calendar.change_googleintegrationsetting"),
    name="dispatch",
)
class GoogleIntegrationSettingsView(LoginRequiredMixin, View):
    """
    Admin Settings page for Google Integration (Settings → Integrations → Google Integration).

    Allows admins to enable/disable Google Calendar integration for all users in the company.
    GET  — render the toggle page.
    POST — save the toggle and re-render.
    """

    def _get_or_create_setting(self, request):
        company = getattr(request, "active_company", None) or request.user.company
        if not company:
            return None
        setting, _ = GoogleIntegrationSetting.all_objects.get_or_create(company=company)
        return setting

    def get(self, request, *args, **kwargs):
        """Render the company Google integration toggle for admins."""
        setting = self._get_or_create_setting(request)
        return render(
            request,
            _INTEGRATION_SETTINGS_TEMPLATE,
            {"integration_setting": setting},
        )

    def _disconnect_all_company_users(self, company):
        """
        Stop watch channels and clear all OAuth tokens/credentials for every user
        in the company when the admin disables Google Calendar integration.
        """
        configs = GoogleCalendarConfig.objects.filter(company=company)
        for config in configs:
            try:
                if config.watch_channel_id:
                    stop_watch_channel(config)
            except Exception:
                logger.warning(
                    "Failed to stop watch channel for user %s during bulk disconnect.",
                    config.user,
                    exc_info=True,
                )
        configs.update(
            token=None,
            google_email=None,
            google_sync_token=None,
            oauth_state=None,
            credentials_json=None,
            redirect_uri=None,
            watch_channel_id=None,
            watch_resource_id=None,
            watch_expiration=None,
            watch_token=None,
        )

    def post(self, request, *args, **kwargs):
        """Persist admin toggle and optionally disconnect all users in the company."""
        setting = self._get_or_create_setting(request)
        if setting is None:
            messages.error(request, _("No active company found. Cannot save settings."))
            return render(
                request, _INTEGRATION_SETTINGS_TEMPLATE, {"integration_setting": None}
            )
        is_enabled = request.POST.get("is_google_calendar_enabled") == "true"
        setting.is_google_calendar_enabled = is_enabled
        setting.updated_by = request.user
        setting.save()
        if is_enabled:
            messages.success(
                request,
                _("Google Calendar integration has been enabled for users."),
            )
        else:
            self._disconnect_all_company_users(getattr(request, "active_company", None))
            messages.info(
                request,
                _(
                    "Google Calendar integration has been disabled. All user connections have been removed."
                ),
            )
        return render(
            request,
            _INTEGRATION_SETTINGS_TEMPLATE,
            {"integration_setting": setting},
        )
