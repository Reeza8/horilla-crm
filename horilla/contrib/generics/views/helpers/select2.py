"""
Select2 and dynamic choice views for horilla.contrib.generics.

Provides AJAX views for select2 widgets and paginated choice loading.
"""

# Standard library imports
import importlib
import inspect
import logging

# Third-party imports (Django)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.views import View

# First party imports (Horilla)
from horilla.apps import apps
from horilla.shortcuts import render
from horilla.utils.translation import gettext_lazy as _
from horilla.web import HttpNotFound, JsonResponse

# Local imports
from ...methods import get_dynamic_form_for_model

logger = logging.getLogger(__name__)


def _is_allowed_import_module_path(module_path):
    """
    Return True only if module_path is an installed Django app or a submodule of one.
    Uses each app's full Python path (app_config.name), so paths like
    horilla.contrib.activity.forms are allowed when horilla.contrib.activity is installed.
    Used to whitelist importlib.import_module() and prevent loading arbitrary code
    from untrusted request parameters.
    """
    if not module_path or not isinstance(module_path, str):
        return False
    # Reject path traversal or obviously dangerous patterns
    if ".." in module_path or module_path.startswith("."):
        return False
    for app_config in apps.get_app_configs():
        name = app_config.name
        if module_path == name or module_path.startswith(name + "."):
            return True
    return False


