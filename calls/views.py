"""Views for the Horilla Calls Integration app."""

# Standard library imports
import logging
import re
from functools import cached_property


# Third-party imports (Django)
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.apps import apps
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse as DjangoHttpResponse
from django.http import JsonResponse
from django.utils import timezone
from django.views import View
from django.views.decorators.csrf import csrf_exempt

# First party imports (Horilla)
from horilla.auth.models import User
from horilla.contrib.core.models import Role
from horilla.contrib.generics.views import (
    HorillaDetailView,
    HorillaListView,
    HorillaNavView,
    HorillaSingleFormView,
    HorillaView,
)
from horilla.contrib.generics.views.delete import HorillaSingleDeleteView
from horilla.http import HttpResponse
from horilla.shortcuts import render
from horilla.urls import reverse, reverse_lazy
from horilla.utils.decorators import htmx_required, method_decorator
from horilla.utils.decorators.wrapper import permission_required_or_denied
from horilla.utils.translation import gettext_lazy as _

# Local imports
from .adapters.factory import get_adapter
from .filters import AgentMappingFilter, CallLogFilter, CallProviderFilter
from .forms import (
    AgentMappingForm,
    CallAccessRolesForm,
    CallAccessUsersForm,
    CallIntegrationSettingForm,
    CallProviderForm,
)
from .models import (
    AgentMapping,
    CallIntegrationSetting,
    CallLog,
    CallProvider,
)
from .registration import _CALLABLE_MODEL_REGISTRY

logger = logging.getLogger(__name__)


# ── Integration Settings ─────────────────────────────────────────────────────


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
        return self._render(request)

    def post(self, request, *args, **kwargs):
        company = request.active_company
        setting = CallIntegrationSetting.get_for_company(company)
        is_enabled = request.POST.get("is_enabled") == "true"
        access_type = request.POST.get("access_type", setting.access_type)
        setting.is_enabled = is_enabled
        setting.access_type = access_type
        setting.save(update_fields=["is_enabled", "access_type"])
        return self._render(request)


# ── Provider Management ───────────────────────────────────────────────────────
@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("calls.view_callprovider"), name="dispatch"
)
class CallProviderListView(LoginRequiredMixin, HorillaListView):
    """Generic list of call providers embedded in the integration settings panel."""

    model = CallProvider
    view_id = "call-provider-list"
    filterset_class = CallProviderFilter
    search_url = reverse_lazy("calls:provider_list")
    main_url = reverse_lazy("calls:integration_settings")
    columns = ["name", "provider_type", "status", "caller_id"]
    table_height_as_class = "h-[calc(100vh_-_620px)] min-h-[180px]"
    bulk_select_option = False
    table_width = False
    full_width_fields = ["notes"]

    actions = [
        {
            "action": "Test Connection",
            "icon": "fa-solid fa-phone",
            "permissions": "calls.view_callprovider",
            "attrs": """
                    hx-post="{get_test_url}"
                    hx-swap="innerHTML"
                """,
        },
        {
            "action": "Edit",
            "src": "assets/icons/edit.svg",
            "img_class": "w-4 h-4",
            "permissions": "call.change_callprovider",
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
            "permissions": "call.delete_callprovider",
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
class CallProviderFormView(LoginRequiredMixin, HorillaSingleFormView):
    """Create / update a call provider (opens in modal)."""

    model = CallProvider
    form_class = CallProviderForm
    form_title = _("Call Provider")
    save_and_new = False

    @cached_property
    def form_url(self):
        """ Return the form action URL, which differs for create vs update based on the presence of 'pk' in the URL or GET parameters."""
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if pk:
            return reverse_lazy(
                "calls:provider_update",
                kwargs={"pk": pk},
            )
        return reverse_lazy("calls:provider_create")


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("calls.delete_callprovider", modal=True),
    name="dispatch",
)
class CallProviderDeleteView(LoginRequiredMixin, HorillaSingleDeleteView):
    """Delete a call provider and re-render the provider list."""

    model = CallProvider

    def get_post_delete_response(self):
        """Return HTMX response to reload shortcut key list after deletion."""
        return HttpResponse("<script>htmx.trigger('#reloadButton','click');</script>")


@method_decorator(htmx_required, name="dispatch")
class CallProviderTestConnectionView(LoginRequiredMixin, View):
    """
    POST /calls/provider-test/<pk>/
    Calls adapter.test_connection() and returns an inline success/error badge
    so the provider card can display live credential health without a page reload.
    """

    def post(self, request, pk, *args, **kwargs):
        provider = CallProvider.objects.filter(pk=pk).first()
        if not provider:
            messages.error(request, _("Provider not found"))
            return HttpResponse()
        try:
            adapter = get_adapter(provider)
            result = adapter.test_connection()
            if result.get("success"):
                messages.success(request, _("Connection successful"))
            else:
                messages.error(request, result.get("error") or _("Connection failed"))
        except Exception as exc:
            messages.error(request, str(exc))
        return HttpResponse(
                    "<script>$('#reloadButton').click();</script>"
                )


# ── Access Control Modals ────────────────────────────────────────────────────


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
        return HttpResponse("<script>closeModal(); location.reload();</script>")


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
        return HttpResponse("<script>closeModal(); location.reload();</script>")


# ── Access Control Detail Modals (read-only lists) ───────────────────────────


@method_decorator(htmx_required, name="dispatch")
class CallAccessRolesDetailView(LoginRequiredMixin, View):
    """Read-only modal listing all roles that currently have call access."""

    def get(self, request, *args, **kwargs):
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
class CallAccessUsersDetailView(LoginRequiredMixin, View):
    """Read-only modal listing all users that currently have call access."""

    def get(self, request, *args, **kwargs):
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
        providers = CallProvider.objects.filter(status=CallProvider.STATUS_ACTIVE)
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
                    "is_available": mapping.is_available if mapping else True,
                }
            )
        return cards

    def get(self, request, *args, **kwargs):
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
            mapping.extension = request.POST.get("extension", "")
            mapping.agent_id = request.POST.get("agent_id", "")
            mapping.is_available = request.POST.get("is_available") == "on"
            mapping.save(update_fields=["extension", "agent_id", "is_available"])
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


