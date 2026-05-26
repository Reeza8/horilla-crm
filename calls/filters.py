"""Filters for the Horilla Calls Integration app."""

# First party imports (Horilla)
from horilla.contrib.generics.filters import HorillaFilterSet

# Local imports
from .models import AgentMapping, CallLog, CallProvider


class CallProviderFilter(HorillaFilterSet):
    """Filter for CallProvider list view."""

    class Meta:
        model = CallProvider
        fields = "__all__"
        exclude = [
            "additional_info",
            "api_key",
            "api_secret",
            "webhook_secret",
            "extra_config",
        ]
        search_fields = ["name", "account_sid", "caller_id"]


class AgentMappingFilter(HorillaFilterSet):
    """Filter for AgentMapping list view."""

    class Meta:
        model = AgentMapping
        fields = "__all__"
        exclude = ["additional_info"]
        search_fields = ["extension", "agent_id"]


class CallLogFilter(HorillaFilterSet):
    """Filter for CallLog list view."""

    class Meta:
        model = CallLog
        fields = "__all__"
        exclude = [
            "additional_info",
            "provider_call_id",
            "recording_url",
            "related_model_name",
            "related_object_id",
        ]
        search_fields = ["from_number", "to_number", "notes"]
