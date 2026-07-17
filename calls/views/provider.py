"""Views for managing call providers (Twilio, Asterisk, etc.) in the Call Integration Settings."""

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
from django.utils import timezone
from django.views import View
from django.views.decorators.csrf import csrf_exempt

# First party imports (Horilla)
from horilla.contrib.generics.views import HorillaListView, HorillaSingleFormView
from horilla.contrib.generics.views.delete import HorillaSingleDeleteView
from horilla.shortcuts import render
from horilla.urls import reverse_lazy
from horilla.utils.decorators import (
    htmx_required,
    method_decorator,
    permission_required_or_denied,
)
from horilla.utils.translation import gettext_lazy as _
from horilla.web import HttpResponse, JsonResponse, ScriptResponse

# Local imports
from ..adapters.factory import get_adapter
from ..filters import CallProviderFilter
from ..forms import CallProviderForm
from ..models import CallLog, CallProvider
from ..registration import _CALLABLE_MODEL_REGISTRY

logger = logging.getLogger(__name__)


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
    columns = ["name", "provider_type", "status_col", "caller_id"]
    table_height_as_class = "h-[calc(100vh_-_420px)]"
    bulk_select_option = False
    table_width = False

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
@method_decorator(
    permission_required_or_denied(
        ["calls.add_callprovider", "calls.change_callprovider"], modal=True
    ),
    name="dispatch",
)  # noqa: E501
class CallProviderFormView(LoginRequiredMixin, HorillaSingleFormView):
    """Create / update a call provider (opens in modal)."""

    model = CallProvider
    form_class = CallProviderForm
    form_title = _("Call Provider")
    save_and_new = False

    @cached_property
    def form_url(self):
        """Determine the form action URL based on whether we're creating a new provider or editing an existing one."""
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if pk:
            return reverse_lazy("calls:provider_update", kwargs={"pk": pk})
        return reverse_lazy("calls:provider_create")


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("calls.view_callprovider"), name="dispatch"
)
class CallProviderFieldsView(LoginRequiredMixin, View):
    """
    HTMX endpoint — returns OOB swaps for provider-specific form fields.
    Triggered by provider_type select on change and load.
    """

    PROVIDER_FIELDS = {
        CallProvider.PROVIDER_TWILIO: ["account_sid", "webhook_secret"],
        CallProvider.PROVIDER_SIGNALWIRE: [
            "account_sid",
            "api_base_url",
            "webhook_secret",
        ],
        CallProvider.PROVIDER_TELNYX: ["api_key", "webhook_secret"],
        CallProvider.PROVIDER_SINCH: ["account_sid"],
        CallProvider.PROVIDER_EXOTEL: ["account_sid", "api_key"],
        CallProvider.PROVIDER_MOCK: [],
    }

    def get(self, request, *args, **kwargs):
        """Return the form fields relevant to the selected provider type, so they can be swapped in via HTMX."""
        provider_type = request.GET.get("provider_type", "")
        pk = request.GET.get("pk") or request.GET.get("id")
        instance = CallProvider.objects.filter(pk=pk).first() if pk else None
        form = CallProviderForm(instance=instance)
        visible_fields = set(self.PROVIDER_FIELDS.get(provider_type, []))
        return render(
            request,
            "calls/provider_fields_oob.html",
            {
                "form": form,
                "visible_fields": visible_fields,
                "provider_type": provider_type,
            },
        )


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
        return ScriptResponse(reload=True, extra="closeDeleteModeModal();")


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("calls.view_callprovider"), name="dispatch"
)
class CallProviderTestConnectionView(LoginRequiredMixin, View):
    """
    POST /calls/provider-test/<pk>/
    Calls adapter.test_connection() and returns an inline success/error badge
    so the provider card can display live credential health without a page reload.
    """

    def post(self, request, pk, *args, **kwargs):
        """Test the connection for the specified provider and return an HTMX response with the result."""
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
        return ScriptResponse(reload=True)


# ── Provider Status Inline Update ─────────────────────────────────────────────


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("calls.change_callprovider"), name="dispatch"
)
class CallProviderStatusUpdateView(LoginRequiredMixin, View):
    """Inline status update for the provider list — POSTed by the status dropdown."""

    def post(self, request, pk, *args, **kwargs):
        """Update the provider status from the inline dropdown and reload the list."""
        provider = CallProvider.objects.filter(pk=pk).first()
        if not provider:
            return HttpResponse("")
        status = request.POST.get("status", "")
        if status in dict(CallProvider.STATUS_CHOICES):
            provider.status = status
            provider.save(update_fields=["status"])
            messages.success(request, _("Provider status updated successfully."))
        return ScriptResponse(reload=True, msgs=True)


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
        """Receive Twilio's POST when the outbound call is answered, and respond with TwiML to bridge the call to the destination number."""
        to_raw = request.POST.get("To", "")
        to_safe = re.sub(r"[^\d+\-\(\)\s]", "", to_raw)
        provider = CallProvider.all_objects.filter(pk=provider_pk).first()
        record_attrs = ""
        if provider and provider.recording_enabled:
            webhook_url = request.build_absolute_uri(
                reverse_lazy(
                    "calls:provider_webhook",
                    kwargs={
                        "provider_type": provider.provider_type,
                        "provider_pk": provider.pk,
                    },
                )
            )
            record_attrs = (
                f' record="record-from-answer"'
                f' recordingStatusCallback="{webhook_url}"'
                f' recordingStatusCallbackMethod="POST"'
            )
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response>"
            f"<Dial{record_attrs}>{to_safe}</Dial>"
            "</Response>"
        )
        return HttpResponse(xml, content_type="text/xml")


@method_decorator(csrf_exempt, name="dispatch")
class ProviderWebhookView(View):
    """
    Receives lifecycle webhook POSTs from telephony providers.
    URL: calls/webhook/<provider_type>/<provider_pk>/

    No LoginRequiredMixin — these are external HTTP POSTs from the provider.
    Validates signature via adapter.validate_webhook() before processing.
    """

    def post(self, request, provider_type, provider_pk, *args, **kwargs):
        """Receive a lifecycle webhook POST from a provider, validate it, and update/create the corresponding CallLog entry."""
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

        terminal_statuses = (
            CallLog.STATUS_COMPLETED,
            CallLog.STATUS_NO_ANSWER,
            CallLog.STATUS_FAILED,
            CallLog.STATUS_CANCELLED,
        )
        if call_log:
            # Don't downgrade a terminal status (e.g. recording callback arrives after completion).
            if call_log.status not in terminal_statuses:
                call_log.status = status
            if payload.get("duration"):
                call_log.duration_seconds = payload["duration"]
            if payload.get("recording_url"):
                call_log.recording_url = payload["recording_url"]
            if status in terminal_statuses and not call_log.ended_at:
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
