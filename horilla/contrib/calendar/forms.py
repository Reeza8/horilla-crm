"""Forms for custom calendars and Google Calendar integration."""

# Standard library imports
import json

# Third-party imports (Django)
from django import forms

# First party imports (Horilla)
from horilla.apps import apps
from horilla.contrib.core.models import HorillaContentType
from horilla.contrib.generics.forms import HorillaModelForm
from horilla.urls import reverse
from horilla.utils.choices import DISPLAYABLE_FIELD_TYPES
from horilla.utils.translation import gettext_lazy as _

from .models import CustomCalendar

# Local imports
from .module_registry import get_custom_calendar_models


def _resolve_model_from_module_value(module_value):
    """Resolve a Django model from HorillaContentType pk or registry key."""
    if not module_value:
        return None
    if str(module_value).isdigit():
        try:
            ct = HorillaContentType.objects.get(pk=module_value)
            module_key = (ct.model or "").strip().lower()
        except HorillaContentType.DoesNotExist:
            return None
    else:
        module_key = str(module_value).strip().lower()
    if not module_key:
        return None
    for key, model_cls in get_custom_calendar_models():
        if key == module_key:
            return model_cls
    for app_config in apps.get_app_configs():
        try:
            return apps.get_model(app_label=app_config.label, model_name=module_key)
        except LookupError:
            continue
    return None


def _date_field_choices(model):
    choices = [("", "---------")]
    if not model:
        return choices
    for field in model._meta.get_fields():
        if not getattr(field, "concrete", False):
            continue
        if getattr(field, "is_relation", False):
            continue
        if not hasattr(field, "get_internal_type"):
            continue
        ft = field.get_internal_type()
        if ft not in ("DateField", "DateTimeField"):
            continue
        label = field.verbose_name or field.name.replace("_", " ").title()
        choices.append((field.name, str(label)))
    return choices


def _display_field_choices(model):
    """Fields suitable for calendar titles (same idea as dashboard column picker)."""
    choices = [("", "---------")]
    if not model:
        return choices
    for field in model._meta.get_fields():
        if field.is_relation and getattr(field, "many_to_one", False):
            field_name = field.name
            field_label = field.verbose_name or field.name
            choices.append((field_name, str(field_label)))
            continue
        if not getattr(field, "concrete", False):
            continue
        if getattr(field, "is_relation", False):
            continue
        if not hasattr(field, "get_internal_type"):
            continue
        field_type = field.get_internal_type()
        if field_type in DISPLAYABLE_FIELD_TYPES:
            label = field.verbose_name or field.name.replace("_", " ").title()
            choices.append((field.name, str(label)))
        elif hasattr(field, "choices") and field.choices:
            label = field.verbose_name or field.name.replace("_", " ").title()
            choices.append((field.name, str(label)))
    return choices


