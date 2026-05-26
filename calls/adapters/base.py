"""Base adapter interface for telephony providers."""

import abc


def _decrypt(value: str) -> str:
    """Decrypt a value stored via EncryptedCharField. Returns plain text."""
    if not value:
        return value
    try:
        from horilla.contrib.mail.encryption_utils import decrypt_password

        return decrypt_password(value)
    except Exception:
        return value


class BaseCallAdapter(abc.ABC):
    """
    Abstract base class every telephony provider adapter must implement.

    Subclasses handle one provider (Twilio, Exotel, Asterisk, …).
    The CRM service layer only calls methods defined here, so adding a
    new provider means creating a subclass and registering it — no changes
    elsewhere.
    """

    def __init__(self, provider):
        self.provider = provider

    def _val(self, field_name: str) -> str:
        """Return the decrypted value of an EncryptedCharField on the provider."""
        return _decrypt(getattr(self.provider, field_name, "") or "")

    @abc.abstractmethod
    def initiate_call(
        self, from_number: str, to_number: str, callback_url: str, **kwargs
    ) -> dict:
        """
        Start an outbound call.

        Returns a dict with at minimum:
            {"call_id": str, "status": str}
        Raises an exception on failure.
        """

    @abc.abstractmethod
    def validate_webhook(self, request) -> bool:
        """
        Validate the authenticity of an incoming webhook request.

        Returns True if the signature / secret is valid, False otherwise.
        Never raise — return False on any verification failure.
        """

    @abc.abstractmethod
    def parse_webhook_payload(self, request) -> dict:
        """
        Normalise a provider-specific webhook POST into a canonical dict:

        {
            "call_id":       str,
            "direction":     "inbound" | "outbound",
            "status":        str,   # maps to CallLog.STATUS_* constants
            "from_number":   str,
            "to_number":     str,
            "duration":      int | None,
            "recording_url": str | None,
        }
        """

    def test_connection(self) -> dict:
        """
        Verify that the provider credentials are valid and the API is reachable.
        Returns {"success": True} on success or {"success": False, "error": str} on failure.
        Override in each adapter for provider-specific health checks.
        """
        return {
            "success": False,
            "error": "test_connection not implemented for this provider",
        }

    def get_agent_for_user(self, user):
        """Return the AgentMapping for this provider + user, or None."""
        from calls.models import AgentMapping

        return AgentMapping.objects.filter(provider=self.provider, user=user).first()
