"""Generic detail + warning modal for duplicate merge flows."""

# Third-party imports (Django)
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View

# First party imports (Horilla)
from horilla.apps import apps

# First party imports (Horilla)
from horilla.contrib.core.models.base import HorillaContentType
from horilla.contrib.generics.views import HorillaModalDetailView
from horilla.db import models
from horilla.db.models import QuerySet
from horilla.shortcuts import render
from horilla.urls import reverse_lazy
from horilla.utils.decorators import htmx_required, method_decorator
from horilla.utils.translation import gettext_lazy as _
from horilla.web import HttpResponse, RedirectResponse


@method_decorator(htmx_required, name="dispatch")
class GenericDuplicateDetailView(LoginRequiredMixin, HorillaModalDetailView):
    """
    Generic detail view for duplicate records.
    Accepts content_type_id and pk to dynamically show detail view for any model.
    """

    title = _("Details")
    model = None  # Will be set dynamically

    def __init__(self, **kwargs):
        """Override to handle None model during initialization"""
        self.model = models.Model
        super().__init__(**kwargs)
        self.model = None
        self.ordered_ids_key = "ordered_ids_generic"

    def dispatch(self, request, *args, **kwargs):
        """Set up model and object before dispatch"""
        object_id = kwargs.get("pk") or request.GET.get("object_id")
        content_type_id = kwargs.get("content_type_id") or request.GET.get(
            "content_type_id"
        )

        if content_type_id:
            if isinstance(content_type_id, str):
                content_type_id = content_type_id.split("?")[0].split("&")[0]
            try:
                content_type_id = int(content_type_id)
            except (ValueError, TypeError):
                content_type_id = None

        if object_id and content_type_id:
            try:
                django_content_type = HorillaContentType.objects.get(pk=content_type_id)
                self.model = django_content_type.model_class()
                self.object_id = object_id
                self.content_type_id = content_type_id

                perm = (
                    f"{self.model._meta.app_label}.view_{self.model._meta.model_name}"
                )
                if not request.user.has_perm(perm):
                    messages.error(
                        request, _("You do not have permission to view this.")
                    )
                    return RedirectResponse(request)

                self.main_object = self.model.objects.get(pk=object_id)
            except Exception as e:
                messages.error(request, str(e))
                return RedirectResponse(request)
        else:
            messages.error(
                request,
                _("Invalid request for potential duplicates."),
            )
            return RedirectResponse(request)

        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        """Get queryset for the model"""
        if not self.model:
            return QuerySet()
        queryset = self.model.objects.all()
        return queryset

    def get_object(self, queryset=None):
        """Get the object using pk"""
        if queryset is None:
            queryset = self.get_queryset()
        pk = self.kwargs.get("pk")
        if not pk:
            return None
        try:
            obj = queryset.get(pk=pk)
            self.instance = obj
            return obj
        except self.model.DoesNotExist:
            return None
        except Exception:
            return None

    def get_header(self, obj=None):
        """Dynamically configure header based on model"""
        if obj is None:
            obj = getattr(self, "object", None) or getattr(self, "instance", None)
        if not obj:
            return {"title": "Horilla", "subtitle": "", "avatar": ""}

        title_field = None
        for field_name in ["name", "title", "first_name", "email", "__str__"]:
            if hasattr(obj, field_name):
                title_field = field_name
                break

        avatar_field = None
        for field_name in ["avatar", "image", "photo", "profile_picture", "get_avatar"]:
            if hasattr(obj, field_name):
                avatar_field = field_name
                break

        return {
            "title": title_field or "__str__",
            "subtitle": "",
            "avatar": avatar_field or "",
        }

    def get_body_fields(self, obj=None):
        """Dynamically configure body fields based on model"""
        if obj is None:
            obj = getattr(self, "object", None) or getattr(self, "instance", None)
        if not obj or not self.model:
            return []

        body_fields = []
        excluded_fields = [
            "id",
            "pk",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "company",
            "additional_info",
            "password",
            "is_active",
            "is_staff",
            "is_superuser",
            "last_login",
            "date_joined",
        ]

        for field in self.model._meta.get_fields():
            if field.name in excluded_fields:
                continue

            if hasattr(field, "related_model") and not getattr(field, "concrete", True):
                continue

            if hasattr(field, "many_to_many") and field.many_to_many:
                continue

            if not getattr(field, "concrete", True):
                continue

            verbose_name = getattr(field, "verbose_name", None)
            body_fields.append((_(verbose_name), field.name))

        return body_fields[:10]

    def get_actions(self, obj=None):
        """Get action buttons - include View Detail if object has get_detail_url"""
        if obj is None:
            obj = getattr(self, "object", None) or getattr(self, "instance", None)
        if not obj:
            return []

        actions = []

        if hasattr(obj, "get_detail_url"):
            try:
                detail_url = obj.get_detail_url()
                if detail_url:
                    detail_url = str(detail_url)
                    actions.append(
                        {
                            "action": _("Details"),
                            "src": "assets/icons/eye.svg",
                            "img_class": "w-3 h-3 flex gap-4 filter brightness-0 invert",
                            "attrs": f"""
                            class="w-24 justify-center px-4 py-2 bg-primary-600 text-white rounded-md text-xs flex items-center gap-2 hover:bg-primary-800 transition duration-300 cursor-pointer"
                            hx-get="{detail_url}"
                            hx-target="#mainContent"
                            hx-swap="outerHTML"
                            hx-push-url="true"
                            hx-select="#mainContent"
                            hx-on::after-request="ModalManager.closeAll()"
                        """,
                        }
                    )
            except Exception:
                pass

        return actions

    def get_context_data(self, **kwargs):
        """Override to set dynamic header and body"""
        obj = (
            kwargs.get("object")
            or getattr(self, "object", None)
            or getattr(self, "instance", None)
        )

        self.header = self.get_header(obj)
        self.body = self.get_body_fields(obj)
        self.actions = self.get_actions(obj)

        context = super().get_context_data(**kwargs)

        context["header"] = self.header
        context["body"] = self.body
        context["title"] = self.title
        context["actions"] = self.actions

        return context


