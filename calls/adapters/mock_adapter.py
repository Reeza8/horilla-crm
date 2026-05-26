"""Mock adapter for Horilla Calls Integration — use for UI/local testing only."""

import logging
import uuid

from .base import BaseCallAdapter
from .factory import register_adapter

logger = logging.getLogger(__name__)


@register_adapter("mock")
class MockAdapter(BaseCallAdapter):
    """
    Fake telephony provider that simulates a successful call without hitting
    any real API. Use this provider during development and UI testing.

    No credentials required — leave all fields blank on the provider form.
    """

    CAPABILITIES = {
        "click_to_call": True,
        "inbound": False,
        "recording": False,
        "webhook_validation": False,
        "sip": False,
    }

    def initiate_call(self, from_number: str, to_number: str, callback_url: str, **kwargs) -> dict:
        if not to_number:
            raise ValueError("A destination phone number is required to place a call.")
        call_id = f"mock_{uuid.uuid4().hex[:12]}"
        logger.info("MockAdapter: simulated call %s → %s (id=%s)", from_number, to_number, call_id)
        return {
            "call_id": call_id,
            "status": "ringing",
        }

    def validate_webhook(self, request) -> bool:
        return True

    def parse_webhook_payload(self, request) -> dict:
        return {
            "call_id": request.POST.get("call_id", ""),
            "direction": request.POST.get("direction", "outbound"),
            "status": request.POST.get("status", "completed"),
            "from_number": request.POST.get("from", ""),
            "to_number": request.POST.get("to", ""),
            "duration": None,
            "recording_url": None,
        }

    def test_connection(self) -> dict:
        return {"success": True}
