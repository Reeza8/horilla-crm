"""Enroll a record in a cadence and un-enroll it again (cadence tab on a record)."""

# Standard library imports
from functools import cached_property

# Third-party imports (Django)
from django.contrib import messages

# First party imports (Horilla)
from horilla.apps import apps
from horilla.auth.mixins import LoginRequiredMixin
from horilla.contrib.core.utils import is_owner
from horilla.contrib.generics.views import HorillaSingleFormView
from horilla.registry.feature import FEATURE_REGISTRY
from horilla.shortcuts import get_object_or_404
from horilla.urls import reverse
from horilla.utils.decorators import htmx_required, method_decorator
from horilla.utils.translation import gettext_lazy as _
from horilla.views.generic import View
from horilla.web import Http404, ScriptResponse

# Local imports
from .. import services
from ..forms import ENROLL_RECORD_SESSION_KEY, CadenceEnrollForm, cadence_record_ref
from ..models import CadenceEnrollment


def get_cadence_record(app_label, model_name, pk):
    """Return ``(model, record)`` for a model registered for cadences, else 404."""
    try:
        model = apps.get_model(app_label, model_name)
    except LookupError as exc:
        raise Http404(_("Invalid model for cadence.")) from exc
    if model not in FEATURE_REGISTRY["cadence_models"]:
        raise Http404(_("Cadences are not enabled for this model."))
    return model, get_object_or_404(model, pk=pk)


def can_change_record(user, model, record):
    """Enrolling changes what happens to a record, so it needs edit access to it."""
    app_label = model._meta.app_label
    model_name = model._meta.model_name
    return user.has_perm(f"{app_label}.change_{model_name}") or (
        user.has_perm(f"{app_label}.change_own_{model_name}")
        and is_owner(model, record.pk)
    )


def _denied(request):
    messages.error(request, _("You don't have permission to change this record."))
    return ScriptResponse(close=True, reload=True, msgs=True)


@method_decorator(htmx_required, name="dispatch")
class CadenceEnrollView(LoginRequiredMixin, HorillaSingleFormView):
    """
    "Enroll Cadence" form: a generic form with one multi-select of cadences.

    Each chosen cadence starts a fresh run from its first follow-up.
    """

    model = CadenceEnrollment
    form_class = CadenceEnrollForm
    form_title = _("Enroll Cadence")
    view_id = "cadence-enroll-form"
    modal_height = False
    save_and_new = False
    full_width_fields = ["cadences"]
    # Only users who may edit the record can enroll it; checked in dispatch().
    skip_permission_check = True

    def dispatch(self, request, *args, **kwargs):
        """Load the record; only users who can edit it may enroll it."""
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        self.record_model, self.record = get_cadence_record(
            kwargs["app_label"], kwargs["record_model"], kwargs["record_pk"]
        )
        if not can_change_record(request.user, self.record_model, self.record):
            return _denied(request)
        if request.method == "GET":
            request.session[ENROLL_RECORD_SESSION_KEY] = cadence_record_ref(
                self.record_model, self.record.pk
            )
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        """The record comes from the URL, never from the submitted data."""
        initial = super().get_initial()
        initial["record"] = cadence_record_ref(self.record_model, self.record.pk)
        return initial

    @cached_property
    def form_url(self):
        """Where the form posts to."""
        return reverse(
            "cadences:cadence_enroll_modal",
            kwargs={
                "app_label": self.kwargs["app_label"],
                "record_model": self.kwargs["record_model"],
                "record_pk": self.kwargs["record_pk"],
            },
        )

    def form_valid(self, form):
        """Enroll in the chosen cadences and report what happened."""
        enrolled, errors = form.save()
        for error in errors:
            messages.error(self.request, error)
        if enrolled:
            messages.success(
                self.request,
                _("Enrolled in %(cadences)s.") % {"cadences": ", ".join(enrolled)},
            )
        return ScriptResponse(close=True, reload=True, msgs=True)


@method_decorator(htmx_required, name="dispatch")
class CadenceUnenrollView(LoginRequiredMixin, View):
    """Un-enroll a manually enrolled, running enrollment."""

    def post(self, request, *args, **kwargs):
        """Close the enrollment and cancel its open follow-ups."""
        enrollment = get_object_or_404(CadenceEnrollment.all_objects, pk=kwargs["pk"])
        model = enrollment.content_type.model_class()
        record = (
            model.objects.filter(pk=enrollment.object_id).first() if model else None
        )
        if record is None or not can_change_record(request.user, model, record):
            return _denied(request)
        try:
            services.unenroll(enrollment, request.user)
        except services.EnrollmentError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request,
                _("Un-enrolled from %(cadence)s.")
                % {"cadence": enrollment.cadence.name},
            )
        return ScriptResponse(close=True, reload=True, msgs=True)
