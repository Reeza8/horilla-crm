"""
This view handles the methods for Big deal alert view
"""

# Third-party imports (Django)
from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.functional import cached_property
from django.views.generic import View

from horilla.contrib.automations.filters import HorillaAutomationFilter
from horilla.contrib.automations.models import HorillaAutomation
from horilla.contrib.automations.views import HorillaAutomationFormView
from horilla.contrib.core.models import HorillaContentType
from horilla.contrib.generics.views import HorillaNavView, HorillaView
from horilla.contrib.utils.middlewares import _thread_local
from horilla.shortcuts import render
from horilla.urls import reverse_lazy
from horilla.utils import timezone
from horilla.utils.decorators import (
    htmx_required,
    method_decorator,
    permission_required_or_denied,
)
from horilla.utils.translation import gettext_lazy as _

# First party imports (Horilla)
from horilla.web import ScriptResponse


class BigDealAlertView(LoginRequiredMixin, HorillaView):
    """
    Template view for Big deal alert page
    """

    template_name = "big_deal_alert_view.html"
    nav_url = reverse_lazy("opportunities:big_deal_alert_nav")
    list_url = reverse_lazy("opportunities:big_deal_alert_list")


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("automations.view_horillaautomation"),
    name="dispatch",
)
class BigDealAlertNavbar(LoginRequiredMixin, HorillaNavView):
    """
    Navbar for big deal alert
    """

    nav_title = _("Big Deal Alerts")
    search_url = reverse_lazy("opportunities:big_deal_alert_list")
    main_url = reverse_lazy("opportunities:big_deal_alert_view")
    filterset_class = HorillaAutomationFilter
    one_view_only = True
    all_view_types = False
    filter_option = False
    reload_option = False
    nav_width = False
    gap_enabled = False
    search_option = False
    border_enabled = False

    @cached_property
    def new_button(self):
        """Return the 'Big Deal Create' button if the user has add permission."""
        if self.request.user.has_perm("automations.add_horillaautomation"):
            return {
                "url": reverse_lazy("opportunities:big_deal_automation_create"),
                "attrs": {"id": "big-deal-create"},
            }
        return None


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("automations.view_horillaautomation"),
    name="dispatch",
)
class BigDealAlertListView(LoginRequiredMixin, View):
    """
    Accordion view for Big Deal Alerts
    Shows only automations with additional_info['big_deal'] = True in accordion format
    """

    template_name = "big_deal_alert_accordion.html"

    def get_queryset(self):
        """Filter automations to show only big deal alerts."""
        return HorillaAutomation.objects.filter(additional_info__big_deal=True)

    def get(self, request, *args, **kwargs):
        """Render the accordion view."""
        automations = self.get_queryset()
        context = {
            "automations": automations,
            "request": request,
        }
        return render(request, self.template_name, context)


