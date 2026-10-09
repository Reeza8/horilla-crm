"""Mixin extensions for approvals: hide records with active pending/rejected approvals."""

# Third-party imports (Django)
from django.contrib import messages

from horilla.contrib.core.models.base import HorillaContentType

# First party imports (Horilla)
from horilla.extension.mixin import MixinExtension
from horilla.registry.feature import FEATURE_REGISTRY
from horilla.utils.translation import gettext_lazy as _
from horilla.web import HttpResponse

# Local imports
from .models import ApprovalInstance


def _approval_models():
    """Return models registered for approval list visibility filtering."""
    return FEATURE_REGISTRY.get("approval_models", [])


class ApprovalListVisibilityExtension(MixinExtension):
    """Exclude records under a pending/rejected approval from module list views."""

    _inherit_mixin = "horilla.contrib.generics.views.list.HorillaListView"

    def get_queryset(self, original, *args, **kwargs):
        """Return the list queryset with pending/rejected approval records excluded."""
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


class ApprovalDetailVisibilityExtension(MixinExtension):
    """
    Block opening the detail view entirely for a record with an active
    pending approval - applies to every HorillaDetailView subclass
    (OpportunityDetailView, LeadDetailView, ...) automatically, the same
    way ApprovalListVisibilityExtension above hides these rows from list
    views, so a user can never land on a view of a record mid-approval by
    following a direct link, a search result, or a "recently viewed" entry
    that bypasses the list's own exclusion.

    Nobody gets an exception for this - not even the pending approver, who
    acts from the Approvals review screen instead, never this detail page.
    """

    _inherit_mixin = "horilla.contrib.generics.views.details.HorillaDetailView"

    def dispatch(self, original, request, *args, **kwargs):
        """Redirect to the list with a message instead of dispatching to the target."""
        # The wrapped dispatch() resolves self.model from model_name/app_label
        # POST/GET params (dynamic detail views, e.g. generic "add field to
        # detail") before using it - mirror that here too, since this layer
        # runs before the original and would otherwise see the class's
        # static default model instead of the one actually being requested.
        model_name = request.POST.get("model_name") or request.GET.get("model_name")
        app_label = request.POST.get("app_label") or request.GET.get("app_label")
        if model_name and app_label:
            from horilla.apps import apps as horilla_apps

            try:
                model = horilla_apps.get_model(
                    app_label=app_label, model_name=model_name
                )
            except Exception:
                model = getattr(self, "model", None)
        else:
            model = getattr(self, "model", None)

        if not model or model._meta.app_label == "approvals":
            return original(request, *args, **kwargs)
        if model not in _approval_models():
            return original(request, *args, **kwargs)

        pk = kwargs.get("pk") or request.GET.get("pk")
        if not pk:
            return original(request, *args, **kwargs)

        try:
            content_type = HorillaContentType.objects.get_for_model(model)
            is_pending = ApprovalInstance.objects.filter(
                content_type=content_type,
                object_id=str(pk),
                status="pending",
                is_active=True,
            ).exists()
        except Exception:
            return original(request, *args, **kwargs)

        if not is_pending:
            return original(request, *args, **kwargs)

        record = model.objects.filter(pk=pk).first()
        record_label = str(record) if record else pk

        messages.info(
            request,
            str(
                _(
                    '%(model)s "%(record)s" is pending approval and cannot '
                    "be viewed until a decision is made."
                )
            )
            % {"model": model._meta.verbose_name, "record": record_label},
        )
        from .view_extensions import _get_list_redirect_url

        fallback = _get_list_redirect_url(request, model._meta.model_name, pk)
        if request.headers.get("HX-Request") == "true":
            response = HttpResponse()
            response["HX-Redirect"] = fallback
            return response
        from horilla.shortcuts import redirect

        return redirect(fallback)
