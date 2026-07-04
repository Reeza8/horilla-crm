"""
Edit-field and inline value views for horilla.contrib.generics.

HTMX views for editing field values and resolving dynamic widgets.
"""

# Standard library imports
from datetime import datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

# Third-party imports (Django)
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.template import Context, Template
from django.views import View

from horilla.apps import apps
from horilla.db import models
from horilla.shortcuts import get_object_or_404, render

# First party imports (Horilla)
from horilla.utils import timezone
from horilla.utils.decorators import htmx_required, method_decorator
from horilla.utils.translation import gettext_lazy as _
from horilla.web import HttpResponse


@method_decorator(htmx_required, name="dispatch")
class EditFieldView(LoginRequiredMixin, View):
    """
    View to render an editable field input for a specific object field.
    """

    template_name = "partials/edit_field.html"
    model = None

    def _is_phone_field(self, field):
        """Check if a CharField should render with country-code phone selection."""
        from horilla.contrib.generics.forms.form_class_mixin import HorillaFormMixin

        return field.name in HorillaFormMixin._DEFAULT_PHONE_FIELD_NAMES

    def get_field_info(self, field, obj, user=None):
        """Get field information including type, choices, and current value"""
        field_info = {
            "name": field.name,
            "verbose_name": field.verbose_name,
            "field_type": "text",  # default
            "value": getattr(obj, field.name, ""),
            "choices": [],
            "display_value": str(getattr(obj, field.name, "")),
            "use_select2": False,  # Default to False
        }

        if isinstance(field, models.ManyToManyField):
            field_info["field_type"] = "select"
            field_info["multiple"] = True
            field_info["use_select2"] = True

            related_model = field.related_model
            field_info["related_app_label"] = related_model._meta.app_label
            field_info["related_model_name"] = related_model._meta.model_name

            # Get current values
            current_values = getattr(obj, field.name).values_list("pk", flat=True)
            field_info["value"] = list(current_values) if current_values else []

            # Get initial choices for selected items only
            field_info["choices"] = []
            if current_values:
                selected_objects = related_model.objects.filter(pk__in=current_values)
                field_info["choices"] = [
                    {"value": obj.pk, "label": str(obj)} for obj in selected_objects
                ]

            field_info["display_value"] = (
                ", ".join(str(item) for item in getattr(obj, field.name).all())
                if getattr(obj, field.name).exists()
                else ""
            )

        elif isinstance(field, models.ForeignKey):
            field_info["field_type"] = "select"
            field_info["use_select2"] = True

            related_model = field.related_model
            field_info["related_app_label"] = related_model._meta.app_label
            field_info["related_model_name"] = related_model._meta.model_name

            # Get current value
            current_obj = getattr(obj, field.name)
            field_info["value"] = current_obj.pk if current_obj else ""

            # Get initial choices - only the selected item if exists
            field_info["choices"] = [{"value": "", "label": "---------"}]
            if current_obj:
                field_info["choices"].append(
                    {"value": current_obj.pk, "label": str(current_obj)}
                )

            field_info["display_value"] = str(current_obj) if current_obj else ""

        elif hasattr(field, "choices") and field.choices:
            field_info["field_type"] = "select"
            field_info["choices"] = [{"value": "", "label": "---------"}]
            field_info["choices"].extend(
                [{"value": choice[0], "label": choice[1]} for choice in field.choices]
            )
            field_info["display_value"] = getattr(obj, f"get_{field.name}_display")()

        elif isinstance(field, models.BooleanField):
            field_info["field_type"] = "select"
            field_info["choices"] = [
                {"value": "", "label": "---------"},
                {"value": "True", "label": "Yes"},
                {"value": "False", "label": "No"},
            ]
            current_value = getattr(obj, field.name)
            field_info["value"] = (
                str(current_value) if current_value is not None else ""
            )
            field_info["display_value"] = (
                "Yes" if current_value else "No" if current_value is False else ""
            )

        elif isinstance(field, models.CharField) and self._is_phone_field(field):
            field_info["field_type"] = "phone"
            from horilla.contrib.generics.forms.generics import PhoneWidget

            field_info["phone_widget_html"] = PhoneWidget().render(
                field.name, field_info["value"] or ""
            )

        elif isinstance(field, models.EmailField):
            field_info["field_type"] = "email"

        elif isinstance(field, models.URLField):
            field_info["field_type"] = "url"

        elif isinstance(
            field,
            (models.IntegerField, models.BigIntegerField, models.SmallIntegerField),
        ):
            field_info["field_type"] = "number"

        elif isinstance(field, (models.DecimalField, models.FloatField)):
            field_info["field_type"] = "number"
            field_info["step"] = "0.01"

        elif isinstance(field, models.DateTimeField):
            field_info["field_type"] = "datetime-local"
            if field_info["value"]:
                dt_value = field_info["value"]

                # Convert to user's timezone if available
                if user and hasattr(user, "time_zone") and user.time_zone:
                    try:
                        user_tz = ZoneInfo(user.time_zone)
                        # Make aware if naive
                        if timezone.is_naive(dt_value):
                            dt_value = timezone.make_aware(
                                dt_value, timezone.get_default_timezone()
                            )
                        # Convert to user timezone
                        dt_value = dt_value.astimezone(user_tz)
                    except Exception:
                        pass

                # Format for datetime-local input (without timezone info)
                field_info["value"] = dt_value.strftime("%Y-%m-%dT%H:%M")

                # Display value with user's format
                if user and hasattr(user, "date_time_format") and user.date_time_format:
                    try:
                        field_info["display_value"] = dt_value.strftime(
                            user.date_time_format
                        )
                    except Exception:
                        field_info["display_value"] = dt_value.strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                else:
                    field_info["display_value"] = dt_value.strftime("%Y-%m-%d %H:%M:%S")

        elif isinstance(field, models.DateField):
            field_info["field_type"] = "date"
            if field_info["value"]:
                date_value = field_info["value"]
                field_info["value"] = date_value.strftime("%Y-%m-%d")

                # Display value with user's format
                if user and hasattr(user, "date_format") and user.date_format:
                    try:
                        field_info["display_value"] = date_value.strftime(
                            user.date_format
                        )
                    except Exception:
                        field_info["display_value"] = date_value.strftime("%Y-%m-%d")
                else:
                    field_info["display_value"] = date_value.strftime("%Y-%m-%d")

        elif isinstance(field, models.TextField):
            field_info["field_type"] = "textarea"

        return field_info

    def get(self, request, pk, field_name, app_label, model_name):
        """
        Render the editable field input for the given object and field.

        Loads the object and field metadata and returns the rendered edit field
        template or a JS snippet to trigger a page reload on error.
        """
        pipeline_field = request.GET.get("pipeline_field", None)
        try:
            if not self.model:
                self.model = apps.get_model(app_label, model_name)
            perm = f"{self.model._meta.app_label}.change_{self.model._meta.model_name}"
            if not request.user.has_perm(perm):
                messages.error(request, _("You do not have permission to edit this."))
                return HttpResponse("<script>$('#reloadButton').click();</script>")
            obj = get_object_or_404(self.model, pk=pk)
            field = next(
                (f for f in obj._meta.get_fields() if f.name == field_name), None
            )
        except Exception as e:
            messages.error(self.request, e)
            return HttpResponse("<script>$('#reloadButton').click();</script>")

        field_info = self.get_field_info(field, obj, request.user)

        context = {
            "object_id": pk,
            "field_info": field_info,
            "app_label": app_label,
            "model_name": model_name,
            "pipeline_field": pipeline_field,
        }
        return render(request, self.template_name, context)


