"""
User picker views for horilla.contrib.generics.

Provides HTMX endpoints for the user picker modal:
 - UserPickerFilterView  : filter panel (add row / field change / operator change)
 - UserPickerListView    : paginated list of items with search + filter applied
"""

# Standard library imports
import importlib
import logging

# Third-party imports (Django)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.views import View

# First party imports (Horilla)
from horilla.apps import apps
from horilla.shortcuts import render
from horilla.utils.choices import FIELD_TYPE_MAP
from horilla.web import HttpResponse

logger = logging.getLogger(__name__)


def _get_model_fields(model):
    """Return filter-field metadata for a model."""
    from horilla.contrib.generics.filters import HorillaFilterSet

    fields = []
    for field in model._meta.fields:
        field_class = field.__class__.__name__
        if field.choices:
            ftype = "choice"
            choices = [{"value": v, "label": l} for v, l in field.choices]
        elif field_class == "ForeignKey":
            ftype = "foreignkey"
            choices = []
        elif field_class == "DateTimeField":
            ftype = "datetime"
            choices = []
        elif field_class == "DateField":
            ftype = "date"
            choices = []
        elif field_class == "BooleanField":
            ftype = "boolean"
            choices = [
                {"value": "True", "label": "Yes"},
                {"value": "False", "label": "No"},
            ]
        else:
            ftype = FIELD_TYPE_MAP.get(field_class, "other")
            choices = []

        operators = HorillaFilterSet.get_operators_for_field(ftype)
        fields.append(
            {
                "name": field.name,
                "verbose_name": str(field.verbose_name).title(),
                "type": ftype,
                "choices": choices,
                "operators": operators,
                "model": (
                    field.related_model.__name__ if ftype == "foreignkey" else None
                ),
                "app_label": (
                    field.related_model._meta.app_label
                    if ftype == "foreignkey"
                    else None
                ),
            }
        )
    return fields


def _apply_filters(queryset, request):
    """Apply field/operator/value triples from GET params to queryset."""
    from django.db.models import Q

    from horilla.contrib.generics.filters import (
        OPERATOR_CHOICES,
        RELATIVE_DATE_OPERATORS,
        STRING_LIKE_FIELDS,
        HorillaFilterSet,
    )

    valid_operators = {op for ops in OPERATOR_CHOICES.values() for op, _ in ops}

    fields = request.GET.getlist("field")
    operators = request.GET.getlist("operator")
    values = request.GET.getlist("value")
    starts = request.GET.getlist("start_value")
    ends = request.GET.getlist("end_value")

    model = queryset.model

    for i, (fname, op) in enumerate(zip(fields, operators)):
        if not fname or op not in valid_operators:
            continue
        try:
            if op == "ne":
                v = values[i] if i < len(values) else None
                if v is not None:
                    queryset = queryset.exclude(**{fname: v})
            elif op == "between":
                s = starts[i] if i < len(starts) else None
                e = ends[i] if i < len(ends) else None
                if s and e:
                    queryset = queryset.filter(
                        **{f"{fname}__gte": s, f"{fname}__lte": e}
                    )
                elif s:
                    queryset = queryset.filter(**{f"{fname}__gte": s})
                elif e:
                    queryset = queryset.filter(**{f"{fname}__lte": e})
            elif op == "isnull":
                try:
                    fobj = model._meta.get_field(fname)
                    if isinstance(fobj, STRING_LIKE_FIELDS):
                        queryset = queryset.filter(
                            Q(**{f"{fname}__isnull": True})
                            | Q(**{f"{fname}__exact": ""})
                        )
                    else:
                        queryset = queryset.filter(**{f"{fname}__isnull": True})
                except Exception:
                    queryset = queryset.filter(**{f"{fname}__isnull": True})
            elif op == "isnotnull":
                try:
                    fobj = model._meta.get_field(fname)
                    if isinstance(fobj, STRING_LIKE_FIELDS):
                        queryset = queryset.filter(
                            ~Q(**{f"{fname}__isnull": True})
                            & ~Q(**{f"{fname}__exact": ""})
                        )
                    else:
                        queryset = queryset.filter(**{f"{fname}__isnull": False})
                except Exception:
                    queryset = queryset.filter(**{f"{fname}__isnull": False})
            elif op in RELATIVE_DATE_OPERATORS:
                queryset = HorillaFilterSet()._apply_relative_date_filter(
                    queryset, fname, op
                )
            else:
                v = values[i] if i < len(values) else None
                if v is not None:
                    queryset = queryset.filter(**{f"{fname}__{op}": v})
        except Exception:
            pass

    return queryset


class UserPickerModalView(LoginRequiredMixin, View):
    """Returns full modal content for the user picker, loaded into horillaModalBox via hx-get."""

    def get(self, request, **kwargs):
        """Render the full user-picker modal shell for HTMX injection."""
        app_label = kwargs.get("app_label")
        model_name = kwargs.get("model_name")
        field_id = request.GET.get("field_id", "")
        field_label = request.GET.get("field_label", "Select")
        form_class = request.GET.get("form_class", "")
        field_name = request.GET.get("field_name", "")

        try:
            apps.get_model(app_label=app_label, model_name=model_name)
        except LookupError:
            return HttpResponse("Model not found", status=404)

        extra_qs = ""
        if form_class and field_name:
            from urllib.parse import urlencode

            extra_qs = "?" + urlencode(
                {"form_class": form_class, "field_name": field_name}
            )

        context = {
            "field_id": field_id,
            "field_label": field_label,
            "list_url": f"/generics/user-picker-list/{app_label}/{model_name}/{extra_qs}",
            "filter_url": f"/generics/user-picker-filter/{app_label}/{model_name}/",
            "app_label": app_label,
            "model_name": model_name,
        }
        return render(request, "partials/user_picker_modal.html", context)


