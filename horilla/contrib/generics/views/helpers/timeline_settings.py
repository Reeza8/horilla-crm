"""
Timeline settings persisted per user (TimelineSpanBy), KanbanGroupBy-style FormView.
"""

# Standard library imports
from urllib.parse import parse_qs, urlencode

# Third-party imports (Django)
from django.views.generic import FormView

from horilla.contrib.core.models import TimelineSpanBy
from horilla.utils.decorators import htmx_required, method_decorator
from horilla.utils.translation import gettext_lazy as _

# First party imports (Horilla)
from horilla.web import ScriptResponse

# Local imports
from ...forms.generics import TimelineSpanByForm


@method_decorator(htmx_required, name="dispatch")
class TimelineSettingsFormView(FormView):
    """Configure and save timeline start/end fields; then HTMX-reload timeline in main session."""

    template_name = "timeline_span_form.html"
    form_class = TimelineSpanByForm

    def get_form_kwargs(self):
        """Build form kwargs with instance/initial from GET and saved TimelineSpanBy row."""
        kwargs = super().get_form_kwargs()
        model_name = self.request.GET.get("model") or self.request.POST.get(
            "model_name"
        )
        app_label = self.request.GET.get("app_label") or self.request.POST.get(
            "app_label"
        )
        if model_name and app_label:
            initial = kwargs.get("initial") or {}
            initial["main_url"] = self.request.GET.get("main_url", "")
            preserve = []
            for key in self.request.GET:
                if key in ("app_label", "model", "main_url"):
                    continue
                for value in self.request.GET.getlist(key):
                    preserve.append((key, value))
            initial["preserve_qs"] = urlencode(preserve) if preserve else ""
            kwargs["initial"] = initial
            existing = (
                TimelineSpanBy.all_objects.filter(
                    app_label=app_label,
                    user=self.request.user,
                )
                .filter(model_name__iexact=model_name)
                .first()
            )
            if existing:
                kwargs["instance"] = existing
            else:
                kwargs["instance"] = TimelineSpanBy(
                    model_name=model_name,
                    app_label=app_label,
                    user=self.request.user,
                    start_field="",
                    end_field="",
                )
                # Defaults from view class via GET if first save
                if self.request.GET.get("timeline_start"):
                    kwargs["initial"]["start_field"] = self.request.GET.get(
                        "timeline_start"
                    )
                if self.request.GET.get("timeline_end"):
                    kwargs["initial"]["end_field"] = self.request.GET.get(
                        "timeline_end"
                    )
        return kwargs

    def get_context_data(self, **kwargs):
        """Add settings title for the timeline span form modal."""
        context = super().get_context_data(**kwargs)
        context["settings_title"] = _("Timeline settings")
        return context

    def form_valid(self, form):
        """Save timeline span settings and reload the timeline via HTMX."""
        form.instance.user = self.request.user
        form.save()
        main_url = (
            self.request.GET.get("main_url") or self.request.POST.get("main_url") or ""
        )
        preserve_qs = self.request.POST.get("preserve_qs") or ""

        if not main_url:
            return ScriptResponse(close=True, reload=True)

        params = {}
        if preserve_qs:
            params = parse_qs(preserve_qs, keep_blank_values=True)
        params["layout"] = ["timeline"]
        params["timeline_start"] = [form.cleaned_data["start_field"]]
        params["timeline_end"] = [form.cleaned_data["end_field"]]
        pairs = []
        for key, values in params.items():
            if not isinstance(values, list):
                values = [values]
            for v in values:
                pairs.append((key, v))
        # qs = urlencode(pairs, doseq=True)
        # url = f"{main_url}?{qs}" if qs else main_url
        # url_js = json.dumps(url)

        return ScriptResponse(reload=True, close=True)


def get_timeline_span_by_row(user, app_label, model_name):
    """
    Return the TimelineSpanBy row for this user/model, or None.
    Matches model_name case-insensitively so navbar ?model=User finds row
    stored as user (or vice versa) and header caption uses saved fields.
    """
    if not user or not user.is_authenticated or not app_label or not model_name:
        return None
    return (
        TimelineSpanBy.all_objects.filter(app_label=app_label, user=user)
        .filter(model_name__iexact=model_name)
        .first()
    )


def get_saved_timeline_fields(user, app_label, model_name):
    """
    Return (start_field, end_field) from TimelineSpanBy for user/model, or (None, None).
    """
    row = get_timeline_span_by_row(user, app_label, model_name)
    if not row:
        return None, None
    return row.start_field or None, row.end_field or None
