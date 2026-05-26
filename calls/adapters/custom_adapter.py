"""Custom / Generic SIP REST adapter for Horilla Calls Integration."""

import hmac
import logging

import requests

from .base import BaseCallAdapter
from .factory import register_adapter

logger = logging.getLogger(__name__)


@register_adapter("custom")
class CustomAdapter(BaseCallAdapter):
    """
    Generic adapter for any SIP provider that exposes a REST API.

    Assumes a simple REST interface — endpoints are constructed from api_base_url.
    Expects these standard endpoints on the remote server:
        POST {api_base_url}/calls          — initiate call
        GET  {api_base_url}/status         — health check

    Credentials expected on provider:
        api_base_url — REST API base URL, e.g. https://sip.yourprovider.com/api/v1
        api_key      — API key or username
        api_secret   — API secret or password (used as Bearer token if api_key is blank)
        caller_id    — default outbound caller ID

    extra_config keys (optional, set via the Extra Configuration JSON field):
        auth_type    — "basic" (default) | "bearer" | "header"
        token_header — header name when auth_type is "header" (default: "X-Api-Key")
        call_endpoint   — override call initiation path (default: "/calls")
        status_endpoint — override health check path (default: "/status")
    """

    def _base_url(self) -> str:
        return self.provider.api_base_url.rstrip("/")

    def _headers(self) -> dict:
        cfg = self.provider.extra_config or {}
        auth_type = cfg.get("auth_type", "basic")

        if auth_type == "bearer":
            return {
                "Authorization": f"Bearer {self._val('api_secret')}",
                "Content-Type": "application/json",
            }
        if auth_type == "header":
            header_name = cfg.get("token_header", "X-Api-Key")
            return {
                header_name: self._val("api_key") or self._val("api_secret"),
                "Content-Type": "application/json",
            }
        return {"Content-Type": "application/json"}

    def _auth(self):
        cfg = self.provider.extra_config or {}
        if cfg.get("auth_type", "basic") == "basic":
            return (self._val("api_key"), self._val("api_secret"))
        return None

    def initiate_call(
        self, from_number: str, to_number: str, callback_url: str
    ) -> dict:
        """
        POST to {api_base_url}/calls with a standard payload.
        The remote server is responsible for dialling and returning a call_id.
        """
        cfg = self.provider.extra_config or {}
        endpoint = cfg.get("call_endpoint", "/calls")
        url = f"{self._base_url()}{endpoint}"
        payload = {
            "from": from_number or self.provider.caller_id,
            "to": to_number,
            "callback_url": callback_url,
        }
        try:
            resp = requests.post(
                url,
                json=payload,
                headers=self._headers(),
                auth=self._auth(),
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "call_id": str(data.get("call_id", data.get("id", ""))),
                "status": self._map_status(data.get("status", "")),
            }
        except requests.RequestException as exc:
            logger.error("Custom adapter initiate_call failed: %s", exc)
            raise

    def validate_webhook(self, request) -> bool:
        """
        Validate webhook using shared secret from webhook_secret field.
        Checks X-Webhook-Secret header, then query param, then POST param.
        """
        secret = self.provider.webhook_secret
        if not secret:
            return True
        provided = (
            request.headers.get("X-Webhook-Secret")
            or request.GET.get("secret")
            or request.POST.get("secret", "")
        )
        return hmac.compare_digest(provided, secret)

    def parse_webhook_payload(self, request) -> dict:
        """
        Parse a generic webhook payload.
        Tries JSON body first, falls back to POST form data.
        Expects keys: call_id, direction, status, from, to, duration, recording_url.
        """
        import json

        try:
            data = json.loads(request.body)
        except Exception:
            data = request.POST

        return {
            "call_id": str(data.get("call_id", data.get("id", ""))),
            "direction": (
                "inbound"
                if str(data.get("direction", "")).lower() == "inbound"
                else "outbound"
            ),
            "status": self._map_status(str(data.get("status", ""))),
            "from_number": data.get("from", data.get("from_number", "")),
            "to_number": data.get("to", data.get("to_number", "")),
            "duration": data.get("duration"),
            "recording_url": data.get("recording_url"),
        }

    def test_connection(self) -> dict:
        """Verify connectivity by calling the status endpoint."""
        if not self.provider.api_base_url:
            return {"success": False, "error": "API Base URL is required."}
        if not self.provider.api_key and not self.provider.api_secret:
            return {"success": False, "error": "API Key or API Secret is required."}
        cfg = self.provider.extra_config or {}
        endpoint = cfg.get("status_endpoint", "/status")
        url = f"{self._base_url()}{endpoint}"
        try:
            resp = requests.get(
                url,
                headers=self._headers(),
                auth=self._auth(),
                timeout=10,
            )
            if resp.status_code in (200, 204):
                return {"success": True}
            return {
                "success": False,
                "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
            }
        except requests.RequestException as exc:
            return {"success": False, "error": str(exc)}

    @staticmethod
    def _map_status(status: str) -> str:
        mapping = {
            "initiated": "initiated",
            "queued": "initiated",
            "ringing": "ringing",
            "in_progress": "in_progress",
            "in-progress": "in_progress",
            "active": "in_progress",
            "answered": "in_progress",
            "completed": "completed",
            "ended": "completed",
            "hangup": "completed",
            "no_answer": "no_answer",
            "no-answer": "no_answer",
            "busy": "busy",
            "failed": "failed",
            "cancelled": "cancelled",
            "canceled": "cancelled",
        }
        return mapping.get(status.lower(), "initiated")
