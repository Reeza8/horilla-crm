"""DRF ViewSets for the Horilla Calls Integration app."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from calls.models import AgentMapping, CallLog, CallProvider
from horilla.contrib.core.api.permissions import (
    HorillaModelPermissions,
    IsCompanyMember,
)
from horilla.contrib.generics.views.helpers.queryset_utils import (
    get_queryset_for_module,
)

from .permissions import HasCallsAccess
from .serializers import (
    AgentMappingSerializer,
    CallLogSerializer,
    CallProviderSerializer,
)


class CallProviderViewSet(ModelViewSet):
    """CRUD API for call providers."""

    serializer_class = CallProviderSerializer
    permission_classes = [
        IsAuthenticated,
        IsCompanyMember,
        HasCallsAccess,
        HorillaModelPermissions,
    ]
    filterset_fields = ["provider_type", "status"]
    queryset = CallProvider.objects.all()

    def get_queryset(self):
        """Return call providers visible to the requesting user's permissions."""
        return get_queryset_for_module(self.request.user, CallProvider)


class AgentMappingViewSet(ModelViewSet):
    """CRUD API for agent mappings."""

    serializer_class = AgentMappingSerializer
    permission_classes = [
        IsAuthenticated,
        IsCompanyMember,
        HasCallsAccess,
        HorillaModelPermissions,
    ]
    filterset_fields = ["provider", "user"]
    queryset = AgentMapping.objects.all()

    def get_queryset(self):
        """Return agent mappings visible to the requesting user's permissions."""
        return get_queryset_for_module(self.request.user, AgentMapping)


class CallLogViewSet(ModelViewSet):
    """CRUD API for call logs."""

    serializer_class = CallLogSerializer
    permission_classes = [
        IsAuthenticated,
        IsCompanyMember,
        HasCallsAccess,
        HorillaModelPermissions,
    ]
    filterset_fields = ["direction", "status", "provider", "agent"]
    queryset = CallLog.objects.all()

    def get_queryset(self):
        """Return call logs visible to the requesting user's permissions."""
        return get_queryset_for_module(self.request.user, CallLog)