# ── Agent Mappings (admin list — still available for admins) ──────────────────


class AgentMappingListView(LoginRequiredMixin, HorillaListView):
    """HTMX list of agent-to-provider mappings (embedded in the settings page)."""

    model = AgentMapping
    view_id = "agent-mapping-list"
    filterset_class = AgentMappingFilter
    search_url = reverse_lazy("calls:agent_list")
    main_url = reverse_lazy("calls:integration_settings")
    columns = ["user", "provider", "extension", "agent_id", "is_available"]


class AgentMappingFormView(LoginRequiredMixin, HorillaSingleFormView):
    """Create / update an agent mapping (opens in modal)."""

    model = AgentMapping
    form_class = AgentMappingForm
    template_name = "calls/agent_form.html"
    new_display_title = _("Map Agent")
    edit_display_title = _("Edit Agent Mapping")

    def form_valid(self, form):
        instance = form.save(commit=False)
        instance.company = self.request.active_company
        instance.save()
        return HttpResponse(
            '<div class="oh-alert-container">'
            '<div class="oh-alert oh-alert--animated oh-alert--success">'
            + str(_("Agent mapping saved."))
            + "</div></div>"
        )


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("calls.delete_agentmapping", modal=True),
    name="dispatch",
)
class AgentMappingDeleteView(LoginRequiredMixin, HorillaSingleDeleteView):
    """Delete an agent mapping."""

    model = AgentMapping

    def get_post_delete_response(self):
        """Return HTMX response to reload shortcut key list after deletion."""
        return HttpResponse("<script>htmx.trigger('#reloadButton','click');</script>")


# ── Call Log Nav + Main View (HorillaView pattern) ────────────────────────────


class CallLogNavView(LoginRequiredMixin, HorillaNavView):
    """
    Navigation bar for the Call Logs main page.
    Provides search, filter, and layout switcher.
    """

    search_url = reverse_lazy("calls:call_log_list")
    main_url = reverse_lazy("calls:call_log_view")
    filterset_class = CallLogFilter
    model_name = "CallLog"
    model_app_label = "calls"
    enable_actions = True


class CallLogView(LoginRequiredMixin, HorillaView):
    """
    Main Call Logs page — renders the nav bar + list layout.
    This is the entry point users see when clicking Call Logs in the menu.
    """

    nav_url = reverse_lazy("calls:call_log_nav")
    list_url = reverse_lazy("calls:call_log_list")


class CallLogListView(LoginRequiredMixin, HorillaListView):
    """HTMX list of call logs."""

    model = CallLog
    view_id = "call-log-list"
    filterset_class = CallLogFilter
    search_url = reverse_lazy("calls:call_log_list")
    main_url = reverse_lazy("calls:call_log_view")
    columns = [
        "direction",
        "from_number",
        "to_number",
        "status",
        "get_duration_display",
        "started_at",
        "provider",
    ]


