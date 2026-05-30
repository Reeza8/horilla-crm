"""Views for the Horilla Calls Integration app."""

# Standard library imports
import logging

# Third-party imports (Django)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View

# First party imports (Horilla)
from horilla.auth.models import User
from horilla.contrib.core.models import Role
from horilla.contrib.generics.views import HorillaSingleFormView
from horilla.contrib.generics.views.core import HorillaTabView
from horilla.http import HttpResponse
from horilla.shortcuts import render
from horilla.urls import reverse, reverse_lazy
from horilla.utils.decorators import (
    htmx_required,
    method_decorator,
    permission_required_or_denied,
)
from horilla.utils.translation import gettext_lazy as _

# Local imports
from ..forms import CallAccessRolesForm, CallAccessUsersForm, CallIntegrationSettingForm
from ..models import AgentMapping, CallIntegrationSetting, CallProvider

logger = logging.getLogger(__name__)


@method_decorator(
    permission_required_or_denied("calls.view_callintegrationsetting"), name="dispatch"
)
class CallIntegrationSettingsView(LoginRequiredMixin, View):
    """
    Admin settings page — enable/disable call integration and manage providers.
    Renders under Settings → Integrations, extending settings/settings.html.
    """

    template_name = "calls/integration_settings.html"

    def _render(self, request):
        company = request.active_company
        setting = CallIntegrationSetting.get_for_company(company) if company else None
        all_roles = (
            Role.objects.filter(company=company) if company else Role.objects.none()
        )
        all_users = (
            User.objects.filter(company=company, is_active=True)
            if company
            else User.objects.none()
        )
        selected_role_ids = (
            list(setting.allowed_roles.values_list("pk", flat=True)) if setting else []
        )
        selected_user_ids = (
            list(setting.allowed_users.values_list("pk", flat=True)) if setting else []
        )
        access_type = setting.access_type if setting else "all"
        return render(
            request,
            self.template_name,
            {
                "setting": setting,
                "form": CallIntegrationSettingForm(instance=setting),
                "all_roles": all_roles,
                "all_users": all_users,
                "selected_role_ids": selected_role_ids,
                "selected_user_ids": selected_user_ids,
                "access_all": access_type == "all",
                "access_roles": access_type == "roles",
                "access_users": access_type == "users",
            },
        )

    def get(self, request, *args, **kwargs):
        """Render the main settings page with the current setting values."""
        return self._render(request)

    def post(self, request, *args, **kwargs):
        """Handle form submission to update the main Call Integration settings (enabled + access type)."""
        company = request.active_company
        setting = CallIntegrationSetting.get_for_company(company)
        is_enabled = request.POST.get("is_enabled") == "true"
        access_type = request.POST.get("access_type", setting.access_type)
        setting.is_enabled = is_enabled
        setting.access_type = access_type
        setting.save(update_fields=["is_enabled", "access_type"])
        return self._render(request)


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("calls.view_callintegrationsetting"), name="dispatch"
)
class CallSettingsTabView(LoginRequiredMixin, HorillaTabView):
    """Tab bar for the Call Integration settings page (Access Control / Providers)."""

    view_id = "call-settings-tab"
    tab_class = "h-[calc(100vh-300px)] overflow-hidden"

    def setup(self, request, *args, **kwargs):
        """Define the tabs for the settings page."""
        super().setup(request, *args, **kwargs)
        self.tabs = [
            {
                "title": _("Access Control"),
                "url": reverse_lazy("calls:settings_access_control"),
                "id": "access-control",
            },
            {
                "title": _("Providers"),
                "url": reverse_lazy("calls:settings_providers"),
                "id": "providers",
            },
        ]


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("calls.view_callintegrationsetting"), name="dispatch"
)
class CallAccessControlTabContent(LoginRequiredMixin, View):
    """HTMX content for the Access Control tab inside Call Integration settings."""

    template_name = "calls/tab_access_control.html"

    def get(self, request, *args, **kwargs):
        """Render the Access Control tab with the current setting values."""
        company = request.active_company
        setting = CallIntegrationSetting.get_for_company(company) if company else None
        selected_role_ids = (
            list(setting.allowed_roles.values_list("pk", flat=True)) if setting else []
        )
        selected_user_ids = (
            list(setting.allowed_users.values_list("pk", flat=True)) if setting else []
        )
        access_type = setting.access_type if setting else "all"
        return render(
            request,
            self.template_name,
            {
                "setting": setting,
                "selected_role_ids": selected_role_ids,
                "selected_user_ids": selected_user_ids,
                "access_all": access_type == "all",
                "access_roles": access_type == "roles",
                "access_users": access_type == "users",
            },
        )


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("calls.view_callprovider"), name="dispatch"
)
class CallProvidersTabContent(LoginRequiredMixin, View):
    """HTMX wrapper for the Providers tab — renders help guide + Add button + provider list."""

    template_name = "calls/tab_providers.html"

    def get(self, request, *args, **kwargs):
        """Render the Providers tab with the list of existing providers and the Add Provider button."""
        return render(request, self.template_name)


