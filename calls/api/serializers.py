"""DRF serializers for the Horilla Calls Integration app."""

from rest_framework import serializers

from calls.models import AgentMapping, CallLog, CallProvider


class CallProviderSerializer(serializers.ModelSerializer):
    """Serializer for CallProvider — never exposes encrypted credential fields."""

    class Meta:
        model = CallProvider
        exclude = ["api_key", "api_secret", "webhook_secret", "additional_info"]
        read_only_fields = ["created_at", "updated_at", "created_by", "updated_by"]


class AgentMappingSerializer(serializers.ModelSerializer):
    """Serializer for AgentMapping."""

    user_display = serializers.StringRelatedField(source="user", read_only=True)
    provider_display = serializers.StringRelatedField(source="provider", read_only=True)

    class Meta:
        model = AgentMapping
        exclude = ["additional_info"]
        read_only_fields = ["created_at", "updated_at", "created_by", "updated_by"]


class CallLogSerializer(serializers.ModelSerializer):
    """Serializer for CallLog."""

    duration_display = serializers.SerializerMethodField()
    provider_display = serializers.StringRelatedField(source="provider", read_only=True)

    class Meta:
        model = CallLog
        exclude = ["additional_info"]
        read_only_fields = ["created_at", "updated_at", "created_by", "updated_by"]

    def get_duration_display(self, obj):
        return obj.get_duration_display()
