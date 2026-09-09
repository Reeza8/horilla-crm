"""
Serializers for horilla_crm.campaigns models
"""

# Third-party imports (other)
from rest_framework import serializers

# First party imports (Horilla)
from horilla.api.mixins import CompanyScopedSerializerMixin
from horilla.contrib.core.api.serializers import HorillaUserSerializer

# Local imports
from horilla_crm.campaigns.models import Campaign


class CampaignSerializer(CompanyScopedSerializerMixin, serializers.ModelSerializer):
    """Serializer for Campaign model"""

    campaign_owner_details = HorillaUserSerializer(
        source="campaign_owner", read_only=True
    )
    parent_campaign_details = serializers.SerializerMethodField()

    class Meta:
        """Meta options for CampaignSerializer."""

        model = Campaign
        fields = "__all__"

    def get_parent_campaign_details(self, obj):
        """Return minimal details about the parent campaign if present"""
        if obj.parent_campaign:
            return {
                "id": obj.parent_campaign.id,
                "campaign_name": obj.parent_campaign.campaign_name,
                "status": obj.parent_campaign.status,
            }
        return None
