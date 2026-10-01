"""
Serializers for notifications models
"""

# Third-party imports (Django)
from rest_framework import serializers

# First party imports (Horilla)
from horilla.auth.models import User

# Local imports
from ..models import Notification


class NotificationUserSerializer(serializers.ModelSerializer):
    """Minimal user payload for nested notification sender/recipient details."""

    class Meta:
        """Meta class for NotificationUserSerializer"""

        model = User
        fields = ("id", "username", "email", "first_name", "last_name")


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model"""

    sender_details = NotificationUserSerializer(source="sender", read_only=True)
    user_details = NotificationUserSerializer(source="user", read_only=True)

    class Meta:
        """Meta class for NotificationSerializer"""

        model = Notification
        fields = "__all__"

    def validate(self, data):
        """
        Validate notification data
        """
        # Validate message field is not empty
        if "message" in data and not data["message"].strip():
            raise serializers.ValidationError({"message": "Message cannot be empty"})

        # Validate URL format if provided
        if "url" in data and data["url"] and not data["url"].startswith("/"):
            raise serializers.ValidationError(
                {"url": "URL must be a relative path starting with /"}
            )

        return data
