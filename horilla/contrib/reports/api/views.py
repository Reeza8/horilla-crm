"""
API views for horilla.contrib.reports models

This module mirrors core/accounts API patterns including search, filtering,
bulk update, bulk delete, permissions, and documentation.
"""

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

# Third-party imports (Django)
from rest_framework import permissions, viewsets
from rest_framework.decorators import action

from horilla.api.docs import BULK_DELETE_DOCS, BULK_UPDATE_DOCS, SEARCH_FILTER_DOCS
from horilla.api.mixins import BulkOperationsMixin, SearchFilterMixin

# First party imports (Horilla)
from horilla.api.permissions import IsCompanyMember

# Local imports
from ..models import Report, ReportFolder
from .docs import (
    REPORT_CREATE_DOCS,
    REPORT_DETAIL_DOCS,
    REPORT_FOLDER_CREATE_DOCS,
    REPORT_FOLDER_DETAIL_DOCS,
    REPORT_FOLDER_LIST_DOCS,
    REPORT_LIST_DOCS,
)
from .serializers import ReportFolderSerializer, ReportSerializer

# Common Swagger parameter for search
search_param = openapi.Parameter(
    "search",
    openapi.IN_QUERY,
    description="Search term for full-text search across relevant fields",
    type=openapi.TYPE_STRING,
)

# Define common Swagger request bodies for bulk operations
bulk_update_body = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "ids": openapi.Schema(
            type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_INTEGER)
        ),
        "data": openapi.Schema(type=openapi.TYPE_OBJECT, additional_properties=True),
    },
    required=["ids", "data"],
)

bulk_delete_body = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "ids": openapi.Schema(
            type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_INTEGER)
        )
    },
    required=["ids"],
)


class ReportFolderViewSet(
    SearchFilterMixin, BulkOperationsMixin, viewsets.ModelViewSet
):
    """ViewSet for ReportFolder model"""

    queryset = ReportFolder.objects.all()
    serializer_class = ReportFolderSerializer
    permission_classes = [permissions.IsAuthenticated, IsCompanyMember]

    def get_serializer_class(self):
        """Return the serializer class for the view"""
        # Handle Swagger schema generation
        if getattr(self, "swagger_fake_view", False):
            return ReportFolderSerializer
        return super().get_serializer_class()

    # Search across common folder fields
    search_fields = [
        "name",
    ]

    # Filtering on key fields and common core fields
    filterset_fields = [
        "is_favourite",
        "report_folder_owner",
        "parent",
        "company",
        "created_by",
    ]

    @swagger_auto_schema(
        manual_parameters=[search_param],
        operation_description=REPORT_FOLDER_LIST_DOCS + "\n\n" + SEARCH_FILTER_DOCS,
    )
    def list(self, request, *args, **kwargs):
        """List report folders with search and filter capabilities"""
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(operation_description=REPORT_FOLDER_DETAIL_DOCS)
    def retrieve(self, request, *args, **kwargs):
        """Retrieve a specific report folder"""
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(operation_description=REPORT_FOLDER_CREATE_DOCS)
    def create(self, request, *args, **kwargs):
        """Create a new report folder"""
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        request_body=bulk_update_body, operation_description=BULK_UPDATE_DOCS
    )
    @action(detail=False, methods=["post"])
    def bulk_update(self, request):
        """Update multiple report folders in a single request"""
        return super().bulk_update(request)

    @swagger_auto_schema(
        request_body=bulk_delete_body, operation_description=BULK_DELETE_DOCS
    )
    @action(detail=False, methods=["post"])
    def bulk_delete(self, request):
        """Delete multiple report folders in a single request"""
        return super().bulk_delete(request)


class ReportViewSet(SearchFilterMixin, BulkOperationsMixin, viewsets.ModelViewSet):
    """ViewSet for Report model"""

    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    permission_classes = [permissions.IsAuthenticated, IsCompanyMember]

    def get_serializer_class(self):
        """Return the serializer class for the view"""
        # Handle Swagger schema generation
        if getattr(self, "swagger_fake_view", False):
            return ReportSerializer
        return super().get_serializer_class()

    # Search across common report fields
    search_fields = [
        "name",
        "chart_type",
    ]

    # Filtering on key fields and common core fields
    filterset_fields = [
        "report_owner",
        "folder",
        "is_favourite",
        "company",
        "created_by",
        "module",
    ]

    @swagger_auto_schema(
        manual_parameters=[search_param],
        operation_description=REPORT_LIST_DOCS + "\n\n" + SEARCH_FILTER_DOCS,
    )
    def list(self, request, *args, **kwargs):
        """List reports with search and filter capabilities"""
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(operation_description=REPORT_DETAIL_DOCS)
    def retrieve(self, request, *args, **kwargs):
        """Retrieve a specific report"""
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(operation_description=REPORT_CREATE_DOCS)
    def create(self, request, *args, **kwargs):
        """Create a new report"""
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        request_body=bulk_update_body, operation_description=BULK_UPDATE_DOCS
    )
    @action(detail=False, methods=["post"])
    def bulk_update(self, request):
        """Update multiple reports in a single request"""
        return super().bulk_update(request)

    @swagger_auto_schema(
        request_body=bulk_delete_body, operation_description=BULK_DELETE_DOCS
    )
    @action(detail=False, methods=["post"])
    def bulk_delete(self, request):
        """Delete multiple reports in a single request"""
        return super().bulk_delete(request)
