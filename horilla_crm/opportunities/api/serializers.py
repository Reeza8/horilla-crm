"""
Serializers for horilla_crm.opportunities models
"""

# Third-party imports (other)
from rest_framework import serializers

# First party imports (Horilla)
from horilla.api.mixins import CompanyScopedSerializerMixin
from horilla.contrib.core.api.serializers import HorillaUserSerializer
from horilla.contrib.generics.views.details import check_record_change_access

# Local imports
from horilla_crm.opportunities.models import (
    DefaultOpportunityMember,
    Opportunity,
    OpportunityStage,
    OpportunityTeam,
    OpportunityTeamMember,
)


class OpportunityStageSerializer(
    CompanyScopedSerializerMixin, serializers.ModelSerializer
):
    """Serializer for OpportunityStage model"""

    class Meta:
        """Meta options for OpportunityStageSerializer."""

        model = OpportunityStage
        fields = "__all__"


class OpportunitySerializer(CompanyScopedSerializerMixin, serializers.ModelSerializer):
    """Serializer for Opportunity model"""

    owner_details = HorillaUserSerializer(source="owner", read_only=True)
    stage_details = OpportunityStageSerializer(source="stage", read_only=True)

    class Meta:
        """Meta options for OpportunitySerializer."""

        model = Opportunity
        fields = "__all__"


class OpportunityTeamSerializer(
    CompanyScopedSerializerMixin, serializers.ModelSerializer
):
    """Serializer for OpportunityTeam model"""

    owner_details = HorillaUserSerializer(source="owner", read_only=True)

    class Meta:
        """Meta options for OpportunityTeamSerializer."""

        model = OpportunityTeam
        fields = "__all__"


class OpportunityTeamMemberSerializer(
    CompanyScopedSerializerMixin, serializers.ModelSerializer
):
    """Serializer for OpportunityTeamMember model"""

    user_details = HorillaUserSerializer(source="user", read_only=True)
    opportunity_details = OpportunitySerializer(source="opportunity", read_only=True)

    class Meta:
        """Meta options for OpportunityTeamMemberSerializer."""

        model = OpportunityTeamMember
        fields = "__all__"

    def validate(self, attrs):
        """
        Require the requester to already have change access on the target
        Opportunity before they can add/modify a team-member row.

        opportunity_access="owner" (or "edit") on OpportunityTeamMember
        grants full change/delete rights on the linked Opportunity via
        Opportunity.has_granted_access/TEAM_ACCESS_LEVELS_FOR_ACTION.
        Without this check, a user holding only add_opportunityteammember
        (not change_opportunity/add_opportunity) could self-escalate by
        adding themselves as an "owner"-level member of any opportunity,
        including ones they have no other authorization to touch.
        """
        attrs = super().validate(attrs)
        opportunity = attrs.get("opportunity") or getattr(
            self.instance, "opportunity", None
        )
        request = self.context.get("request")
        if opportunity is not None and request is not None:
            user = request.user
            if not user.is_superuser and not check_record_change_access(
                user, opportunity
            ):
                raise serializers.ValidationError(
                    {
                        "opportunity": "You do not have permission to manage "
                        "team members for this opportunity."
                    }
                )
        return attrs


class DefaultOpportunityMemberSerializer(
    CompanyScopedSerializerMixin, serializers.ModelSerializer
):
    """Serializer for DefaultOpportunityMember model"""

    user_details = HorillaUserSerializer(source="user", read_only=True)
    team_details = OpportunityTeamSerializer(source="team", read_only=True)

    class Meta:
        """Meta options for DefaultOpportunityMemberSerializer."""

        model = DefaultOpportunityMember
        fields = "__all__"
