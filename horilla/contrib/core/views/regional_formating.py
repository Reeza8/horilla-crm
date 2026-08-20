"""
This view handles the methods for regional Formating view
"""

# Third-party imports (Django)
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin

# First party imports (Horilla)
from horilla.shortcuts import render
from horilla.utils.decorators import method_decorator, permission_required_or_denied
from horilla.utils.translation import gettext_lazy as _
from horilla.views.generic import FormView

# Local imports
from ..forms import RegionalFormattingForm


@method_decorator(
    permission_required_or_denied("core.can_change_profile"), name="dispatch"
)
class ReginalFormatingView(LoginRequiredMixin, FormView):
    """
    Template view for Big deal alert page
    """

    template_name = "regional_formating/formating_view.html"
    form_class = RegionalFormattingForm

    def get(self, request, *args, **kwargs):
        """Render regional formatting form with current user instance."""
        form = self.get_form_class()(instance=request.user)
        context = {
            "form": form,
            "view_id": "regional-formating-view",
        }
        return render(request, self.template_name, context)

    def get_form_kwargs(self):
        """Pass current user as form instance."""
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.request.user
        return kwargs

    def form_valid(self, form):
        """Save preferences and re-render form with success message."""
        form.save()
        messages.success(
            self.request, _("Your preferences have been updated successfully.")
        )
        context = {
            "form": self.get_form_class()(instance=self.request.user),
            "view_id": "regional-formating-view",
        }
        return render(self.request, self.template_name, context)

    def form_invalid(self, form):
        """Show error message and re-render form with validation errors."""
        messages.error(self.request, _("There was an error updating your preferences."))
        return self.render_to_response(self.get_context_data(form=form))
