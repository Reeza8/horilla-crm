"""
Custom permissions for Horilla API
"""

# Third-party imports (Django)
from rest_framework import permissions

# First party imports (Horilla)
from horilla.contrib.generics.views.details import (
    check_record_access,
    check_record_change_access,
    check_record_delete_access,
)


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or admins to edit it
    """

    def has_object_permission(self, request, view, obj):
        """Allow safe methods to all; allow write only to owner (created_by or id) or staff."""
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the owner or admin
        if hasattr(obj, "created_by"):
            return obj.created_by == request.user or request.user.is_staff

        # For user objects
        if hasattr(obj, "id") and hasattr(request.user, "id"):
            return obj.id == request.user.id or request.user.is_staff

        return False


class IsCompanyMember(permissions.BasePermission):
    """
    Custom permission to only allow members of the same company to access objects
    """

    def has_object_permission(self, request, view, obj):
        """Allow access only if object.company matches request.user.company or user is staff."""
        # Check if user belongs to the same company
        if hasattr(obj, "company") and hasattr(request.user, "company"):
            return obj.company == request.user.company or request.user.is_staff

        return False


class HorillaModelPermissions(permissions.BasePermission):
    """
    Enforce the same granular Roles-and-Permissions codenames
    (view/add/change/delete and their _own variants) that the classic
    Horilla views already check via horilla.contrib.generics.views.details,
    so a permission revoked in Settings > Roles and Permissions also takes
    effect on the DRF API, not just the server-rendered pages.
    """

    def has_permission(self, request, view):
        """Gate create (list/retrieve are gated at the queryset/object level)."""
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method != "POST":
            return True
        model = view.get_queryset().model
        app_label = model._meta.app_label
        model_name = model._meta.model_name
        return (
            user.is_superuser
            or user.has_perm(f"{app_label}.add_{model_name}")
            or user.has_perm(f"{app_label}.add_own_{model_name}")
        )

    def has_object_permission(self, request, view, obj):
        """Check view/change/delete (+ _own via OWNER_FIELDS) for a specific object."""
        user = request.user
        if request.method in permissions.SAFE_METHODS:
            return check_record_access(user, obj)
        if request.method == "DELETE":
            return check_record_delete_access(user, obj)
        return check_record_change_access(user, obj)