class CustomCalendarForm(HorillaModelForm):
    """Single-step form: module, date fields, display field, color, and generic conditions."""

    htmx_field_choices_url = "generics:get_model_field_choices"

    field_order = [
        "name",
        "color",
        "module",
        "start_date_field",
        "end_date_field",
        "display_name_field",
        "is_selected",
    ]

    class Meta:
        """Field list and widgets for creating or editing a custom calendar."""

        model = CustomCalendar
        fields = "__all__"
        exclude = ["user"]
        widgets = {
            "color": forms.TextInput(
                attrs={
                    "type": "color",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        # HTMX reload after changing module must NOT use ``data=GET`` - that binds the form and
        # triggers validation, showing "required" on empty fields before Save. Merge GET into
        # ``initial`` instead so the form stays unbound until POST.
        request = kwargs.get("request")
        if (
            request
            and request.method == "GET"
            and request.GET
            and request.headers.get("HX-Request")
        ):
            initial = kwargs.get("initial")
            if initial is None:
                initial = {}
            elif not isinstance(initial, dict):
                initial = dict(initial)
            q = request.GET
            for key in q.keys():
                initial[key] = q.get(key)
            kwargs["initial"] = initial
        super().__init__(*args, **kwargs)

        module_val = None
        if self.data:
            module_val = self.data.get("module")
        if not module_val and getattr(self, "initial", None):
            module_val = self.initial.get("module")
        if not module_val and self.request:
            module_val = self.request.GET.get("module") or self.request.POST.get(
                "module"
            )
        if (
            not module_val
            and self.instance
            and self.instance.pk
            and self.instance.module_id
        ):
            module_val = str(self.instance.module_id)

        model = _resolve_model_from_module_value(module_val)

        if "module" in self.fields and self.request and hasattr(self.request, "user"):
            user = self.request.user
            allowed_pks = []
            for _, model_cls in get_custom_calendar_models():
                app_label = model_cls._meta.app_label
                meta_model_name = model_cls._meta.model_name
                view_perm = f"{app_label}.view_{meta_model_name}"
                view_own_perm = f"{app_label}.view_own_{meta_model_name}"
                if user.has_perm(view_perm) or user.has_perm(view_own_perm):
                    ct = HorillaContentType.objects.filter(
                        app_label=app_label,
                        model=model_cls._meta.model_name,
                    ).first()
                    if ct:
                        allowed_pks.append(ct.pk)
            self.fields["module"].queryset = HorillaContentType.objects.filter(
                pk__in=allowed_pks
            )
            self.fields["module"].required = False
            self.fields["module"].empty_label = "---------"
            # Refresh this single-form view when module changes,
            # so date/display field choices are rebuilt from selected model.
            reload_path = self.request.path
            pk = getattr(getattr(self, "instance", None), "pk", None)
            if pk:
                reload_path = reverse(
                    "calendar:custom_calendar_update", kwargs={"pk": pk}
                )
            self.fields["module"].widget.attrs.update(
                {
                    "hx-get": reload_path,
                    "hx-target": "#customcalendar-form-view-container",
                    "hx-swap": "outerHTML",
                    "hx-include": "#customcalendar-form-view",
                    "hx-trigger": "change",
                }
            )

        date_choices = _date_field_choices(model)
        display_choices = _display_field_choices(model)

        for fname in ("start_date_field", "end_date_field", "display_name_field"):
            self.fields[fname] = forms.ChoiceField(
                choices=(
                    date_choices if fname != "display_name_field" else display_choices
                ),
                required=fname != "end_date_field",
                widget=forms.Select(
                    attrs={
                        "class": "js-example-basic-single headselect",
                        "id": f"id_{fname}",
                    }
                ),
            )
        self.fields["start_date_field"].label = CustomCalendar._meta.get_field(
            "start_date_field"
        ).verbose_name
        self.fields["end_date_field"].label = CustomCalendar._meta.get_field(
            "end_date_field"
        ).verbose_name
        self.fields["display_name_field"].label = CustomCalendar._meta.get_field(
            "display_name_field"
        ).verbose_name
        self.fields["name"].label = CustomCalendar._meta.get_field("name").verbose_name
        self.fields["color"].label = CustomCalendar._meta.get_field(
            "color"
        ).verbose_name
        self.fields["module"].label = CustomCalendar._meta.get_field(
            "module"
        ).verbose_name
        self.fields["is_selected"].label = CustomCalendar._meta.get_field(
            "is_selected"
        ).verbose_name
        # Keep native color swatch appearance with compact boxed styling.
        self.fields["color"].widget.attrs.pop("placeholder", None)
        self.fields["color"].widget.attrs[
            "class"
        ] = "w-full h-8 p-1 cursor-pointer bg-white border border-dark-50 rounded-md"

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("module"):
            self.add_error("module", _("Please select a module."))
        start = cleaned_data.get("start_date_field")
        end = cleaned_data.get("end_date_field")
        if start and end and start == end:
            self.add_error(
                "end_date_field",
                _("End date field must differ from start date field."),
            )
        return cleaned_data


class GoogleSyncDirectionForm(forms.ModelForm):
    """Form for the user to choose one-way or two-way sync direction."""

    class Meta:
        """Expose only ``sync_direction`` on :class:`~.models.GoogleCalendarConfig`."""

        from .models import GoogleCalendarConfig

        model = GoogleCalendarConfig
        fields = ["sync_direction"]
        widgets = {
            "sync_direction": forms.RadioSelect(),
        }


class GoogleCredentialsUploadForm(forms.Form):
    """
    Form for users to upload their Google OAuth2 client_secret_*.json file
    and set the redirect URI, stored per-user in GoogleCalendarConfig.
    """

    credentials_file = forms.FileField(
        label=_("Google OAuth JSON file"),
        help_text=_(
            "Upload the client_secret_*.json file downloaded from Google Cloud Console."
        ),
        widget=forms.ClearableFileInput(attrs={"accept": ".json"}),
    )
    redirect_uri = forms.URLField(
        label=_("Redirect URI"),
        help_text=_(
            "Must match exactly what you registered in Google Cloud Console. "
            "E.g. https://yourdomain.com/calendar/google-calendar/callback/"
        ),
        widget=forms.URLInput(
            attrs={
                "class": "w-full text-xs border border-dark-50 rounded-md p-3 focus:outline-none focus:border-primary-400 mt-1",
                "placeholder": "https://yourdomain.com/calendar/google-calendar/callback/",
            }
        ),
    )

    def clean_credentials_file(self):
        """Validate uploaded JSON is a Google OAuth client secret / installed app file."""
        f = self.cleaned_data["credentials_file"]
        try:
            data = json.loads(f.read().decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise forms.ValidationError(_("Invalid JSON file.")) from exc
        if "web" not in data and "installed" not in data:
            raise forms.ValidationError(
                _(
                    "Not a valid Google OAuth2 credentials file. "
                    "Expected a JSON with a 'web' or 'installed' key."
                )
            )
        return data  # Returns parsed dict, not the raw file
