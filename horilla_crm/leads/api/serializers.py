"""
Serializers for horilla_crm.leads models
"""

# Third-party imports (other)
from rest_framework import serializers

# First party imports (Horilla)
from horilla.api.mixins import CompanyScopedSerializerMixin

# Local imports
from horilla_crm.leads.models import Lead, LeadStatus


class LeadSerializer(CompanyScopedSerializerMixin, serializers.ModelSerializer):
    """Serializer for Lead model"""

    class Meta:
        """Meta options for LeadSerializer."""

        model = Lead
        fields = "__all__"


class LeadStatusSerializer(CompanyScopedSerializerMixin, serializers.ModelSerializer):
    """Serializer for LeadStatus model"""

    class Meta:
        """Meta options for LeadStatusSerializer."""

        model = LeadStatus
        fields = "__all__"
