"""
Serializers for Horilla Calendar models
"""

# Third-party imports (Django)
from rest_framework import serializers

# First party imports (Horilla)
from horilla.api.mixins import CompanyScopedSerializerMixin
from horilla.contrib.core.api.serializers import HorillaUserSerializer

# Local imports
from ..models import UserAvailability, UserCalendarPreference


class _OwnUserSerializerMixin:
    """
    Forces the writable ``user`` FK to the requesting user, matching the
    classic (non-DRF) UserAvailabilityFormView/calendar preference flow,
    which hides `user` from the form entirely and always sets it to
    self.request.user (horilla/contrib/calendar/views.py:701,724) -- it is
    never editable to point at someone else. Without this, `user` is a
    plain writable FK via `fields = "__all__"`, letting any authenticated
    user with add_* permission create/alter another user's calendar
    preferences or unavailability windows.
    """

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get("request")
        if request is not None and hasattr(request, "user"):
            attrs["user"] = request.user
        return attrs


class UserCalendarPreferenceSerializer(
    _OwnUserSerializerMixin, CompanyScopedSerializerMixin, serializers.ModelSerializer
):
    """Serializer for UserCalendarPreference model"""

    user_details = HorillaUserSerializer(source="user", read_only=True)

    class Meta:
        """Meta class for UserCalendarPreferenceSerializer"""

        model = UserCalendarPreference
        fields = "__all__"


class UserAvailabilitySerializer(
    _OwnUserSerializerMixin, CompanyScopedSerializerMixin, serializers.ModelSerializer
):
    """Serializer for UserAvailability model"""

    user_details = HorillaUserSerializer(source="user", read_only=True)

    class Meta:
        """Meta class for UserAvailabilitySerializer"""

        model = UserAvailability
        fields = "__all__"
