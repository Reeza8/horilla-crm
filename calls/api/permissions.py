"""Custom permissions for the calls integration API."""

from rest_framework import permissions

from calls.models import CallIntegrationSetting


class HasCallsAccess(permissions.BasePermission):
    """Only allow users the company's CallIntegrationSetting grants calls access to."""

    def has_permission(self, request, view):
        """Deny unless the integration is enabled and the user's role/account is allowed."""
        user = request.user
        company = getattr(user, "company", None)
        if not company:
            return False
        return CallIntegrationSetting.user_can_access(user, company)