@method_decorator(htmx_required, name="dispatch")
class BigDealAutomationFormView(HorillaAutomationFormView):
    """
    Form view for creating automation for Big Deal Alert.
    Inherits from HorillaAutomationFormView and sets initial model to opportunity.
    """

    hidden_fields = ["model"]
    full_width_fields = ["title"]

    @cached_property
    def form_title(self):
        """Return form title based on whether we're creating or updating."""
        if self.kwargs.get("pk"):
            return _("Update Big Deal Alert")
        return _("Create Big Deal Alert")

    @cached_property
    def form_url(self):
        """Override form_url to use big deal automation URLs."""
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if pk:
            return reverse_lazy(
                "opportunities:big_deal_automation_update", kwargs={"pk": pk}
            )
        return reverse_lazy("opportunities:big_deal_automation_create")

    def dispatch(self, request, *args, **kwargs):
        """Override dispatch."""
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """Override post."""
        return super().post(request, *args, **kwargs)

    def get_form_kwargs(self):
        """Return keyword arguments for initializing the form."""
        kwargs = super().get_form_kwargs()

        # Ensure hidden_fields is always passed to the form
        kwargs["hidden_fields"] = self.hidden_fields

        if not self.kwargs.get("pk"):
            try:
                opportunity_content_type = HorillaContentType.objects.get(
                    model="opportunity"
                )
                if "initial" not in kwargs:
                    kwargs["initial"] = {}
                kwargs["initial"]["model"] = opportunity_content_type.pk
                kwargs["initial"]["model_name"] = "opportunity"
            except HorillaContentType.DoesNotExist:
                pass

        return kwargs

    def form_invalid(self, form):
        """Handle invalid form submission and ensure model field stays hidden."""
        if "model" in form.fields and "model" in self.hidden_fields:
            form.fields["model"].widget = forms.HiddenInput()
            form.fields["model"].widget.attrs.update({"class": "hidden-input"})
        return super().form_invalid(form)

    def form_valid(self, form):
        """Override form_valid to set additional_info['big_deal'] = True before saving."""
        if not self.request.user.is_authenticated:
            messages.error(
                self.request, "You must be logged in to perform this action."
            )
            return self.form_invalid(form)

        if self.condition_fields and not self.condition_model:
            created_instances = self.save_multiple_main_instances(form)
            if created_instances is False:
                return self.form_invalid(form)
            if created_instances:
                self.request.session["condition_row_count"] = 0
                messages.success(
                    self.request,
                    f"Created {len(created_instances)} {self.model._meta.verbose_name.lower()}(s) successfully!",
                )
                return ScriptResponse(reload=True, close=True)
            if created_instances == []:
                form.add_error(
                    None,
                    "At least one instance must be created with all required fields.",
                )
                return self.form_invalid(form)

        # Get object like parent does
        self.object = form.save(commit=False)

        # Handle file fields like parent
        for field_name, field in form.fields.items():
            if isinstance(field, forms.FileField) or isinstance(
                field, forms.ImageField
            ):
                clear_flag = self.request.POST.get(f"id_{field_name}_clear", "false")
                if clear_flag == "true":
                    setattr(self.object, field_name, None)

        # Set timestamps and company like parent
        if self.kwargs.get("pk") and not self.duplicate_mode:
            self.object.updated_at = timezone.now()
            self.object.updated_by = self.request.user
        else:
            self.object.created_at = timezone.now()
            self.object.created_by = self.request.user
            self.object.updated_at = timezone.now()
            self.object.updated_by = self.request.user
        self.object.company = form.cleaned_data.get("company") or (
            getattr(_thread_local, "request", None).active_company
            if hasattr(_thread_local, "request")
            else self.request.user.company
        )

        # Set additional_info['big_deal'] = True - THIS IS THE ONLY CHANGE
        if not self.object.additional_info:
            self.object.additional_info = {}
        self.object.additional_info["big_deal"] = True

        # Now manually save and handle the rest (can't use super() because it would save without our change)
        try:
            self.object.save()
            form.save_m2m()

            if self.condition_fields and self.condition_model:
                self.save_conditions(form)

            self.request.session["condition_row_count"] = 0
            self.request.session.modified = True
            action = (
                _("duplicated")
                if self.duplicate_mode
                else (
                    _("updated")
                    if self.kwargs.get("pk") and not self.duplicate_mode
                    else _("created")
                )
            )

            messages.success(
                self.request,
                _("%(model)s %(action)s successfully!")
                % {
                    "model": self.model._meta.verbose_name,
                    "action": action,
                },
            )

            if (
                "save_and_new" in self.request.POST
                and not self.kwargs.get("pk")
                and not self.duplicate_mode
            ):
                create_url = self.get_create_url()
                return render(
                    self.request,
                    "big_deal_alert_reload_fragment.html",
                    {"load_url": create_url, "close_modal": False},
                )

            if (
                self.detail_url_name
                and not self.kwargs.get("pk")
                and not self.duplicate_mode
            ):
                detail_url = reverse_lazy(
                    self.detail_url_name, kwargs={"pk": self.object.pk}
                )
                return render(
                    self.request,
                    "big_deal_alert_reload_fragment.html",
                    {"load_url": detail_url, "close_modal": True},
                )

            return render(
                self.request,
                "big_deal_alert_reload_fragment.html",
                {"load_url": None, "close_modal": True},
            )
        except Exception as e:
            messages.error(self.request, f"Error saving: {str(e)}")
            return self.form_invalid(form)
