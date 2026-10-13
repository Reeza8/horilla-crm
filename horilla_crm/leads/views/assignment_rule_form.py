"""
Live preview behind the "Assign using rules" option on the lead forms.

The option is a checkbox under the Owner field of the create forms. Toggling it
(or changing a field the assignment rules look at while it is ticked) asks this
view for the Owner box as it should look now: limited to the people the
matching rule can assign to, or back to the normal owner field when the
checkbox is unticked.
"""

# Third-party imports (Django)
from django.contrib.auth.mixins import LoginRequiredMixin

# First party imports (Horilla)
from horilla.extension.forms.resolve import resolve_form_class
from horilla.utils.decorators import htmx_required, method_decorator
from horilla.views.generic import View
from horilla.web import HttpResponse

# Local imports
from horilla_crm.leads.forms import LeadFormClass, LeadSingleForm

# The form is picked from this list; a form class is never taken from the request.
FORM_CLASSES = {"single": LeadSingleForm, "multi": LeadFormClass}


@method_decorator(htmx_required, name="dispatch")
class LeadAssignmentOwnerView(LoginRequiredMixin, View):
    """Render the Owner field of a lead create form for the current form values."""

    def get(self, request, *args, **kwargs):
        """Return the Owner field for the submitted values."""
        if not request.user.has_any_perms(["leads.add_lead", "leads.add_own_lead"]):
            return HttpResponse(status=403)

        base_class = FORM_CLASSES.get(request.GET.get("mode"), LeadSingleForm)
        form = resolve_form_class(base_class)(data=request.GET, request=request)
        form._assignment_preview = True
        form.full_clean()
        return HttpResponse(form.render_owner_preview())