@method_decorator(htmx_required, name="dispatch")
class DuplicateWarningModalView(LoginRequiredMixin, View):
    """
    View to render duplicate warning modal content.
    This view retrieves modal data from session and generates HTML directly.
    """

    def get(self, request, *args, **kwargs):
        """
        Return the duplicate warning modal HTML.
        """

        session_key = kwargs.get("session_key")

        if not session_key:
            return HttpResponse("No session key provided", status=404)

        if session_key not in request.session:
            return HttpResponse(f"Session key {session_key} not found", status=404)

        modal_data = request.session.pop(session_key, {})
        request.session.modified = True

        duplicate_records = []
        if modal_data.get("duplicate_records") and modal_data.get("model_name"):
            try:
                model_name = modal_data["model_name"]
                Model = None
                for app_config in apps.get_app_configs():
                    try:
                        Model = apps.get_model(app_config.label, model_name.lower())
                        break
                    except (LookupError, ValueError):
                        continue

                if Model:
                    for pk, _ in modal_data.get("duplicate_records", []):
                        try:
                            record = Model.objects.get(pk=pk)
                            duplicate_records.append(record)
                        except Model.DoesNotExist:
                            pass
            except Exception:
                pass

        duplicate_records_data = []
        for record in duplicate_records:
            detail_url = None
            try:
                content_type = HorillaContentType.objects.get_for_model(record)
                detail_url = str(
                    reverse_lazy(
                        "duplicates:generic_duplicate_detail_view",
                        kwargs={"content_type_id": content_type.pk, "pk": record.pk},
                    )
                )
            except Exception:
                pass

            duplicate_records_data.append(
                {
                    "display": str(record),
                    "detail_url": detail_url,
                }
            )

        context = {
            "alert_title": str(
                modal_data.get("alert_title", "Potential Duplicate Detected")
            ),
            "alert_message": str(
                modal_data.get(
                    "alert_message",
                    "Similar records were found. Do you want to proceed?",
                )
            ),
            "duplicate_records": duplicate_records_data,
            "show_duplicate_records": modal_data.get("show_duplicate_records", True),
            "action": modal_data.get("action", "allow"),
            "save_and_new_value": str(modal_data.get("save_and_new", "")),
        }

        return render(
            request,
            "duplicates/duplicate_warning_modal.html",
            context,
        )