@method_decorator(htmx_required, name="dispatch")
class UpdateFieldView(LoginRequiredMixin, View):
    """
    View to handle updating a single field of an object.
    """

    template_name = "partials/field_display.html"
    model = None

    def post(self, request, pk, field_name, app_label, model_name):
        """
        Update a single field on an object based on submitted POST data.

        Handles many-to-many and simple field updates and returns an appropriate
        HTTP response or error status on failure.
        """
        try:
            if not self.model:
                self.model = apps.get_model(app_label, model_name)
            perm = f"{self.model._meta.app_label}.change_{self.model._meta.model_name}"
            if not request.user.has_perm(perm):
                messages.error(request, _("You do not have permission to edit this."))
                return HttpResponse(
                    "<script>$('#reloadButton').click();</script>", status=403
                )
            obj = get_object_or_404(self.model, pk=pk)
            field = next(
                (f for f in obj._meta.get_fields() if f.name == field_name), None
            )
        except Exception as e:
            messages.error(self.request, e)
            return HttpResponse("<script>$('#reloadButton').click();</script>")

        if not field:
            return HttpResponse(status=404)

        if isinstance(field, models.ManyToManyField):
            values = request.POST.getlist(f"{field_name}[]")  # Get list of selected IDs
            try:
                # Clear existing relationships and set new ones
                related_manager = getattr(obj, field_name)
                related_manager.clear()
                if values and values != [""]:  # Only add if there are selected values
                    related_manager.add(*values)
            except Exception as e:
                msg = Template("Error updating field: {{ message }}").render(
                    Context({"message": str(e)})
                )
                return HttpResponse(msg, status=400)
        elif isinstance(field, models.CharField) and EditFieldView()._is_phone_field(
            field
        ):
            from horilla.contrib.generics.forms.generics import PhoneField

            code = request.POST.get(f"{field_name}_0", "")
            number = request.POST.get(f"{field_name}_1", "")
            setattr(obj, field_name, PhoneField().compress([code, number]))
            obj.save()
        else:
            value = request.POST.get(field_name)

            if value is not None:
                try:
                    # Handle different field types
                    if isinstance(field, models.ForeignKey):
                        if value == "":
                            setattr(obj, field_name, None)
                        else:
                            related_obj = field.related_model.objects.get(pk=value)
                            setattr(obj, field_name, related_obj)

                    elif isinstance(field, models.BooleanField):
                        if value == "":
                            setattr(obj, field_name, None)
                        else:
                            setattr(obj, field_name, value == "True")

                    elif isinstance(
                        field,
                        (
                            models.IntegerField,
                            models.BigIntegerField,
                            models.SmallIntegerField,
                        ),
                    ):
                        setattr(obj, field_name, int(value) if value else None)

                    elif isinstance(field, models.DecimalField):
                        if value:
                            try:
                                setattr(obj, field_name, Decimal(value))
                            except InvalidOperation:
                                msg = Template(
                                    "Invalid decimal value: {{ value }}"
                                ).render(Context({"value": value}))
                                return HttpResponse(msg, status=400)
                        else:
                            setattr(obj, field_name, None)

                    elif isinstance(field, models.FloatField):
                        setattr(obj, field_name, float(value) if value else None)

                    elif isinstance(field, models.DateTimeField):
                        if value:
                            try:
                                # Parse the datetime from the input (in user's timezone)
                                parsed_value = datetime.fromisoformat(value)

                                # Get user's timezone
                                user = request.user
                                if hasattr(user, "time_zone") and user.time_zone:
                                    try:
                                        # Convert to UTC or default timezone for storage
                                        user_tz = ZoneInfo(user.time_zone)
                                        # Make the parsed datetime aware in user's timezone
                                        parsed_value = parsed_value.replace(
                                            tzinfo=user_tz
                                        )
                                        parsed_value = parsed_value.astimezone(
                                            timezone.get_default_timezone()
                                        )
                                    except Exception:
                                        # Fallback: make aware with default timezone
                                        parsed_value = timezone.make_aware(
                                            parsed_value,
                                            timezone.get_default_timezone(),
                                        )
                                else:
                                    # No user timezone, use default
                                    parsed_value = timezone.make_aware(
                                        parsed_value, timezone.get_default_timezone()
                                    )

                                setattr(obj, field_name, parsed_value)
                            except ValueError as e:
                                msg = Template(
                                    "Invalid datetime format: {{ value }}"
                                ).render(Context({"value": value}))
                                return HttpResponse(msg, status=400)
                        else:
                            setattr(obj, field_name, None)

                    elif isinstance(field, models.DateField):
                        if value:
                            try:
                                parsed_value = datetime.fromisoformat(value).date()
                                setattr(obj, field_name, parsed_value)
                            except ValueError:
                                msg = Template(
                                    "Invalid date format: {{ value }}"
                                ).render(Context({"value": value}))
                                return HttpResponse(msg, status=400)
                        else:
                            setattr(obj, field_name, None)

                    else:
                        setattr(obj, field_name, value)

                    obj.save()

                except Exception as e:
                    msg = Template("Error updating field: {{ message }}").render(
                        Context({"message": str(e)})
                    )
                    return HttpResponse(msg, status=400)

        # Get updated field info for display
        edit_view = EditFieldView()
        field_info = edit_view.get_field_info(field, obj, request.user)

        context = {
            "field_info": field_info,
            "object_id": pk,
            "app_label": app_label,
            "model_name": model_name,
        }
        return render(request, self.template_name, context)