class CallLogDetailView(LoginRequiredMixin, HorillaDetailView):
    """Detail view for a single call log."""

    model = CallLog
    template_name = "calls/call_log_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["related_object"] = self.object.get_related_object()
        return ctx


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("calls.delete_calllog", modal=True),
    name="dispatch",
)
class CallLogDeleteView(LoginRequiredMixin, HorillaSingleDeleteView):
    """Delete a call log."""

    model = CallLog

    def get_post_delete_response(self):
        """Return HTMX response to reload shortcut key list after deletion."""
        return HttpResponse("<script>htmx.trigger('#reloadButton','click');</script>")


# ── Click-to-Call ──────────────────────────────────────────────────────────────


@method_decorator(htmx_required, name="dispatch")
class ClickToCallView(LoginRequiredMixin, View):
    """
    Initiates an outbound call from a Lead or Contact detail page.

    GET  — renders the click-to-call modal with providers + phone number pre-filled.
    POST — calls adapter.initiate_call(), creates CallLog(status='initiated'),
           returns HTMX success fragment.
    """

    def get(self, request, *args, **kwargs):
        providers = CallProvider.objects.filter(status=CallProvider.STATUS_ACTIVE)
        return render(
            request,
            "calls/click_to_call_modal.html",
            {
                "providers": providers,
                "phone_number": request.GET.get("phone_number", ""),
                "related_model_name": request.GET.get("model_name", ""),
                "related_object_id": request.GET.get("object_id", ""),
            },
        )

    def post(self, request, *args, **kwargs):
        provider_id = request.POST.get("provider_id")
        from_number = request.POST.get("from_number", "")
        to_number = request.POST.get("to_number", "")
        related_model_name = request.POST.get("related_model_name", "")
        related_object_id = request.POST.get("related_object_id") or None

        provider = CallProvider.objects.filter(pk=provider_id).first()
        if not provider:
            return JsonResponse({"error": str(_("Provider not found."))}, status=400)

        company = request.active_company
        related_object_id = self._validate_related_object(
            related_model_name, related_object_id, company
        )
        if related_object_id is None:
            related_model_name = ""

        agent_mapping = AgentMapping.objects.filter(
            provider=provider, user=request.user
        ).first()

        callback_url = request.build_absolute_uri(
            reverse(
                "calls:provider_webhook",
                kwargs={
                    "provider_type": provider.provider_type,
                    "provider_pk": provider.pk,
                },
            )
        )
        twiml_url = (
            request.build_absolute_uri(
                reverse("calls:twilio_twiml", kwargs={"provider_pk": provider.pk})
            )
            if provider.provider_type == "twilio"
            else ""
        )

        try:
            adapter = get_adapter(provider)
            result = adapter.initiate_call(
                from_number, to_number, callback_url, twiml_url=twiml_url
            )
        except Exception as exc:
            logger.error("Click-to-call failed for provider %s: %s", provider, exc)
            return JsonResponse({"error": str(exc)}, status=500)

        call_log = CallLog.objects.create(
            provider=provider,
            agent=agent_mapping,
            direction=CallLog.DIRECTION_OUTBOUND,
            status=result.get("status", CallLog.STATUS_INITIATED),
            from_number=from_number,
            to_number=to_number,
            started_at=timezone.now(),
            provider_call_id=result.get("call_id", ""),
            related_model_name=related_model_name,
            related_object_id=related_object_id,
            company=company,
            created_by=request.user,
        )

        return render(
            request, "calls/click_to_call_success.html", {"call_log": call_log}
        )

    @staticmethod
    def _validate_related_object(model_name, object_id, company):
        """Return object_id only when the object exists and belongs to company.
        Works for any model — no hardcoded app names."""
        if not object_id or not model_name or not company:
            return object_id
        try:
            pk = int(object_id)
        except (TypeError, ValueError):
            return None
        try:
            model_class = ContentType.objects.get(
                model=model_name.lower()
            ).model_class()
            manager = getattr(model_class, "all_objects", model_class.objects)
            qs = (
                manager.filter(pk=pk, company=company)
                if hasattr(model_class, "company")
                else manager.filter(pk=pk)
            )
            return pk if qs.exists() else None
        except Exception:
            pass
        return None


# ── Provider Webhook ───────────────────────────────────────────────────────────


@method_decorator(csrf_exempt, name="dispatch")
class TwilioTwiMLView(View):
    """
    Returns TwiML XML instructing Twilio how to handle the outbound call leg.
    Twilio POSTs here when the call is answered; we reply with <Dial> to bridge
    the call to the destination number.

    This endpoint is CSRF-exempt — Twilio calls it from its servers.
    The To number is validated to contain only phone-safe characters before
    being embedded in the XML response.
    """

    def post(self, request, provider_pk, *args, **kwargs):
        to_raw = request.POST.get("To", "")
        to_safe = re.sub(r"[^\d+\-\(\)\s]", "", to_raw)
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response>"
            f"<Dial>{to_safe}</Dial>"
            "</Response>"
        )
        return DjangoHttpResponse(xml, content_type="text/xml")


