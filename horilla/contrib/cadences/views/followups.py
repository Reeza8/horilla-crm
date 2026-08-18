"""Cadence follow-up create/update/delete views."""

# Standard library imports
from functools import cached_property

# Third-party imports (Django)
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.template.loader import render_to_string

from horilla.contrib.generics.views import (
    HorillaSingleDeleteView,
    HorillaSingleFormView,
)
from horilla.contrib.mail.models import HorillaMailConfiguration
from horilla.shortcuts import get_object_or_404
from horilla.urls import reverse_lazy
from horilla.utils.decorators import (
    htmx_required,
    method_decorator,
    permission_required_or_denied,
)
from horilla.utils.translation import gettext_lazy as _

# First party imports (Horilla)
from horilla.views.generic import TemplateView
from horilla.web import Http404, HttpResponse, ScriptResponse

# Local imports
from ..forms import CadenceFollowUpForm
from ..models import Cadence, CadenceFollowUp


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(["cadences.add_cadence"]), name="dispatch"
)
class CadenceFollowUpCreateView(LoginRequiredMixin, HorillaSingleFormView):
    """Create follow-up item for a cadence."""

    model = CadenceFollowUp
    form_class = CadenceFollowUpForm
    modal_height = False
    save_and_new = False
    view_id = "cadence-followup-form"
    hidden_fields = ["followup_number", "branch_from"]

    def dispatch(self, request, *args, **kwargs):
        cadence_pk = kwargs.get("cadence_pk")
        if cadence_pk is not None:
            try:
                _cadence = get_object_or_404(Cadence, pk=cadence_pk)
            except Exception as e:
                messages.error(request, str(e))
                return ScriptResponse(reload=True, close=True)

        try:
            return super().dispatch(request, *args, **kwargs)
        except ValueError as e:
            messages.error(request, str(e))
            return ScriptResponse(reload=True, close=True)

    @staticmethod
    def _has_outgoing_mail_server(cadence):
        return HorillaMailConfiguration.objects.filter(
            mail_channel="outgoing", is_active=True
        ).exists()

    def _should_show_mail_config_popup(self, request, **kwargs):
        followup_type = request.GET.get("followup_type")
        is_update = bool(kwargs.get("pk"))
        if followup_type != "email" or is_update:
            return False
        cadence_pk = kwargs.get("cadence_pk") or request.GET.get("cadence")
        try:
            cadence = get_object_or_404(Cadence, pk=cadence_pk)
        except Exception as e:
            messages.error(request, str(e))
            return (
                None,
                ScriptResponse(reload=True, close=True),
            )
        return not self._has_outgoing_mail_server(cadence)

    def get(self, request, *args, **kwargs):
        show_mail_config_popup = self._should_show_mail_config_popup(request, **kwargs)
        if show_mail_config_popup:
            query = request.GET.copy()
            query["followup_type"] = "task"
            request.GET = query
        response = super().get(request, *args, **kwargs)
        if show_mail_config_popup and isinstance(response, HttpResponse):
            if hasattr(response, "render") and callable(response.render):
                response = response.render()
            popup_script = render_to_string(
                "partials/cadence_mail_config_popup.html",
                {"configure_url": "/mail/mail-server/"},
                request=request,
            )
            response.content = response.content + popup_script.encode("utf-8")
        return response

    def get_initial(self):
        """Set initial cadence and follow-up fields from URL when creating a follow-up."""
        initial = super().get_initial()
        if self.kwargs.get("pk"):
            return initial
        cadence_pk = self.kwargs.get("cadence_pk")
        if cadence_pk:
            initial["cadence"] = cadence_pk
        if self.request.GET.get("followup_number"):
            initial["followup_number"] = self.request.GET.get("followup_number")
        if self.request.GET.get("followup_type"):
            initial["followup_type"] = self.request.GET.get("followup_type")
        if self.request.GET.get("branch_from"):
            initial["branch_from"] = self.request.GET.get("branch_from")
        return initial

    @cached_property
    def form_url(self):
        """Return the URL for form submission, used in form kwargs for HTMX."""
        if self.kwargs.get("pk"):
            return reverse_lazy(
                "cadences:cadence_followup_update_view",
                kwargs={"pk": self.kwargs.get("pk")},
            )
        cadence_pk = self.kwargs.get("cadence_pk")
        return reverse_lazy(
            "cadences:cadence_followup_create_view",
            kwargs={"cadence_pk": cadence_pk},
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        form_url = self.get_form_url()
        if hasattr(form_url, "url"):
            form_url = form_url.url
        kwargs["form_url"] = self.request.build_absolute_uri(form_url)
        kwargs["htmx_trigger_target"] = f"#{self.view_id}-container"
        kwargs["do_this_toggle_url"] = reverse_lazy(
            "cadences:cadence_followup_do_this_value_field"
        )
        return kwargs

    def form_valid(self, form):
        super().form_valid(form)
        return ScriptResponse(close=True, reload=True)


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        [
            "cadences.delete_cadencefollowup",
        ]
    ),
    name="dispatch",
)
class CadenceFollowUpDeleteView(LoginRequiredMixin, HorillaSingleDeleteView):
    """Delete follow-up when it has no branch children."""

    model = CadenceFollowUp
    check_delete_permission = False
    success_message = _("Follow-up removed.")

    def _block_if_has_branch_children(self):
        if self.object.branch_children.exists():
            messages.error(
                self.request,
                _(
                    "Remove or reassign follow-ups in later stages before deleting this step."
                ),
            )
            return ScriptResponse(close=True, reload=True, msgs=True)
        return None

    def get(self, request, *args, **kwargs):
        try:
            self.object = self.get_object()
        except Exception as e:
            messages.error(self.request, str(e))
            return ScriptResponse(
                reload=True, msgs=True, extra="closeDeleteModeModal();", close=True
            )
        blocked = self._block_if_has_branch_children()
        if blocked is not None:
            return blocked
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        try:
            self.object = self.get_object()
        except Http404:
            raise
        blocked = self._block_if_has_branch_children()
        if blocked is not None:
            return blocked
        return super().post(request, *args, **kwargs)

    def get_post_delete_response(self):
        return HttpResponse(
            "<script>closeModal();htmx.trigger('#reloadButton','click');"
            "$('#reloadMessagesButton').click();closeDeleteModeModal();closeDeleteModal();</script>"
        )


@method_decorator(htmx_required, name="dispatch")
class CadenceFollowupDoThisValueFieldView(LoginRequiredMixin, TemplateView):
    """Return only do_this_value field container (HTMX field-level update)."""

    template_name = "partials/cadence_followup_do_this_value_field.html"

    def get_context_data(self, **kwargs):
        """Build form context for the do_this_value field partial."""
        context = super().get_context_data(**kwargs)
        form = CadenceFollowUpForm(
            initial=self.request.GET.dict() if self.request.GET else None
        )
        context["form"] = form
        do_this_unit = self.request.GET.get("do_this_unit") or "immediately"
        context["show_field"] = do_this_unit != "immediately"
        return context