class HorillaSelect2DataView(LoginRequiredMixin, View):
    """View for providing JSON data to Select2 AJAX dropdowns with search and pagination."""

    def get(self, request, *args, **kwargs):
        """
        Return JSON data for select2 AJAX queries.

        Expects `app_label` and `model_name` in `kwargs` and supports searching and
        paging parameters for select2 results.
        """
        if not request.headers.get("x-requested-with") == "XMLHttpRequest":
            return render(request, "405.html", status=405)
        app_label = kwargs.get("app_label")
        model_name = kwargs.get("model_name")
        field_name = request.GET.get("field_name")

        try:
            model = apps.get_model(app_label=app_label, model_name=model_name)
        except LookupError as e:
            raise HttpNotFound(e) from e

        search_term = request.GET.get("q", "").strip()
        ids = request.GET.get("ids", "").strip()
        page = request.GET.get("page", "1")
        dependency_value = request.GET.get("dependency_value", "").strip()
        dependency_model = request.GET.get("dependency_model", "").strip()
        dependency_field = request.GET.get("dependency_field", "").strip()
        try:
            page = int(page)
        except ValueError:
            page = 1
        per_page = 10

        queryset = None

        # Try to get queryset from filter class first (NEW CODE)
        filter_class = self._get_filter_class_from_request(
            request, app_label, model_name
        )
        if filter_class and field_name:
            try:
                # Initialize filter with request to trigger OwnerFiltersetMixin
                filterset = filter_class(request=request, data={})
                if field_name in filterset.filters:
                    filter_obj = filterset.filters[field_name]
                    if hasattr(filter_obj, "field") and hasattr(
                        filter_obj.field, "queryset"
                    ):
                        queryset = filter_obj.field.queryset
                        logger.info(
                            "[Select2] Using queryset from filter class for %s",
                            field_name,
                        )
            except Exception as e:
                logger.error("[Select2] Could not resolve queryset from filter: %s", e)

        # Fallback to form class (EXISTING CODE)
        form_class = self._get_form_class_from_request(request)
        if form_class and field_name:
            try:
                form_kwargs = {"request": request}
                # Pass instance when object_id is provided (edit mode) so OwnerQuerysetMixin
                # uses change/change_own instead of add/add_own.
                # Also temporarily set request.active_company to the instance's company so
                # the form's FK querysets are scoped to the record's tenant, not the
                # admin's currently-selected company.
                object_id = request.GET.get("object_id")
                original_active_company = getattr(request, "active_company", None)
                if (
                    object_id
                    and hasattr(form_class, "_meta")
                    and hasattr(form_class._meta, "model")
                ):
                    parent_model = form_class._meta.model
                    try:
                        instance = parent_model.all_objects.get(pk=object_id)
                        form_kwargs["instance"] = instance
                        instance_company = getattr(instance, "company", None)
                        if instance_company is not None:
                            request.active_company = instance_company
                    except (parent_model.DoesNotExist, ValueError):
                        pass
                try:
                    form = form_class(**form_kwargs)
                    if field_name in form.fields:
                        queryset = form.fields[field_name].queryset
                finally:
                    request.active_company = original_active_company
            except Exception as e:
                logger.error("[Select2] Could not resolve queryset from form: %s", e)

        if queryset is None:
            queryset = model.objects.all()

        # Apply company filtering if model has company field.
        # In edit mode, scope to the parent object's company so FK choices stay
        # within the record's tenant even when the admin's active_company differs.
        # In create mode, fall back to request.active_company.
        company = None
        edit_object_id = request.GET.get("object_id")
        if (
            edit_object_id
            and form_class
            and hasattr(form_class, "_meta")
            and hasattr(form_class._meta, "model")
        ):
            parent_model_for_company = form_class._meta.model
            try:
                parent_instance = parent_model_for_company.all_objects.get(
                    pk=edit_object_id
                )
                company = getattr(parent_instance, "company", None)
            except Exception:
                pass
        if company is None:
            company = getattr(request, "active_company", None)
        if company:
            try:
                model._meta.get_field("company")
                queryset = queryset.filter(company=company)
            except Exception:
                pass

        if dependency_value and dependency_model and dependency_field:
            try:
                dep_app_label, dep_model_name = dependency_model.split(".")
                related_model = apps.get_model(
                    app_label=dep_app_label, model_name=dep_model_name
                )

                field = model._meta.get_field(dependency_field)
                if field.related_model != related_model:
                    raise ValueError(
                        f"Field {dependency_field} does not reference {dependency_model}"
                    )

                filter_kwargs = {f"{dependency_field}__pk": dependency_value}
                queryset = queryset.filter(**filter_kwargs)
            except (ValueError, LookupError, AttributeError):
                queryset = queryset.none()

        if ids:
            try:
                id_list = [
                    int(id.strip()) for id in ids.split(",") if id.strip().isdigit()
                ]
                if id_list:
                    queryset = queryset.filter(pk__in=id_list)
                    results = [
                        {
                            "id": obj.pk,
                            "text": str(obj) or f"Unnamed {model_name} {obj.pk}",
                        }
                        for obj in queryset
                    ]
                    return JsonResponse(
                        {"results": results, "pagination": {"more": False}}
                    )
                # else:
                return JsonResponse({"results": [], "pagination": {"more": False}})
            except Exception:
                return JsonResponse({"results": [], "pagination": {"more": False}})

        if search_term:
            search_term_lower = search_term.lower()
            matched_ids = [
                obj.pk for obj in queryset if search_term_lower in str(obj).lower()
            ]
            queryset = queryset.filter(pk__in=matched_ids)
        else:
            queryset = queryset.order_by("pk")

        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)

        results = [
            {"id": obj.pk, "text": str(obj) or f"Unnamed {model_name} {obj.pk}"}
            for obj in page_obj.object_list
        ]

        return JsonResponse(
            {"results": results, "pagination": {"more": page_obj.has_next()}}
        )

    def _get_filter_class_from_request(self, request, app_label, model_name):
        """
        Get the filter class for the model.

        Discovery order:
        1. Explicit filter_class parameter from request
        2. Search all FilterSet classes in filters module and match by Meta.model
        """
        filter_path = request.GET.get("filter_class")
        if filter_path:
            try:
                module_path, class_name = filter_path.rsplit(".", 1)
                if not _is_allowed_import_module_path(module_path):
                    logger.warning(
                        "[Select2] Rejected disallowed filter_class module path: %s",
                        module_path,
                    )
                else:
                    module = importlib.import_module(module_path)
                    return getattr(module, class_name)
            except Exception as e:
                logger.error(
                    "[Select2] Could not import filter_class %s: %s", filter_path, e
                )

        # Search all FilterSet classes in the module and match by Meta.model.
        # Use the app's full Python path (app_config.name) so paths like
        # horilla.contrib.activity.filters are used when app_label is "activity".
        try:
            try:
                app_config = apps.get_app_config(app_label)
                filters_module_path = f"{app_config.name}.filters"
            except LookupError:
                filters_module_path = f"{app_label}.filters"
            if not _is_allowed_import_module_path(filters_module_path):
                logger.warning(
                    "[Select2] Rejected disallowed filters module path: %s",
                    filters_module_path,
                )
            else:
                filters_module = importlib.import_module(filters_module_path)
                import django_filters

                model = apps.get_model(app_label=app_label, model_name=model_name)

                for name, obj in inspect.getmembers(filters_module, inspect.isclass):
                    # Check if it's a FilterSet subclass (but not FilterSet itself)
                    if (
                        issubclass(obj, django_filters.FilterSet)
                        and obj is not django_filters.FilterSet
                    ):
                        # Check if Meta.model matches the requested model
                        if hasattr(obj, "Meta") and hasattr(obj.Meta, "model"):
                            if obj.Meta.model == model:
                                logger.info(
                                    "[Select2] Found filter class by model match: %s",
                                    name,
                                )
                                return obj
        except Exception as e:
            logger.debug("[Select2] Could not auto-discover filter class: %s", e)

        return None

    def _get_form_class_from_request(self, request):
        """
        Resolve which form is being used from form_class query param.
        DynamicForm is created inside get_form_class() and is not importable;
        when form_path contains DynamicForm, resolve via get_dynamic_form_for_model
        using parent_model  - works for any model, no per-model code.
        """
        form_path = request.GET.get("form_class")
        if not form_path:
            return None
        if "DynamicForm" in form_path:
            parent_model_path = request.GET.get("parent_model", "").strip()
            if parent_model_path and "." in parent_model_path:
                try:
                    p_app, p_model = parent_model_path.rsplit(".", 1)
                    parent_model = apps.get_model(app_label=p_app, model_name=p_model)
                    return get_dynamic_form_for_model(parent_model)
                except (LookupError, ValueError) as e:
                    logger.debug(
                        "[Select2] Could not resolve DynamicForm for parent_model %s: %s",
                        parent_model_path,
                        e,
                    )
            return None
        try:
            module_path, class_name = form_path.rsplit(".", 1)
            if not _is_allowed_import_module_path(module_path):
                logger.warning(
                    "[Select2] Rejected disallowed form_class module path: %s",
                    module_path,
                )
                return None
            module = importlib.import_module(module_path)
            return getattr(module, class_name)
        except Exception as e:
            logger.error("[Select2] Could not import form_class %s: %s", form_path, e)
            return None
