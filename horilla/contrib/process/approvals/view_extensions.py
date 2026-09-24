"""
``_inherit_view`` extension so bulk "Edit Details" saves respect the approval
pending-edit guard the way the old single-field inline editor did.

``UpdateAllFieldsView`` (the bulk-edit save endpoint) is a single, concrete,
model-agnostic view (routed directly in ``urls.py``, never subclassed per
app) — exactly the shape ``_inherit_view`` targets without any base-class
fallback, so it's registered directly here, hooking the ``handle_save_error``
seam. ``enforce_pending_edit_policy`` (connected via a ``pre_save`` signal in
``signals.py``) still runs as a normal side effect of ``obj.save()`` inside
``UpdateAllFieldsView.post`` — this extension only customizes the response
when that policy raises a ``ValidationError``, turning it into the same
friendly warning + redirect the old inline editor showed instead of a bare
form-level error message.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError

from horilla.apps import apps as horilla_apps
from horilla.contrib.core.models.base import HorillaContentType
from horilla.extension.view import ViewExtension
from horilla.utils.translation import gettext_lazy as _
from horilla.web import HttpResponse

from .models import ApprovalInstance


def _get_list_redirect_url(request, model_name, pk):
    """
    Return the list/parent URL to redirect to after an approval event.
    Tries (in order):
      1. The stored detail-referer session key set by HorillaDetailView
         when the user navigated from the list to this detail view.
      2. HTTP_REFERER header.
      3. "/" as a last resort.
    """
    session_key = f"detail_referer_{model_name}_{pk}"
    url = request.session.get(session_key)
    if url:
        return url
    return request.META.get("HTTP_REFERER") or "/"


class ApprovalGuardBulkEditExtension(ViewExtension):
    """Redirect with a friendly message when a bulk save is blocked by the approval guard."""

    _inherit_view = (
        "horilla.contrib.generics.views.helpers.edit_field.UpdateAllFieldsView"
    )

    def handle_save_error(self, request, obj, error, app_label, model_name):
        """Turn the approval pending-edit ``ValidationError`` into a redirect."""
        approval_phrases = ("pending approval", "rejected state")
        message_text = " ".join(str(msg) for msg in error.messages).lower()
        if not any(phrase in message_text for phrase in approval_phrases):
            return super().handle_save_error(request, obj, error, app_label, model_name)

        messages.warning(
            request,
            str(_("This record is pending approval and cannot be edited.")),
        )
        resp = HttpResponse()
        resp["HX-Redirect"] = _get_list_redirect_url(request, model_name, obj.pk)
        return resp

    def post(self, request, pk, app_label, model_name):
        """Redirect after a successful bulk save that created a pending approval."""
        response = super().post(request, pk, app_label, model_name)
        if response.status_code != 200:
            return response
        try:
            model = horilla_apps.get_model(app_label, model_name)
            ct = HorillaContentType.objects.get_for_model(model)
            is_pending = ApprovalInstance.objects.filter(
                content_type=ct,
                object_id=str(pk),
                status="pending",
                is_active=True,
            ).exists()
        except Exception:
            return response

        if not is_pending:
            return response

        messages.success(request, str(_("Record has been submitted for approval.")))
        resp = HttpResponse()
        resp["HX-Redirect"] = _get_list_redirect_url(request, model_name, pk)
        return resp
