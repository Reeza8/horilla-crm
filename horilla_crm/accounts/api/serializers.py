"""
Serializers for horilla_crm.accounts models
"""

# Third-party imports (other)
from rest_framework import serializers

# First party imports (Horilla)
from horilla.api.mixins import CompanyScopedSerializerMixin
from horilla.contrib.core.api.serializers import HorillaUserSerializer

# Local imports
from horilla_crm.accounts.models import Account, PartnerAccountRelationship


class AccountSerializer(CompanyScopedSerializerMixin, serializers.ModelSerializer):
    """Serializer for Account model"""

    account_owner_details = HorillaUserSerializer(
        source="account_owner", read_only=True
    )
    parent_account_details = serializers.SerializerMethodField()

    class Meta:
        """Meta options for AccountSerializer."""

        model = Account
        fields = "__all__"

    def get_parent_account_details(self, obj):
        """Get parent account details if available"""
        if obj.parent_account:
            return {
                "id": obj.parent_account.id,
                "name": obj.parent_account.name,
                "account_number": obj.parent_account.account_number,
            }
        return None


class PartnerAccountRelationshipSerializer(
    CompanyScopedSerializerMixin, serializers.ModelSerializer
):
    """Serializer for PartnerAccountRelationship model"""

    account_details = AccountSerializer(source="account", read_only=True)
    partner_details = AccountSerializer(source="partner", read_only=True)

    class Meta:
        """Meta options for PartnerAccountRelationshipSerializer."""

        model = PartnerAccountRelationship
        fields = "__all__"
