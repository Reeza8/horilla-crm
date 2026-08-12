"""
API views for keys models

This module mirrors the core API architecture, including search,
filtering, bulk update, and bulk delete capabilities.
"""

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

# Third-party imports
from rest_framework import permissions, viewsets

from horilla.api.docs import BULK_DELETE_DOCS, BULK_UPDATE_DOCS, SEARCH_FILTER_DOCS
from horilla.api.mixins import BulkOperationsMixin, SearchFilterMixin

# First party imports (Horilla)
from horilla.api.permissions import HorillaModelPermissions, IsOwnerOrAdmin

# Local imports
from ..models import ShortcutKey
from .serializers import ShortcutKeySerializer

# Define common Swagger parameters for search and filtering, mirroring core
search_param = openapi.Parameter(
    "search",
    openapi.IN_QUERY,
    description="Search term for full-text search across relevant fields",
    type=openapi.TYPE_STRING,
)


class ShortcutKeyViewSet(SearchFilterMixin, BulkOperationsMixin, viewsets.ModelViewSet):
    """ViewSet for ShortcutKey model"""

    queryset = ShortcutKey.objects.all()
    serializer_class = ShortcutKeySerializer
    permission_classes = [
        permissions.IsAuthenticated,
        IsOwnerOrAdmin,
        HorillaModelPermissions,
    ]

    # Enable search and filtering matching core's pattern
    search_fields = ["page", "command", "key"]
    filterset_fields = ["user", "page", "command", "is_active", "company"]

    @swagger_auto_schema(
        manual_parameters=[search_param], operation_description=SEARCH_FILTER_DOCS
    )
    def list(self, request, *args, **kwargs):
        """List shortcut keys with search and filter capabilities"""
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(operation_description=BULK_UPDATE_DOCS)
    def bulk_update(self, request, *args, **kwargs):
        """Update multiple shortcut keys in a single request"""
        return super().bulk_update(request)

    @swagger_auto_schema(operation_description=BULK_DELETE_DOCS)
    def bulk_delete(self, request, *args, **kwargs):
        """Delete multiple shortcut keys in a single request"""
        return super().bulk_delete(request)