class UserPickerListView(LoginRequiredMixin, View):
    """
    HTMX endpoint: returns a paginated HTML list of model items for the user picker modal.
    Accepts: search, field[], operator[], value[], start_value[], end_value[], page.
    """

    def _resolve_queryset(self, request, model):
        """Try to get a filtered queryset from the form field's queryset, fall back to all()."""
        from .select2 import _is_allowed_import_module_path

        form_class_path = request.GET.get("form_class", "").strip()
        field_name = request.GET.get("field_name", "").strip()
        if form_class_path and field_name:
            try:
                module_path, class_name = form_class_path.rsplit(".", 1)
                if _is_allowed_import_module_path(module_path):
                    module = importlib.import_module(module_path)
                    form_class = getattr(module, class_name)
                    form = form_class(request=request)
                    if field_name in form.fields:
                        qs = getattr(form.fields[field_name], "queryset", None)
                        if qs is not None:
                            return qs
            except Exception as e:
                logger.debug("[UserPicker] Could not resolve queryset from form: %s", e)
        return model.objects.all()

    def get(self, request, **kwargs):
        """Return a paginated HTML list slice for the picker, with search and filters applied."""
        app_label = kwargs.get("app_label")
        model_name = kwargs.get("model_name")

        try:
            model = apps.get_model(app_label=app_label, model_name=model_name)
        except LookupError:
            return HttpResponse("Model not found", status=404)

        queryset = self._resolve_queryset(request, model)

        # Apply search
        search = request.GET.get("search", "").strip()
        if search:
            matched_pks = [
                obj.pk for obj in queryset if search.lower() in str(obj).lower()
            ]
            queryset = queryset.filter(pk__in=matched_pks)

        # Apply filters
        queryset = _apply_filters(queryset, request)

        # Pagination
        per_page = 20
        try:
            page = int(request.GET.get("page", 1))
        except ValueError:
            page = 1

        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)

        items = [{"id": obj.pk, "text": str(obj)} for obj in page_obj.object_list]

        context = {
            "items": items,
            "page_obj": page_obj,
            "app_label": app_label,
            "model_name": model_name,
        }
        return render(request, "partials/user_picker_list.html", context)


class UserPickerFilterView(LoginRequiredMixin, View):
    """
    HTMX endpoint for the user picker modal filter panel.
    Handles: add_filter_row, field_change, operator_change, initial row render.
    """

    def get(self, request, **kwargs):
        """Render filter rows or field/operator UI fragments for the user picker."""
        app_label = kwargs.get("app_label")
        model_name = kwargs.get("model_name")

        try:
            model = apps.get_model(app_label=app_label, model_name=model_name)
        except LookupError:
            return HttpResponse("Model not found", status=404)

        filter_url = request.path
        filter_fields = _get_model_fields(model)

        # ── Add a new empty row ───────────────────────────────────────────────
        if request.GET.get("add_filter_row") == "true":
            row_id = int(request.GET.get("row_id", 0)) + 1
            context = {
                "filter_rows": [
                    {
                        "row_id": row_id,
                        "field": None,
                        "operator": None,
                        "value": None,
                        "operators": [],
                        "type": None,
                        "choices": [],
                    }
                ],
                "filter_fields": filter_fields,
                "up_filter_url": filter_url,
            }
            return render(request, "partials/user_picker_filter_row.html", context)

        # ── Field changed → return new operator select ────────────────────────
        if request.GET.get("field_change") == "true":
            field_name = request.GET.get("field", "")
            row_id = request.GET.get("row_id", "0")
            field_info = next(
                (f for f in filter_fields if f["name"] == field_name), None
            )
            operators = field_info["operators"] if field_info else []
            context = {
                "operators": operators,
                "field_name": field_name,
                "row_id": row_id,
                "up_filter_url": filter_url,
            }
            return render(request, "partials/user_picker_operator_select.html", context)

        # ── Operator changed → return new value field ─────────────────────────
        if request.GET.get("operator_change") == "true":
            field_name = request.GET.get("field", "")
            operator = request.GET.get("operator", "")
            row_id = request.GET.get("row_id", "0")
            field_info = next(
                (f for f in filter_fields if f["name"] == field_name), None
            )
            context = {
                "field_info": field_info or {},
                "operator": operator,
                "row_id": row_id,
                "app_label": app_label,
                "model_name": model_name,
            }
            return render(request, "partials/user_picker_value_field.html", context)

        # ── Initial render (row 0) ────────────────────────────────────────────
        context = {
            "filter_rows": [
                {
                    "row_id": 0,
                    "field": None,
                    "operator": None,
                    "value": None,
                    "operators": [],
                    "type": None,
                    "choices": [],
                }
            ],
            "filter_fields": filter_fields,
            "up_filter_url": filter_url,
        }
        return render(request, "partials/user_picker_filter_row.html", context)
