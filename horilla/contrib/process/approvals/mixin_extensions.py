"""Mixin extensions for approvals: hide records with active pending/rejected approvals."""

# First party imports (Horilla)
from horilla.contrib.core.models.base import HorillaContentType
from horilla.extension.mixin import MixinExtension
from horilla.registry.feature import FEATURE_REGISTRY

# Local imports
from .models import ApprovalInstance


def _approval_models():
    return FEATURE_REGISTRY.get("approval_models", [])


class ApprovalListVisibilityExtension(MixinExtension):
    """Exclude records under a pending/rejected approval from module list views."""

    _inherit_mixin = "horilla.contrib.generics.views.list.HorillaListView"

    def get_queryset(self, original, *args, **kwargs):
        queryset = original(*args, **kwargs)
        model = getattr(self, "model", None)
        if not model or model._meta.app_label == "approvals":
            return queryset
        if model not in _approval_models():
            return queryset
        try:
            content_type = HorillaContentType.objects.get_for_model(model)
            pending_object_ids = list(
                ApprovalInstance.objects.filter(
                    content_type=content_type,
                    status__in=["pending", "rejected"],
                    is_active=True,
                ).values_list("object_id", flat=True)
            )
            pending_pks = [int(oid) for oid in pending_object_ids if str(oid).isdigit()]
            return queryset.exclude(pk__in=pending_pks)
        except Exception:
            return queryset
