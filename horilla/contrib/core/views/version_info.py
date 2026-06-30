"""Views for displaying version information of Horilla and its modules."""

# Third-party imports (Django)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from horilla.shortcuts import render
from horilla.utils.version import collect_all_versions

# First party imports (Horilla)
from horilla.web import Http404


class VersionInfotemplateView(LoginRequiredMixin, TemplateView):
    """
    View to display version information of Horilla and its modules.
    When GET details=core|0|1|... is present, returns fragment for contentModal (HTMX).
    """

    template_name = "version_info/info.html"
    fragment_template_name = "version_info/version_details_fragment.html"

    def get_context_data(self, **kwargs):
        """Add core and other module versions to context."""
        context = super().get_context_data(**kwargs)
        module_versions = collect_all_versions()
        context["core_module"] = module_versions["module_versions"][0]
        context["other_modules"] = module_versions["module_versions"][1:]
        return context

    def get(self, request, *args, **kwargs):
        """Handle GET request. If 'details' param is present, return the corresponding module version fragment."""
        details = request.GET.get("details")
        if details is not None:
            module_versions = collect_all_versions()
            versions = module_versions["module_versions"]
            if details == "core":
                module = versions[0]
            else:
                try:
                    idx = int(details)
                    if idx < 0 or idx >= len(versions) - 1:
                        raise Http404("Invalid module index")
                    module = versions[1 + idx]
                except ValueError as exc:
                    raise Http404("Invalid details parameter") from exc
            return render(
                request,
                self.fragment_template_name,
                {"module": module},
            )
        return super().get(request, *args, **kwargs)
