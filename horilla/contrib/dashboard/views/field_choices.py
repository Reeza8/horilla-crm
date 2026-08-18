"""Views for providing field choices based on selected modules in dashboard."""

# Standard library imports
import logging

# Third-party imports (Django)
from django.utils.encoding import force_str

# First party imports (Horilla)
from horilla.apps import apps
from horilla.contrib.core.models import HorillaContentType
from horilla.shortcuts import render
from horilla.utils.choices import DISPLAYABLE_FIELD_TYPES
from horilla.utils.decorators import (
    htmx_required,
    method_decorator,
    permission_required_or_denied,
)
from horilla.utils.translation import gettext_lazy as _
from horilla.views.generic import View
from horilla.web import HttpResponse

# Local imports
from ..forms import get_dashboard_component_models

logger = logging.getLogger(__name__)


def _resolve_model_from_module(module):
    """
    Resolve model class from module param (content type pk or registry key).
    Prefer dashboard registry so we match the same model as the module dropdown.
    """
    if not module:
        return None
    if module.isdigit():
        try:
            content_type = HorillaContentType.objects.get(pk=module)
            module = content_type.model
        except HorillaContentType.DoesNotExist:
            return None
    module_key = (module or "").strip().lower()
    if not module_key:
        return None
    for key, model_cls in get_dashboard_component_models():
        if key == module_key:
            return model_cls
    # Fallback: first app with this model name
    for app_config in apps.get_app_configs():
        try:
            return apps.get_model(app_label=app_config.label, model_name=module_key)
        except LookupError:
            continue
    return None


