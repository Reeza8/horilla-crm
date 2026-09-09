"""
Serializers for dashboard models
"""

# Third-party imports (Django)
from rest_framework import serializers

# First party imports (Horilla)
from horilla.api.mixins import CompanyScopedSerializerMixin
from horilla.contrib.core.api.serializers import HorillaUserSerializer

# Local imports
from ..models import ComponentCriteria, Dashboard, DashboardComponent, DashboardFolder


class DashboardFolderSerializer(
    CompanyScopedSerializerMixin, serializers.ModelSerializer
):
    """Serializer for DashboardFolder model"""

    folder_owner_details = HorillaUserSerializer(source="folder_owner", read_only=True)

    class Meta:
        """Meta class for DashboardFolderSerializer"""

        model = DashboardFolder
        fields = "__all__"


class DashboardSerializer(CompanyScopedSerializerMixin, serializers.ModelSerializer):
    """Serializer for Dashboard model"""

    dashboard_owner_details = HorillaUserSerializer(
        source="dashboard_owner", read_only=True
    )
    folder_details = serializers.SerializerMethodField()

    class Meta:
        """Meta class for DashboardSerializer"""

        model = Dashboard
        fields = "__all__"

    def get_folder_details(self, obj):
        """Return minimal folder details if available"""
        if obj.folder:
            return {
                "id": obj.folder.id,
                "name": obj.folder.name,
            }
        return None


class DashboardComponentSerializer(
    CompanyScopedSerializerMixin, serializers.ModelSerializer
):
    """Serializer for DashboardComponent model"""

    component_owner_details = HorillaUserSerializer(
        source="component_owner", read_only=True
    )
    dashboard_details = serializers.SerializerMethodField()

    class Meta:
        """Meta class for DashboardComponentSerializer"""

        model = DashboardComponent
        fields = "__all__"

    def get_dashboard_details(self, obj):
        """Return minimal dashboard details"""
        if obj.dashboard:
            return {
                "id": obj.dashboard.id,
                "name": obj.dashboard.name,
            }
        return None


class ComponentCriteriaSerializer(
    CompanyScopedSerializerMixin, serializers.ModelSerializer
):
    """Serializer for ComponentCriteria model"""

    component_details = serializers.SerializerMethodField()

    class Meta:
        """Meta class for ComponentCriteriaSerializer"""

        model = ComponentCriteria
        fields = "__all__"

    def get_component_details(self, obj):
        """Return minimal component details."""
        if obj.component:
            return {
                "id": obj.component.id,
                "name": obj.component.name,
                "dashboard_id": obj.component.dashboard_id,
            }
        return None
