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
        """
        Gate list/create/bulk actions.

        Retrieve/update/destroy are gated at the object level via
        has_object_permission. list requires view/view_own so anonymous-of-
        permission users cannot enumerate records they could never open
        individually; bulk_update/bulk_delete require the actual
        change/delete (or _own) codenames rather than add, since they are
        registered as POST actions.
        """
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True

        model = view.get_queryset().model
        app_label = model._meta.app_label
        model_name = model._meta.model_name

        def has_any(action: str) -> bool:
            return user.has_perm(f"{app_label}.{action}_{model_name}") or user.has_perm(
                f"{app_label}.{action}_own_{model_name}"
            )

        action = getattr(view, "action", None)
        # list_actions (set on ViewSets alongside scope_list_to_view_permission,
        # see SearchFilterMixin.get_queryset) marks every custom @action that
        # returns a bare collection of objects via get_queryset() rather than
        # a single get_object()-checked instance -- e.g. Activity's
        # by_owner/by_assigned/upcoming/etc. Without gating these the same
        # as "list", they fall through to the final `return True` below and
        # leak every row to any authenticated user regardless of view/view_own.
        list_like_actions = set(getattr(view, "list_actions", ())) | {"list"}
        if action in list_like_actions:
            return has_any("view")
        # change_actions/delete_actions let a ViewSet opt a custom @action
        # (e.g. LeadStatusViewSet.reorder, which writes to many rows via a
        # raw queryset the same way bulk_update does) into the same
        # change/delete gating as bulk_update/bulk_delete, instead of
        # falling through to the generic "any POST just needs add" rule
        # below -- reorder only ever mutates existing rows, so add_* is the
        # wrong permission to check for it.
        change_like_actions = {"bulk_update"} | set(getattr(view, "change_actions", ()))
        delete_like_actions = {"bulk_delete"} | set(getattr(view, "delete_actions", ()))
        if action in change_like_actions:
            return has_any("change")
        if action in delete_like_actions:
            return has_any("delete")
        if request.method == "POST":
            return has_any("add")
        return True

    def has_object_permission(self, request, view, obj):
        """Check view/change/delete (+ _own via OWNER_FIELDS) for a specific object."""
        user = request.user
        if request.method in permissions.SAFE_METHODS:
            return check_record_access(user, obj)
        if request.method == "DELETE":
            return check_record_delete_access(user, obj)
        return check_record_change_access(user, obj)