@method_decorator(htmx_required, name="dispatch")
class CancelEditView(LoginRequiredMixin, View):
    """
    View to cancel editing and return to display mode without saving.
    """

    template_name = "partials/field_display.html"
    model = None

    def get(self, request, pk, field_name, app_label, model_name):
        """
        Return the display mode for a field after canceling edit.

        Re-uses EditFieldView.get_field_info to provide field rendering without
        making changes to the object.
        """
        try:
            if not self.model:
                self.model = apps.get_model(app_label, model_name)
            perm = f"{self.model._meta.app_label}.view_{self.model._meta.model_name}"
            if not request.user.has_perm(perm):
                messages.error(request, _("You do not have permission to view this."))
                return HttpResponse("<script>$('#reloadButton').click();</script>")
            obj = get_object_or_404(self.model, pk=pk)
            field = next(
                (f for f in obj._meta.get_fields() if f.name == field_name), None
            )
        except Exception as e:
            messages.error(self.request, e)
            return HttpResponse("<script>$('#reloadButton').click();</script>")

        # Use the same field info structure as EditFieldView
        edit_view = EditFieldView()
        field_info = edit_view.get_field_info(field, obj)

        context = {
            "field_info": field_info,
            "object_id": pk,
            "app_label": app_label,
            "model_name": model_name,
        }
        return render(request, self.template_name, context)