@method_decorator(csrf_exempt, name="dispatch")
class ProviderWebhookView(View):
    """
    Receives lifecycle webhook POSTs from telephony providers.
    URL: calls/webhook/<provider_type>/<provider_pk>/

    No LoginRequiredMixin — these are external HTTP POSTs from the provider.
    Validates signature via adapter.validate_webhook() before processing.
    """

    def post(self, request, provider_type, provider_pk, *args, **kwargs):
        provider = CallProvider.all_objects.filter(
            pk=provider_pk, provider_type=provider_type
        ).first()
        if not provider:
            return JsonResponse({"error": "Provider not found"}, status=404)

        try:
            adapter = get_adapter(provider)
        except ValueError as exc:
            logger.error("Webhook for unknown provider type: %s", exc)
            return JsonResponse({"error": str(exc)}, status=400)

        if not adapter.validate_webhook(request):
            logger.warning("Webhook signature invalid for provider %s", provider)
            return JsonResponse({"error": "Invalid signature"}, status=403)

        try:
            payload = adapter.parse_webhook_payload(request)
        except Exception as exc:
            logger.error("Failed to parse webhook payload: %s", exc)
            return JsonResponse({"error": "Invalid payload"}, status=400)

        self._process_payload(provider, payload)
        return JsonResponse({"status": "ok"})

    def _process_payload(self, provider, payload):
        call_id = payload.get("call_id", "")
        status = payload.get("status", CallLog.STATUS_INITIATED)
        direction = payload.get("direction", CallLog.DIRECTION_OUTBOUND)

        call_log = CallLog.all_objects.filter(
            provider=provider, provider_call_id=call_id
        ).first()

        if call_log:
            call_log.status = status
            if payload.get("duration"):
                call_log.duration_seconds = payload["duration"]
            if payload.get("recording_url"):
                call_log.recording_url = payload["recording_url"]
            if status in (
                CallLog.STATUS_COMPLETED,
                CallLog.STATUS_NO_ANSWER,
                CallLog.STATUS_FAILED,
                CallLog.STATUS_CANCELLED,
            ):
                call_log.ended_at = timezone.now()
            call_log.save(
                update_fields=[
                    "status",
                    "duration_seconds",
                    "recording_url",
                    "ended_at",
                ]
            )
        else:
            from_number = payload.get("from_number", "")
            to_number = payload.get("to_number", "")
            related_model_name, related_object_id = self._match_related_object(
                from_number, provider
            )
            call_log = CallLog.all_objects.create(
                provider=provider,
                direction=direction,
                status=status,
                from_number=from_number,
                to_number=to_number,
                provider_call_id=call_id,
                duration_seconds=payload.get("duration"),
                recording_url=payload.get("recording_url"),
                started_at=timezone.now(),
                related_model_name=related_model_name or "",
                related_object_id=related_object_id,
                company=provider.company,
            )

        if (
            direction == CallLog.DIRECTION_INBOUND
            and status == CallLog.STATUS_RINGING
            and call_log.agent is not None
        ):
            self._push_incoming_call(call_log)

    @staticmethod
    def _match_related_object(from_number, provider):
        """Match an inbound number against any registered callable model."""
        normalized = from_number.replace(" ", "").replace("-", "")
        last10 = normalized[-10:] if len(normalized) >= 10 else normalized
        company = provider.company

        for app_label, model_name, phone_field in _CALLABLE_MODEL_REGISTRY:
            try:
                model_class = apps.get_model(app_label, model_name)
                manager = getattr(model_class, "all_objects", model_class.objects)
                obj = manager.filter(
                    company=company, **{f"{phone_field}__endswith": last10}
                ).first()
                if obj:
                    return model_name, obj.pk
            except Exception:
                pass

        return None, None

    @staticmethod
    def _push_incoming_call(call_log):
        try:
            agent_user = call_log.agent.user if call_log.agent else None
            if not agent_user:
                return

            related = call_log.get_related_object()
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"calls_{agent_user.id}",
                {
                    "type": "incoming_call",
                    "from_number": call_log.from_number,
                    "to_number": call_log.to_number,
                    "provider_name": (
                        call_log.provider.name if call_log.provider else ""
                    ),
                    "call_log_id": call_log.pk,
                    "related_name": str(related) if related else None,
                },
            )
        except Exception as exc:
            logger.warning("Failed to push incoming call notification: %s", exc)
