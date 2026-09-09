"""
Serializers for horilla_crm.forecast models
"""

# Third-party imports (other)
from rest_framework import serializers

# First party imports (Horilla)
from horilla.api.mixins import CompanyScopedSerializerMixin
from horilla.contrib.core.api.serializers import HorillaUserSerializer

# Local imports
from horilla_crm.forecast.models import (
    Forecast,
    ForecastTarget,
    ForecastTargetUser,
    ForecastType,
)


class ForecastTypeSerializer(CompanyScopedSerializerMixin, serializers.ModelSerializer):
    """Serializer for ForecastType model"""

    class Meta:
        """Meta options for ForecastTypeSerializer."""

        model = ForecastType
        fields = "__all__"


class ForecastSerializer(CompanyScopedSerializerMixin, serializers.ModelSerializer):
    """Serializer for Forecast model"""

    owner_details = HorillaUserSerializer(source="owner", read_only=True)
    forecast_type_details = ForecastTypeSerializer(
        source="forecast_type", read_only=True
    )
    closed_deals_count = serializers.IntegerField(read_only=True)

    class Meta:
        """Meta options for ForecastSerializer."""

        model = Forecast
        fields = "__all__"
        # All target/pipeline/best_case/commit/closed/actual amount and
        # quantity fields are roll-ups recomputed from ForecastTarget and
        # linked Opportunity data (see forecast/utils.py and the
        # recalculate_forecasts management command) -- never data a client
        # should set directly. status/approved_by/approved_at/submitted_at
        # represent a draft->submitted->approved workflow with no
        # transition endpoint in this API; leaving them writable let any
        # holder of change_own_forecast approve their own forecast outright.
        read_only_fields = [
            "target_amount",
            "pipeline_amount",
            "best_case_amount",
            "commit_amount",
            "closed_amount",
            "actual_amount",
            "target_quantity",
            "pipeline_quantity",
            "best_case_quantity",
            "commit_quantity",
            "closed_quantity",
            "actual_quantity",
            "status",
            "submitted_at",
            "approved_at",
            "approved_by",
        ]


class ForecastTargetSerializer(
    CompanyScopedSerializerMixin, serializers.ModelSerializer
):
    """Serializer for ForecastTarget model"""

    assigned_to_details = HorillaUserSerializer(source="assigned_to", read_only=True)
    forcasts_type_details = ForecastTypeSerializer(
        source="forcasts_type", read_only=True
    )

    class Meta:
        """Meta options for ForecastTargetSerializer."""

        model = ForecastTarget
        fields = "__all__"
        # current_amount is documented on the model as "auto-calculated"
        # (achievement tracking derived from closed deals) -- target_amount
        # itself (the manager-set goal) stays writable.
        read_only_fields = ["current_amount"]


class ForecastTargetUserSerializer(
    CompanyScopedSerializerMixin, serializers.ModelSerializer
):
    """Serializer for ForecastTargetUser model"""

    user_details = HorillaUserSerializer(source="user", read_only=True)
    forecast_target_details = ForecastTargetSerializer(
        source="forecast_target", read_only=True
    )

    class Meta:
        """Meta options for ForecastTargetUserSerializer."""

        model = ForecastTargetUser
        fields = "__all__"
        # current_revenue/current_quantity are auto-calculated achievement
        # tracking -- revenue_target/quantity_target (the assigned goals)
        # stay writable.
        read_only_fields = ["current_revenue", "current_quantity"]