# ── Access Control Modals ────────────────────────────────────────────────────


@method_decorator(htmx_required, name="dispatch")
class CallAccessRolesView(LoginRequiredMixin, HorillaSingleFormView):
    """Modal: select which roles can access call integration."""

    model = CallIntegrationSetting
    form_class = CallAccessRolesForm
    form_title = _("Select Roles")
    form_url = reverse_lazy("calls:call_access_roles")
    full_width_fields = ["allowed_roles"]
    modal_height = False
    save_and_new = False

    def get_form(self, form_class=None):
        """Override to limit the allowed_roles queryset to roles from this company and set initial values."""
        company = self.request.active_company
        setting = CallIntegrationSetting.get_for_company(company)
        form = super().get_form(form_class)
        form.fields["allowed_roles"].queryset = Role.objects.filter(company=company)
        form.fields["allowed_roles"].initial = setting.allowed_roles.all()
        return form

    def form_valid(self, form):
        company = self.request.active_company
        setting = CallIntegrationSetting.get_for_company(company)
        setting.access_type = "roles"
        setting.save(update_fields=["access_type"])
        setting.allowed_roles.set(form.cleaned_data["allowed_roles"])
        return HttpResponse("<script>$('#reloadButton').click();closeModal();</script>")


@method_decorator(htmx_required, name="dispatch")
class CallAccessUsersView(LoginRequiredMixin, HorillaSingleFormView):
    """Modal: select which users can access call integration."""

    model = CallIntegrationSetting
    form_class = CallAccessUsersForm
    form_title = _("Select Users")
    form_url = reverse_lazy("calls:call_access_users")
    full_width_fields = ["allowed_users"]
    modal_height = False
    save_and_new = False

    def get_form(self, form_class=None):
        """Override to limit the allowed_users queryset to active users from this company and set initial values."""
        company = self.request.active_company
        setting = CallIntegrationSetting.get_for_company(company)
        form = super().get_form(form_class)
        form.fields["allowed_users"].queryset = User.objects.filter(
            company=company, is_active=True
        )
        form.fields["allowed_users"].initial = setting.allowed_users.all()
        return form

    def form_valid(self, form):
        company = self.request.active_company
        setting = CallIntegrationSetting.get_for_company(company)
        setting.access_type = "users"
        setting.save(update_fields=["access_type"])
        setting.allowed_users.set(form.cleaned_data["allowed_users"])
        return HttpResponse("<script>$('#reloadButton').click();closeModal();</script>")


