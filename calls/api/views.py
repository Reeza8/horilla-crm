"""DRF ViewSets for the Horilla Calls Integration app."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from calls.models import AgentMapping, CallLog, CallProvider

from .serializers import (
    AgentMappingSerializer,
    CallLogSerializer,
    CallProviderSerializer,
)


class CallProviderViewSet(ModelViewSet):
    """CRUD API for call providers."""

    serializer_class = CallProviderSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["provider_type", "status"]

    def get_queryset(self):
        return CallProvider.objects.all()


class AgentMappingViewSet(ModelViewSet):
    """CRUD API for agent mappings."""

    serializer_class = AgentMappingSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["provider", "user", "is_available"]

    def get_queryset(self):
        return AgentMapping.objects.all()


class CallLogViewSet(ModelViewSet):
    """CRUD API for call logs."""

    serializer_class = CallLogSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["direction", "status", "provider", "agent"]

    def get_queryset(self):
        return CallLog.objects.all()
