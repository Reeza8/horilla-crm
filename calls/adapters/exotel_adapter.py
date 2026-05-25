"""Exotel adapter for Horilla Calls Integration."""

import logging

import requests

from .base import BaseCallAdapter
from .factory import register_adapter

logger = logging.getLogger(__name__)

EXOTEL_API_BASE = "https://api.exotel.com/v1/Accounts"


@register_adapter("exotel")
class ExotelAdapter(BaseCallAdapter):
    """
    Adapter for Exotel Voice API.

    Credentials expected on provider:
        account_sid  — Exotel Account SID
        api_key      — Exotel API Key
        api_secret   — Exotel API Token
        caller_id    — Exotel ExoPhone (outbound number)

    Docs: https://developer.exotel.com/api/#calls-create
    """

    def _auth(self):
        return (self._val("api_key"), self._val("api_secret"))

    def _base_url(self):
        return f"{EXOTEL_API_BASE}/{self._val('account_sid')}"

    def initiate_call(self, from_number: str, to_number: str, callback_url: str) -> dict:
        """
        Initiate a call via Exotel Calls API.
        Exotel bridges: agent (From) ← ExoPhone → customer (To).
        """
        url = f"{self._base_url()}/Calls/connect.json"
        payload = {
            "From": from_number,
            "To": to_number,
            "CallerId": self.provider.caller_id,
            "StatusCallback": callback_url,
        }
        try:
            resp = requests.post(url, data=payload, auth=self._auth(), timeout=15)
            resp.raise_for_status()
            data = resp.json()
            call = data.get("Call", {})
            return {
                "call_id": call.get("Sid", ""),
                "status": self._map_status(call.get("Status", "")),
            }
        except requests.RequestException as exc:
            logger.error("Exotel initiate_call failed: %s", exc)
            raise

    def validate_webhook(self, request) -> bool:
        """
        Exotel does not cryptographically sign webhooks by default.
        If webhook_secret is configured, validate shared-secret query param.
        """
        secret = self.provider.webhook_secret
        if not secret:
            return True
        provided = request.GET.get("secret") or request.POST.get("secret", "")
        return provided == secret

    def parse_webhook_payload(self, request) -> dict:
        """Map Exotel POST fields to canonical dict."""
        data = request.POST
        raw_status = data.get("Status", data.get("CallStatus", ""))
        return {
            "call_id": data.get("CallSid", ""),
            "direction": self._map_direction(data.get("Direction", "")),
            "status": self._map_status(raw_status),
            "from_number": data.get("From", ""),
            "to_number": data.get("To", ""),
            "duration": int(data["RecordingDuration"]) if data.get("RecordingDuration") else None,
            "recording_url": data.get("RecordingUrl"),
        }

    def test_connection(self) -> dict:
        """Verify Exotel credentials by fetching the account resource."""
        if not self.provider.account_sid or not self.provider.api_key or not self.provider.api_secret:
            return {"success": False, "error": "Account SID, API Key, and API Secret are required."}
        url = f"{self._base_url()}.json"
        try:
            resp = requests.get(url, auth=self._auth(), timeout=10)
            if resp.status_code == 200:
                return {"success": True}
            return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        except requests.RequestException as exc:
            return {"success": False, "error": str(exc)}

    @staticmethod
    def _map_status(exotel_status: str) -> str:
        mapping = {
            "queued": "initiated",
            "ringing": "ringing",
            "in-progress": "in_progress",
            "completed": "completed",
            "busy": "busy",
            "failed": "failed",
            "no-answer": "no_answer",
            "canceled": "cancelled",
        }
        return mapping.get(exotel_status.lower(), "initiated")

    @staticmethod
    def _map_direction(exotel_dir: str) -> str:
        if "inbound" in exotel_dir.lower():
            return "inbound"
        return "outbound"