# ── Access Control Detail Modals (read-only lists) ───────────────────────────


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("calls.view_callintegrationsetting"), name="dispatch"
)
class CallAccessRolesDetailView(LoginRequiredMixin, View):
    """Read-only modal listing all roles that currently have call access."""

    def get(self, request, *args, **kwargs):
        """Render a read-only list of roles that currently have call access, with a link to the edit modal."""
        company = request.active_company
        setting = CallIntegrationSetting.get_for_company(company)
        roles = setting.allowed_roles.all() if setting else []
        return render(
            request,
            "calls/access_detail_modal.html",
            {
                "title": _("Roles with Call Access"),
                "items": [{"name": r.role_name} for r in roles],
                "empty_msg": _("No roles selected yet."),
                "edit_url": reverse("calls:call_access_roles"),
            },
        )


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("calls.view_callintegrationsetting"), name="dispatch"
)
class CallAccessUsersDetailView(LoginRequiredMixin, View):
    """Read-only modal listing all users that currently have call access."""

    def get(self, request, *args, **kwargs):
        """Render a read-only list of users that currently have call access, with a link to the edit modal."""
        company = request.active_company
        setting = CallIntegrationSetting.get_for_company(company)
        users = setting.allowed_users.all() if setting else []
        return render(
            request,
            "calls/access_detail_modal.html",
            {
                "title": _("Users with Call Access"),
                "items": [
                    {
                        "name": u.get_full_name() or u.username,
                        "initials": (
                            (u.first_name[:1] + u.last_name[:1]).upper()
                            if u.first_name
                            else u.username[:2].upper()
                        ),
                    }
                    for u in users
                ],
                "empty_msg": _("No users selected yet."),
                "edit_url": reverse("calls:call_access_users"),
            },
        )


# ── User Settings (My Settings → Calls) ──────────────────────────────────────


class CallUserSettingsView(LoginRequiredMixin, View):
    """
    Per-user Calls settings — shown in My Settings → Calls.
    Each user sees one card per active provider and can save their own
    extension / agent ID for that provider.
    """

    template_name = "calls/calls_user_settings.html"

    def _get_user_cards(self, request):
        """Build a list of provider cards with this user's current AgentMapping for each."""
        providers = CallProvider.objects.filter(
            status=CallProvider.STATUS_ACTIVE
        ).exclude(provider_type=CallProvider.PROVIDER_MOCK)
        cards = []
        for provider in providers:
            mapping = AgentMapping.objects.filter(
                provider=provider, user=request.user
            ).first()
            cards.append(
                {
                    "provider": provider,
                    "mapping": mapping,
                    "extension": mapping.extension if mapping else "",
                    "agent_id": mapping.agent_id if mapping else "",
                }
            )
        return cards

    def get(self, request, *args, **kwargs):
        """Render the user's settings page with a card for each active provider, showing their current extension/agent ID if set."""
        company = request.active_company
        has_access = (
            CallIntegrationSetting.user_can_access(request.user, company)
            if company
            else False
        )
        return render(
            request,
            self.template_name,
            {
                "has_access": has_access,
                "provider_cards": self._get_user_cards(request) if has_access else [],
            },
        )

    def post(self, request, *args, **kwargs):
        """Handle saving/updating the user's AgentMapping for a given provider based on the submitted form data."""
        provider_id = request.POST.get("provider_id")
        action = request.POST.get("action", "save")
        provider = CallProvider.objects.filter(pk=provider_id).first()

        if not provider:
            return self.get(request, *args, **kwargs)

        company = request.active_company
        if action == "save":
            mapping, _ = AgentMapping.all_objects.get_or_create(
                provider=provider,
                user=request.user,
                defaults={"company": company, "created_by": request.user},
            )
            mapping.agent_id = request.POST.get("agent_id", "")
            mapping.save(update_fields=["agent_id"])
        elif action == "remove":
            AgentMapping.objects.filter(provider=provider, user=request.user).delete()

        has_access = (
            CallIntegrationSetting.user_can_access(request.user, company)
            if company
            else False
        )
        return render(
            request,
            self.template_name,
            {
                "has_access": has_access,
                "provider_cards": self._get_user_cards(request) if has_access else [],
            },
        )
