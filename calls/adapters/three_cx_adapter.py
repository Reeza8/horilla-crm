"""3CX adapter for Horilla Calls Integration."""

import hmac
import logging

import requests

from .base import BaseCallAdapter
from .factory import register_adapter

logger = logging.getLogger(__name__)


@register_adapter("three_cx")
class ThreeCXAdapter(BaseCallAdapter):
    """
    Adapter for 3CX Phone System via the 3CX Call Control API.

    Credentials expected on provider:
        api_base_url — 3CX web server URL, e.g. https://company.3cx.us:5001
        api_key      — 3CX API client ID (from Admin → Integrations → CRM)
        api_secret   — 3CX API client secret
        caller_id    — outbound DID / extension number

    Docs: https://www.3cx.com/docs/call-control-api/
    """

    _token_cache: dict = {}

    def _base_url(self):
        return self.provider.api_base_url.rstrip("/")

    def _get_token(self) -> str:
        """Fetch a Bearer token via OAuth2 client_credentials grant."""
        cache_key = self.provider.pk
        cached = self._token_cache.get(cache_key)
        if cached:
            return cached

        url = f"{self._base_url()}/connect/token"
        resp = requests.post(
            url,
            data={
                "grant_type": "client_credentials",
                "client_id": self._val("api_key"),
                "client_secret": self._val("api_secret"),
            },
            timeout=10,
        )
        resp.raise_for_status()
        token = resp.json().get("access_token", "")
        self._token_cache[cache_key] = token
        return token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._get_token()}", "Content-Type": "application/json"}

    def initiate_call(self, from_number: str, to_number: str, callback_url: str, **kwargs) -> dict:
        """
        Originate a call via 3CX Call Control API /callcontrol/makecall.
        """
        url = f"{self._base_url()}/callcontrol/makecall"
        payload = {
            "from": from_number or self.provider.caller_id,
            "to": to_number,
        }
        try:
            resp = requests.post(url, json=payload, headers=self._headers(), timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return {
                "call_id": str(data.get("callId", data.get("id", ""))),
                "status": "initiated",
            }
        except requests.RequestException as exc:
            logger.error("3CX initiate_call failed: %s", exc)
            raise

    def validate_webhook(self, request) -> bool:
        """
        3CX webhooks can carry a shared secret as a header or query param.
        If webhook_secret is not set, allow all.
        """
        secret = self.provider.webhook_secret
        if not secret:
            return True
        provided = (
            request.headers.get("X-3CX-Secret")
            or request.GET.get("secret")
            or request.POST.get("secret", "")
        )
        return hmac.compare_digest(provided, secret)

    def parse_webhook_payload(self, request) -> dict:
        """Map 3CX webhook JSON to canonical dict."""
        import json
        try:
            data = json.loads(request.body)
        except Exception:
            data = {}

        return {
            "call_id": str(data.get("callId", data.get("id", ""))),
            "direction": "inbound" if data.get("inbound") else "outbound",
            "status": self._map_status(data.get("status", data.get("callStatus", ""))),
            "from_number": data.get("from", data.get("caller", "")),
            "to_number": data.get("to", data.get("callee", "")),
            "duration": data.get("duration") or data.get("talkDuration"),
            "recording_url": data.get("recordingUrl"),
        }

    def test_connection(self) -> dict:
        """Verify 3CX credentials by fetching /callcontrol/status."""
        if not self.provider.api_base_url or not self.provider.api_key or not self.provider.api_secret:
            return {"success": False, "error": "API Base URL, API Key, and API Secret are required."}
        try:
            token = self._get_token()
            if not token:
                return {"success": False, "error": "Failed to obtain access token."}
            url = f"{self._base_url()}/callcontrol/status"
            resp = requests.get(url, headers=self._headers(), timeout=10)
            if resp.status_code in (200, 204):
                return {"success": True}
            return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        except requests.RequestException as exc:
            return {"success": False, "error": str(exc)}

    @staticmethod
    def _map_status(status: str) -> str:
        mapping = {
            "idle": "initiated",
            "ringing": "ringing",
            "dialing": "ringing",
            "talking": "in_progress",
            "connected": "in_progress",
            "ended": "completed",
            "completed": "completed",
            "busy": "busy",
            "failed": "failed",
            "noanswer": "no_answer",
            "no_answer": "no_answer",
            "cancelled": "cancelled",
        }
        return mapping.get(status.lower(), "initiated")
