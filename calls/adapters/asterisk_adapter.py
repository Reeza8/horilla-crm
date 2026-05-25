"""Asterisk / FreePBX adapter for Horilla Calls Integration."""

import hmac
import logging

import requests

from .base import BaseCallAdapter
from .factory import register_adapter

logger = logging.getLogger(__name__)


@register_adapter("asterisk")
class AsteriskAdapter(BaseCallAdapter):
    """
    Adapter for Asterisk / FreePBX via ARI (Asterisk REST Interface).

    Credentials expected on provider:
        api_base_url — ARI base URL, e.g. http://192.168.1.10:8088/ari
        api_key      — ARI username
        api_secret   — ARI password
        caller_id    — default outbound caller ID / trunk number

    Docs: https://wiki.asterisk.org/wiki/display/AST/Asterisk+REST+Interface
    """

    def _auth(self):
        return (self._val("api_key"), self._val("api_secret"))

    def _base_url(self):
        return self.provider.api_base_url.rstrip("/")

    def initiate_call(self, from_number: str, to_number: str, callback_url: str) -> dict:
        """
        Originate a call via ARI /channels endpoint.
        Asterisk dials the agent (from_number) first, then bridges to the customer (to_number).
        """
        url = f"{self._base_url()}/channels"
        payload = {
            "endpoint": f"SIP/{to_number}",
            "callerId": from_number or self.provider.caller_id,
            "app": "horilla_calls",
            "variables": {
                "CALLBACK_URL": callback_url,
                "TO_NUMBER": to_number,
            },
        }
        try:
            resp = requests.post(url, json=payload, auth=self._auth(), timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return {
                "call_id": data.get("id", ""),
                "status": self._map_status(data.get("state", "")),
            }
        except requests.RequestException as exc:
            logger.error("Asterisk initiate_call failed: %s", exc)
            raise

    def validate_webhook(self, request) -> bool:
        """
        Asterisk does not sign webhooks natively.
        If webhook_secret is set, validate it against a shared-secret header or query param.
        """
        secret = self.provider.webhook_secret
        if not secret:
            return True
        provided = (
            request.headers.get("X-Asterisk-Secret")
            or request.GET.get("secret")
            or request.POST.get("secret", "")
        )
        return hmac.compare_digest(provided, secret)

    def parse_webhook_payload(self, request) -> dict:
        """Map Asterisk ARI event JSON to canonical dict."""
        import json
        try:
            data = json.loads(request.body)
        except Exception:
            data = {}

        channel = data.get("channel", {})
        return {
            "call_id": channel.get("id", ""),
            "direction": self._map_direction(channel.get("dialplan", {}).get("context", "")),
            "status": self._map_status(channel.get("state", "")),
            "from_number": channel.get("caller", {}).get("number", ""),
            "to_number": channel.get("connected", {}).get("number", ""),
            "duration": data.get("duration"),
            "recording_url": None,
        }

    def test_connection(self) -> dict:
        """Verify ARI credentials by fetching /asterisk/info."""
        if not self.provider.api_base_url or not self.provider.api_key or not self.provider.api_secret:
            return {"success": False, "error": "API Base URL, API Key, and API Secret are required."}
        url = f"{self._base_url()}/asterisk/info"
        try:
            resp = requests.get(url, auth=self._auth(), timeout=10)
            if resp.status_code == 200:
                return {"success": True}
            return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        except requests.RequestException as exc:
            return {"success": False, "error": str(exc)}

    @staticmethod
    def _map_status(ari_state: str) -> str:
        mapping = {
            "down": "initiated",
            "rsrvd": "initiated",
            "offhook": "initiated",
            "dialing": "ringing",
            "ring": "ringing",
            "ringing": "ringing",
            "up": "in_progress",
            "busy": "busy",
            "dialing_offhook": "ringing",
            "prering": "ringing",
            "hungup": "completed",
        }
        return mapping.get(ari_state.lower(), "initiated")

    @staticmethod
    def _map_direction(context: str) -> str:
        if "inbound" in context.lower() or "from-trunk" in context.lower():
            return "inbound"
        return "outbound"
