"""Potential duplicates list + bulk merge button."""

# Standard library imports
from functools import cached_property
from urllib.parse import urlencode

# Third-party imports (Django)
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin

# First party imports (Horilla)
from horilla.contrib.core.models.base import HorillaContentType
from horilla.contrib.generics.views import HorillaListView

# First party imports (Horilla)
from horilla.db import models
from horilla.db.models import Case, QuerySet, When
from horilla.urls import reverse_lazy
from horilla.utils.decorators import htmx_required, method_decorator
from horilla.utils.translation import gettext_lazy as _
from horilla.web.response import RedirectResponse

# Local imports
from ...duplicate_checker import check_duplicates


@method_decorator(htmx_required, name="dispatch")
class PotentialDuplicatesTabView(LoginRequiredMixin, HorillaListView):
    """
    Tab view endpoint for potential duplicates using HorillaListView.
    Displays duplicates in a table format with bulk merge action.
    """

    template_name = "duplicates/potential_duplicates_list_view.html"
    view_id = "potential-duplicates-list"
    bulk_update_option = False
    bulk_delete_enabled = False
    bulk_export_option = False
    bulk_select_option = True
    list_column_visibility = False
    clear_session_button_enabled = False
    track_list_navigation = False

    # Limit selection to 3 items
    max_selection_limit = 3

    def __init__(self, **kwargs):
        """Initialize - model will be set in dispatch()"""

        class DummyModel(models.Model):
            """
            Dummy model used temporarily during initialization.
            This allows HorillaListView to initialize without a real model.
            """

            name = models.CharField(max_length=100, default="")

            class Meta:
                """
                Meta options for DummyModel.
                Set as unmanaged to prevent database table creation.
                """

                managed = False
                db_table = "dummy_table_for_init"

        self.model = DummyModel
        self.columns = [
            (_("Name"), "__str__"),
        ]
        super().__init__(**kwargs)
        self.model = None
        delattr(self, "columns")

    def get_custom_bulk_actions(self):
        """Get custom bulk actions with dynamic values"""
        object_id = getattr(self, "object_id", "")
        content_type_id = getattr(self, "content_type_id", "")
        view_id = getattr(self, "view_id", "potential-duplicates-list")

        return [
            {
                "name": "merge",
                "label": _("Merge Selected"),
                "url": reverse_lazy("duplicates:merge_duplicates_compare"),
                "method": "get",
                "icon": "fa-solid fa-code-branch",
                "bg_color": "#009dff26",
                "hover_bg_color": "#009dff",
                "text_color": "#009fff",
                "border_color": "#009dff4a",
                "hover_text_color": "white",
                "target": "#contentModalBox",
                "swap": "innerHTML",
                "onclick": "openContentModal();",
                "hx_vals": f"js:{{'object_id': '{object_id}', 'content_type_id': '{content_type_id}', 'selected_ids': JSON.stringify(selectedRecordIds('{view_id}'))}}",
            },
        ]

    @cached_property
    def custom_bulk_actions(self):
        """Cached property for custom bulk actions"""
        return self.get_custom_bulk_actions()

    def dispatch(self, request, *args, **kwargs):
        """Set up model and object before dispatch"""
        object_id = request.GET.get("object_id")
        content_type_id = request.GET.get("content_type_id")

        if content_type_id:
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
        """Get duplicate records as queryset - main object first, then duplicates"""
        if not hasattr(self, "main_object") or self.model is None:
            return QuerySet()

        duplicate_result = check_duplicates(self.main_object, is_edit=True)

        if duplicate_result.get("has_duplicates"):
            duplicate_records = duplicate_result.get("duplicate_records", [])
            pks = [self.main_object.pk] + [record.pk for record in duplicate_records]
            preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(pks)])
            return self.model.objects.filter(pk__in=pks).order_by(preserved)

        return self.model.objects.none()

    @cached_property
    def columns(self):
        """Define columns to display - show duplicate details"""
        if not hasattr(self, "model") or self.model is None:
            return [(_("Record"), "__str__")]

        try:
            columns = []

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

            field_count = 0
            for field in self.model._meta.get_fields():
                if field_count >= 5:
                    break

                if field.name in excluded_fields:
                    continue
                if not hasattr(field, "name") or getattr(field, "auto_created", False):
                    continue
                if hasattr(field, "many_to_many") and field.many_to_many:
                    continue
                if not getattr(field, "concrete", True):
                    continue
                if not getattr(field, "editable", True):
                    continue

                # Add the field
                verbose_name = (
                    getattr(field, "verbose_name", None)
                    or field.name.replace("_", " ").title()
                )
                columns.append((_(verbose_name), field.name))
                field_count += 1

            # Fallback when no user-facing fields exist
            return columns or [(_("Record"), "__str__")]
        except Exception:
            return [(_("Record"), "__str__")]

    @cached_property
    def col_attrs(self):
        """Define column attributes - make first column clickable to navigate to detail view"""

        query_params = {}
        if hasattr(self, "request") and self.request:
            if "section" in self.request.GET:
                query_params["section"] = self.request.GET.get("section")
        query_string = urlencode(query_params) if query_params else ""

        attrs = {
            "hx-get": f"{{get_detail_url}}{'?' + query_string if query_string else ''}",
            "hx-target": "#mainContent",
            "hx-swap": "outerHTML",
            "hx-push-url": "true",
            "hx-select": "#mainContent",
            "style": "cursor:pointer",
            "class": "hover:text-primary-600",
        }

        first_field_name = "__str__"
        if hasattr(self, "columns") and self.columns:
            first_field_name = self.columns[0][
                1
            ]  # Get field name from (verbose_name, field_name) tuple

        return [
            {
                first_field_name: attrs,
            }
        ]

    def get_context_data(self, **kwargs):
        """Add custom context"""
        context = super().get_context_data(**kwargs)

        context["main_object"] = getattr(self, "main_object", None)

        queryset = context.get("queryset", self.get_queryset())
        context["total_duplicates_count"] = queryset.count() if queryset else 0
        context["object_id"] = getattr(self, "object_id", None)
        context["content_type_id"] = getattr(self, "content_type_id", None)
        context["max_selection_limit"] = self.max_selection_limit
        context["show_select_three"] = True

        return context

    def get_template_names(self):
        """Override to use custom template"""
        return ["duplicates/potential_duplicates_list_view.html"]
