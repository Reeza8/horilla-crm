"""
Serializers for keys models
"""

# Third-party imports (Django)
from rest_framework import serializers

# First party imports (Horilla)
from horilla.api.mixins import CompanyScopedSerializerMixin

# Local imports
from ..models import ShortcutKey


class ShortcutKeySerializer(CompanyScopedSerializerMixin, serializers.ModelSerializer):
    """Serializer for ShortcutKey model"""

    class Meta:
        """Meta class for ShortcutKeySerializer"""

        model = ShortcutKey
        fields = "__all__"

    def validate(self, attrs):
        """Force `user` to the requester and enforce unique (user, page)."""
        attrs = super().validate(attrs)
        # A shortcut key is inherently personal -- the classic UI never
        # lets a user set someone else's shortcuts. Without forcing this,
        # `user` is a plain writable FK via `fields = "__all__"`, letting
        # any holder of add_shortcutkey plant/overwrite another user's
        # key bindings (an IDOR, since IsOwnerOrAdmin only checks
        # created_by, which stays the attacker's own id).
        request = self.context.get("request")
        if request is not None and hasattr(request, "user"):
            attrs["user"] = request.user
        # Enforce unique_together (user, page) at the serializer level to avoid 500s
        user = attrs.get("user") or getattr(self.instance, "user", None)
        page = attrs.get("page") or getattr(self.instance, "page", None)

        if user and page:
            qs = ShortcutKey.objects.filter(user=user, page=page)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"page": "ShortcutKey for this user and page already exists."}
                )
        return attrs