def _append_grouping_choice(grouping_fields, field_name, field_label):
    """Append (name, str_label) so templates/JSON never get lazy __proxy__."""
    grouping_fields.append((field_name, force_str(field_label)))


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("dashboard.add_dashboard"), name="dispatch"
)
class ModuleFieldChoicesView(View):
    """
    Class-based view to return field choices for a selected module via HTMX.
    """

    def get(self, request, *args, **kwargs):
        """
        Handle GET request to return a <select> element with field choices.
        """
        module = request.GET.get("module")
        row_id = request.GET.get("row_id", "0")
        if not row_id.isdigit():
            row_id = "0"

        field_name = f"field_{row_id}"
        field_id = f"id_field_{row_id}"

        if module and module.isdigit():
            try:
                content_type = HorillaContentType.objects.get(pk=module)
                module = content_type.model
            except HorillaContentType.DoesNotExist:
                pass

        if not module:
            return render(
                request,
                "partials/field_select_empty.html",
                {"field_name": field_name, "field_id": field_id},
            )

        try:
            model = None
            for app_config in apps.get_app_configs():
                try:
                    model = apps.get_model(
                        app_label=app_config.label, model_name=module.lower()
                    )
                    break
                except LookupError:
                    continue
            if not model:
                return render(
                    request,
                    "partials/field_select_empty.html",
                    {"field_name": field_name, "field_id": field_id},
                )
        except Exception:
            return render(
                request,
                "partials/field_select_empty.html",
                {"field_name": field_name, "field_id": field_id},
            )
        model_fields = []
        for field in model._meta.get_fields():
            if field.concrete or field.is_relation:
                verbose_name = getattr(field, "verbose_name", field.name)
                if field.is_relation:
                    verbose_name = f"{verbose_name}"
                model_fields.append((field.name, verbose_name))

        field_choices = [("", "Select Field")] + model_fields

        return render(
            request,
            "partials/module_field_select.html",
            {
                "field_name": field_name,
                "field_id": field_id,
                "row_id": row_id,
                "model_name": module,
                "field_choices": field_choices,
            },
        )


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("dashboard.add_dashboard"), name="dispatch"
)
class ColumnFieldChoicesView(View):
    """
    View to return metric field choices for a selected module via HTMX.
    """

    def get(self, request, *args, **kwargs):
        """Handle GET request to return a <select> element with column field choices."""
        module = request.GET.get("module")

        if not module:
            return HttpResponse(
                '<select name="columns" id="id_columns" class="js-example-basic-multiple headselect" multiple ><option value="">---------</option></select>'
            )

        model = _resolve_model_from_module(module)
        if not model:
            return render(
                request,
                "partials/column_field_select_empty.html",
            )

        column_fields = []
        for field in model._meta.get_fields():
            if field.concrete and not field.is_relation:
                field_name = field.name
                field_label = field.verbose_name or field.name

                if hasattr(field, "get_internal_type"):
                    field_type = field.get_internal_type()
                    if field_type in DISPLAYABLE_FIELD_TYPES:
                        column_fields.append((field_name, field_label))
                    elif hasattr(field, "choices") and field.choices:
                        column_fields.append((field_name, f"{field_label}"))
            # Include ForeignKey fields for grouping
            elif hasattr(field, "related_model") and field.many_to_one:
                field_name = field.name
                field_label = field.verbose_name or field.name
                column_fields.append((field_name, f"{field_label}"))

        field_choices = [("", "Add Columns")] + column_fields

        return render(
            request,
            "partials/column_field_select.html",
            {"field_choices": field_choices},
        )


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("dashboard.add_dashboard"), name="dispatch"
)
class GroupingFieldChoicesView(View):
    """
    View to return grouping field choices for a selected module via HTMX.
    """

    def get(self, request, *args, **kwargs):
        """Handle GET request to return a <select> element with grouping field choices."""
        module = request.GET.get("module")
        current_grouping = (request.GET.get("grouping_field") or "").strip()

        model = _resolve_model_from_module(module)
        if not model:
            return render(
                request,
                "partials/grouping_field_select_empty.html",
            )

        # Get fields suitable for grouping (labels forced to str for JSON/template safety)
        grouping_fields = []
        for field in model._meta.get_fields():
            if field.concrete and not field.is_relation:
                field_name = field.name
                field_label = field.verbose_name or field.name

                if hasattr(field, "get_internal_type"):
                    field_type = field.get_internal_type()
                    if field_type in DISPLAYABLE_FIELD_TYPES:
                        _append_grouping_choice(
                            grouping_fields, field_name, field_label
                        )
                    elif hasattr(field, "choices") and field.choices:
                        _append_grouping_choice(
                            grouping_fields, field_name, f"{field_label}"
                        )

            # Include ForeignKey fields for grouping
            elif hasattr(field, "related_model") and field.many_to_one:
                field_name = field.name
                field_label = field.verbose_name or field.name
                _append_grouping_choice(grouping_fields, field_name, field_label)

        field_choices = [("", force_str(_("Select Grouping Field")))] + grouping_fields

        return render(
            request,
            "partials/grouping_field_select.html",
            {
                "field_choices": field_choices,
                "current_grouping": current_grouping,
            },
        )


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("dashboard.add_dashboard"), name="dispatch"
)
class SecondaryGroupingFieldChoicesView(View):
    """
    View to return secondary grouping field choices for a selected module via HTMX.
    """

    def get(self, request, *args, **kwargs):
        """Handle GET request to return a <select> element with secondary grouping field choices."""
        module = request.GET.get("module")
        current_secondary = (request.GET.get("secondary_grouping") or "").strip()

        model = _resolve_model_from_module(module)
        if not model:
            return render(
                request,
                "partials/secondary_grouping_field_select_empty.html",
            )

        grouping_fields = []
        for field in model._meta.get_fields():
            if field.concrete and not field.is_relation:
                field_name = field.name
                field_label = field.verbose_name or field.name

                if hasattr(field, "get_internal_type"):
                    field_type = field.get_internal_type()
                    if field_type in DISPLAYABLE_FIELD_TYPES:
                        _append_grouping_choice(
                            grouping_fields, field_name, field_label
                        )
                    elif hasattr(field, "choices") and field.choices:
                        _append_grouping_choice(
                            grouping_fields, field_name, f"{field_label}"
                        )

            elif hasattr(field, "related_model") and field.many_to_one:
                field_name = field.name
                field_label = field.verbose_name or field.name
                _append_grouping_choice(grouping_fields, field_name, field_label)

        field_choices = [
            ("", force_str(_("Select Secondary Grouping Field")))
        ] + grouping_fields

        return render(
            request,
            "partials/secondary_grouping_field_select.html",
            {
                "field_choices": field_choices,
                "current_secondary": current_secondary,
            },
        )


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("dashboard.add_dashboard"), name="dispatch"
)
class MetricFieldChoicesView(View):
    """
    View to return metric type choices for KPI components based on the selected module.
    """

    def get(self, request, *args, **kwargs):
        """
        Build choices like:
        - Count of records
        - Sum/Average/Minimum/Maximum of each numeric field on the model.
        Only active when component_type == 'kpi'.
        """
        _component_type = (request.GET.get("component_type") or "").strip()

        module = request.GET.get("module")
        current_metric = (request.GET.get("metric_type") or "").strip()

        model = _resolve_model_from_module(module)
        metric_choices = [("count", "Count of records")]

        if model:
            numeric_internal_types = {
                "IntegerField",
                "BigIntegerField",
                "SmallIntegerField",
                "PositiveIntegerField",
                "PositiveSmallIntegerField",
                "DecimalField",
                "FloatField",
            }

            for field in model._meta.get_fields():
                if not getattr(field, "concrete", False) or getattr(
                    field, "is_relation", False
                ):
                    continue

                field_type = (
                    field.get_internal_type()
                    if hasattr(field, "get_internal_type")
                    else ""
                )

                if field_type not in numeric_internal_types:
                    continue

                field_name = field.name
                field_label = getattr(field, "verbose_name", field_name)
                field_label_str = force_str(field_label)

                metric_choices.extend(
                    [
                        (f"sum__{field_name}", f"Sum of {field_label_str}"),
                        (f"average__{field_name}", f"Average of {field_label_str}"),
                        (f"min__{field_name}", f"Minimum of {field_label_str}"),
                        (f"max__{field_name}", f"Maximum of {field_label_str}"),
                    ]
                )

        # Ensure the currently selected metric is always included
        if current_metric and current_metric not in {v for v, _ in metric_choices}:
            parts = current_metric.split("__", 1)
            if len(parts) == 2:
                agg_key, field_name = parts
                agg_label = (
                    "Average"
                    if agg_key == "average"
                    else agg_key.replace("_", " ").title()
                )
                field_label = field_name.replace("_", " ").title()
                label = f"{agg_label} of {field_label}"
            else:
                label = current_metric.replace("_", " ").title()
            metric_choices.append((current_metric, label))

        return render(
            request,
            "partials/metric_field_select.html",
            {
                "field_choices": metric_choices,
                "current_metric": current_metric or "count",
            },
        )


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("dashboard.add_dashboard"), name="dispatch"
)
class YAxisMetricFieldChoicesView(View):
    """
    View to return y-axis metric type choices for chart components based on the selected module.
    Uses the same logic as MetricFieldChoicesView but binds to the y_axis_metric_type field.
    """

    def get(self, request, *args, **kwargs):
        """Method to handle GET request and return metric choices for y-axis based on the selected module."""
        component_type = (request.GET.get("component_type") or "").strip()
        # Only charts use the dedicated y-axis metric; others fall back to simple count.
        if component_type != "chart":
            metric_choices = [("count", "Count of records")]
            current_metric = (request.GET.get("y_axis_metric_type") or "").strip()
            return render(
                request,
                "partials/y_axis_metric_field_select.html",
                {
                    "field_choices": metric_choices,
                    "current_metric": current_metric or "count",
                },
            )

        module = request.GET.get("module")
        current_metric = (request.GET.get("y_axis_metric_type") or "").strip()

        model = _resolve_model_from_module(module)
        metric_choices = [("count", "Count of records")]

        if model:
            numeric_internal_types = {
                "IntegerField",
                "BigIntegerField",
                "SmallIntegerField",
                "PositiveIntegerField",
                "PositiveSmallIntegerField",
                "DecimalField",
                "FloatField",
            }

            for field in model._meta.get_fields():
                if not getattr(field, "concrete", False) or getattr(
                    field, "is_relation", False
                ):
                    continue

                field_type = (
                    field.get_internal_type()
                    if hasattr(field, "get_internal_type")
                    else ""
                )

                if field_type not in numeric_internal_types:
                    continue

                field_name = field.name
                field_label = getattr(field, "verbose_name", field_name)
                field_label_str = force_str(field_label)

                metric_choices.extend(
                    [
                        (f"sum__{field_name}", f"Sum of {field_label_str}"),
                        (f"average__{field_name}", f"Average of {field_label_str}"),
                        (f"min__{field_name}", f"Minimum of {field_label_str}"),
                        (f"max__{field_name}", f"Maximum of {field_label_str}"),
                    ]
                )

        if current_metric and current_metric not in {v for v, _ in metric_choices}:
            parts = current_metric.split("__", 1)
            if len(parts) == 2:
                agg_key, field_name = parts
                agg_label = (
                    "Average"
                    if agg_key == "average"
                    else agg_key.replace("_", " ").title()
                )
                field_label = field_name.replace("_", " ").title()
                label = f"{agg_label} of {field_label}"
            else:
                label = current_metric.replace("_", " ").title()
            metric_choices.append((current_metric, label))

        return render(
            request,
            "partials/y_axis_metric_field_select.html",
            {
                "field_choices": metric_choices,
                "current_metric": current_metric or "count",
            },
        )
