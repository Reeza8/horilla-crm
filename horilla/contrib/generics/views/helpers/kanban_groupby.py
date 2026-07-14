"""
Kanban group-by settings view for horilla.contrib.generics.

Form view for configuring kanban board group-by field and options.
"""

# Third-party imports (Django)
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.views.generic import FormView

# First party imports (Horilla)
from horilla.apps import apps
from horilla.contrib.core.models import KanbanGroupBy
from horilla.utils.decorators import htmx_required, method_decorator
from horilla.utils.translation import gettext_lazy as _
from horilla.web import HttpResponse, ScriptResponse

from ...forms import KanbanGroupByForm
from ..groupby import HorillaGroupByView

# Local imports
from ..kanban import HorillaKanbanView


@method_decorator(htmx_required, name="dispatch")
class HorillaKanbanGroupByView(FormView):
    """View for configuring kanban board group-by field settings."""

    template_name = "kanban_settings_form.html"
    form_class = KanbanGroupByForm

    def get_form_kwargs(self):
        """Pass model_name, app_label, exclude/include fields, and view_type to the form."""
        kwargs = super().get_form_kwargs()
        model_name = self.request.GET.get("model")
        app_label = self.request.GET.get("app_label")

        exclude_fields = self.request.POST.get(
            "exclude_fields"
        ) or self.request.GET.get("exclude_fields", None)

        if exclude_fields:
            exclude_fields = [f.strip() for f in exclude_fields.split(",") if f.strip()]
            exclude_fields = exclude_fields if exclude_fields else None
        else:
            exclude_fields = None

        include_fields = self.request.POST.get(
            "include_fields"
        ) or self.request.GET.get("include_fields", None)
        if include_fields:
            include_fields = [f.strip() for f in include_fields.split(",") if f.strip()]
            include_fields = include_fields if include_fields else None
        else:
            include_fields = None

        view_type = self.request.GET.get("view_type") or self.request.POST.get(
            "view_type"
        )
        if model_name and app_label:
            kwargs["instance"] = KanbanGroupBy(
                model_name=model_name,
                app_label=app_label,
                user=self.request.user,
                view_type=view_type,
            )
        kwargs["exclude_fields"] = exclude_fields
        kwargs["include_fields"] = include_fields
        kwargs["initial"] = kwargs.get("initial") or {}
        kwargs["initial"]["view_type"] = view_type
        return kwargs

    def get_context_data(self, **kwargs):
        """Add group_by_view_type and settings_title to template context."""
        context = super().get_context_data(**kwargs)
        view_type = self.request.GET.get("view_type") or self.request.POST.get(
            "view_type"
        )
        context["group_by_view_type"] = view_type
        context["settings_title"] = (
            _("Group By Settings") if view_type == "group_by" else _("Kanban Settings")
        )
        return context

    def form_valid(self, form):
        """Save group-by settings, set user and view_type, return close-modal script."""
        form.instance.user = self.request.user  # set the user server-side
        form.instance.view_type = form.cleaned_data.get("view_type")
        form.save()
        view_type = form.instance.view_type
        btn_id = "groupByBtn" if view_type == "group_by" else "kanbanBtn"
        return ScriptResponse(
            close=True,
            extra=f"$('#{btn_id}').click();",
        )


@method_decorator(htmx_required, name="dispatch")
class KanbanLoadMoreView(LoginRequiredMixin, View):
    """
    Handle AJAX request to load more items for a specific Kanban column.
    """

    def get(self, request, app_label, model_name, *args, **kwargs):
        """
        Handle GET request to load more items for a specific Kanban column.
        """
        try:
            model = apps.get_model(
                app_label=app_label.split(".")[-1], model_name=model_name
            )
            perm = f"{model._meta.app_label}.view_{model._meta.model_name}"
            if not request.user.has_perm(perm):
                messages.error(request, _("You do not have permission to view this."))
                return HttpResponse("<script>$('#reloadButton').click();")

            view_class = HorillaKanbanView._view_registry.get(model)
            if not view_class:
                messages.error(request, f"View class {model_name} not found")
                return HttpResponse("<script>$('#reloadButton').click();")

            # FIX: Properly initialize the view with model
            view = view_class()
            view.request = request
            view.model = model
            view.kwargs = kwargs  # Pass kwargs if needed

            return view.load_more_items(request)
        except Exception as e:
            messages.error(request, f"Load More failed: {str(e)}")
            return HttpResponse("<script>$('#reloadButton').click();")


@method_decorator(htmx_required, name="dispatch")
class GroupByLoadMoreView(LoginRequiredMixin, View):
    """
    Handle AJAX request to load more items for a specific group in the group-by view.
    """

    def get(self, request, app_label, model_name, *args, **kwargs):
        """
        Handle GET request to load more items for a specific group.
        """
        try:
            model = apps.get_model(
                app_label=app_label.split(".")[-1], model_name=model_name
            )
            perm = f"{model._meta.app_label}.view_{model._meta.model_name}"
            if not request.user.has_perm(perm):
                messages.error(request, _("You do not have permission to view this."))
                return HttpResponse("<script>$('#reloadButton').click();")

            view_class = HorillaGroupByView._view_registry.get(model)
            if not view_class:
                messages.error(request, f"View class {model_name} not found")
                return HttpResponse("<script>$('#reloadButton').click();")

            view = view_class()
            view.request = request
            view.model = model
            view.kwargs = kwargs

            return view.load_more_items(request)
        except Exception as e:
            messages.error(request, f"Load More failed: {str(e)}")
            return HttpResponse("<script>$('#reloadButton').click();")
