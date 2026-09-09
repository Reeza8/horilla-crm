"""
Serializers for mail models, consistent with core conventions
"""

# Third-party imports (Django)
from rest_framework import serializers

# First party imports (Horilla)
from horilla.api.mixins import CompanyScopedSerializerMixin
from horilla.contrib.core.models import HorillaContentType

# Local imports
from ..models import (
    HorillaMail,
    HorillaMailAttachment,
    HorillaMailConfiguration,
    HorillaMailTemplate,
)


class HorillaMailConfigurationSerializer(
    CompanyScopedSerializerMixin, serializers.ModelSerializer
):
    """Serializer for HorillaMailConfiguration model"""

    class Meta:
        """Meta class for HorillaMailConfigurationSerializer"""

        model = HorillaMailConfiguration
        fields = "__all__"
        # Secrets must never round-trip to a client: password/client secret
        # are stored via EncryptedCharField, which still hands back ciphertext
        # at the Python level (from_db_value does not decrypt), and
        # token/oauth_state hold live OAuth access/refresh material in
        # plaintext. write_only lets a client set/rotate them without ever
        # reading them back via list/retrieve/create-echo.
        extra_kwargs = {
            "password": {"write_only": True},
            "outlook_client_secret": {"write_only": True},
            "token": {"write_only": True},
            "oauth_state": {"write_only": True},
        }

    def validate(self, attrs):
        """Ensure only one primary mail configuration exists per system."""
        is_primary = attrs.get(
            "is_primary", getattr(self.instance, "is_primary", False)
        )
        if is_primary:
            qs = HorillaMailConfiguration.objects.exclude(
                pk=getattr(self.instance, "pk", None)
            ).filter(is_primary=True)
            if qs.exists():
                raise serializers.ValidationError(
                    {"is_primary": "Another primary mail configuration already exists."}
                )
            # A primary configuration is intentionally system-wide (no
            # company, per HorillaMailConfiguration.clean()), so skip the
            # CompanyScopedSerializerMixin company-forcing for this case
            # rather than calling super().validate(), which would stamp the
            # caller's active company onto what must stay company=None.
            return attrs
        return super().validate(attrs)


class HorillaMailSerializer(CompanyScopedSerializerMixin, serializers.ModelSerializer):
    """Serializer for HorillaMail model"""

    related_model = serializers.CharField(write_only=True, required=False)

    class Meta:
        """Meta class for HorillaMailSerializer"""

        model = HorillaMail
        fields = "__all__"

    def validate(self, attrs):
        """Validate content_type and object_id so the related object exists."""
        attrs = super().validate(attrs)
        content_type = attrs.get("content_type") or getattr(
            self.instance, "content_type", None
        )
        object_id = attrs.get("object_id") or getattr(self.instance, "object_id", None)
        if content_type and object_id is not None:
            try:
                model_class = HorillaContentType.objects.get(
                    pk=content_type.pk
                ).model_class()
                if not model_class.objects.filter(pk=object_id).exists():
                    raise serializers.ValidationError(
                        {
                            "object_id": "Related object does not exist for the given content type."
                        }
                    )
            except HorillaContentType.DoesNotExist as exc:
                raise serializers.ValidationError(
                    {"content_type": "Invalid content type provided."}
                ) from exc
        return attrs


class HorillaMailAttachmentSerializer(
    CompanyScopedSerializerMixin, serializers.ModelSerializer
):
    """Serializer for HorillaMailAttachment model"""

    class Meta:
        """Meta class for HorillaMailAttachmentSerializer"""

        model = HorillaMailAttachment
        fields = "__all__"


class HorillaMailTemplateSerializer(
    CompanyScopedSerializerMixin, serializers.ModelSerializer
):
    """Serializer for HorillaMailTemplate model"""

    class Meta:
        """Meta class for HorillaMailTemplateSerializer"""

        model = HorillaMailTemplate
        fields = "__all__"

    def validate(self, attrs):
        """Enforce unique (title, company) for mail templates."""
        attrs = super().validate(attrs)
        title = attrs.get("title") or getattr(self.instance, "title", None)
        company = attrs.get("company") or getattr(self.instance, "company", None)
        if title and company:
            qs = HorillaMailTemplate.objects.filter(title=title, company=company)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {
                        "title": "Mail template with this title already exists for the company."
                    }
                )
        return attrs
