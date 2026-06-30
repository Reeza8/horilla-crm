"""
Bulk delete mixin extracted from HorillaListView to keep the main
list view class smaller and focused.
"""

# Standard library imports
import json
import logging
from functools import reduce
from operator import or_

# Third-party imports (Django)
from django.contrib import messages

from horilla.contrib.core.models import RecycleBin

# First party imports (Horilla)
from horilla.db.models import Q
from horilla.shortcuts import render
from horilla.utils.translation import gettext_lazy as _
from horilla.web import HttpResponse

logger = logging.getLogger(__name__)


class HorillaBulkDeleteMixin:
    """
    Mixin that encapsulates all bulk delete–related logic so it can be kept
    separate from the main list view responsibilities.
    """

    def handle_bulk_delete_post(self, request, action, record_ids, delete_type):
        """
        Handle all bulk delete–related POST branches.

        Returns an HttpResponse when the request was handled here, otherwise None.
        """
        # Delete mode selection (hard/soft)
        if request.POST.get("delete_mode_form") == "true":
            selected_ids = request.POST.get("selected_ids", "[]")
            try:
                selected_ids = json.loads(selected_ids)
                selected_ids = [int(id) for id in selected_ids if str(id).isdigit()]
                valid_ids = (
                    self.get_queryset()
                    .filter(id__in=selected_ids)
                    .values_list("id", flat=True)
                )
                valid_ids = list(valid_ids)

                self.object_list = self.get_queryset()
                context = self.get_context_data()
                context["selected_ids"] = valid_ids
                context["selected_ids_json"] = json.dumps(valid_ids)
                if not valid_ids:
                    messages.error(request, _("No rows selected for deletion."))
                    return HttpResponse("<script>$('#reloadButton').click();</script>")
                return render(request, "partials/delete_mode_form.html", context)
            except (json.JSONDecodeError, ValueError) as e:
                logger.error("Error processing selected_ids: %s", str(e))
                self.object_list = self.get_queryset()
                context = self.get_context_data()
                context["selected_ids"] = []
                context["selected_ids_json"] = json.dumps([])
                return render(request, "partials/delete_mode_form.html", context)

        # Bulk delete form rendering for hard delete
        if request.POST.get("bulk_delete_form") == "true":
            selected_ids = request.POST.get("selected_ids", "[]")
            try:
                selected_ids = json.loads(selected_ids)
                selected_ids = [int(id) for id in selected_ids if str(id).isdigit()]
                valid_ids = (
                    self.get_queryset()
                    .filter(id__in=selected_ids)
                    .values_list("id", flat=True)
                )
                valid_ids = list(valid_ids)

                cannot_delete, can_delete, _dependency_details = (
                    HorillaBulkDeleteMixin._check_dependencies(self, valid_ids)
                )
                self.object_list = self.get_queryset()
                context = self.get_context_data()
                context.update(
                    {
                        "selected_ids": valid_ids,
                        "selected_ids_json": json.dumps(valid_ids),
                        "cannot_delete": cannot_delete,
                        "can_delete": can_delete,
                        "cannot_delete_count": len(cannot_delete),
                        "can_delete_count": len(can_delete),
                        "model_verbose_name": self.model._meta.verbose_name_plural,
                    }
                )
                return render(request, "partials/bulk_delete_form.html", context)
            except (json.JSONDecodeError, ValueError) as e:
                logger.error("Error processing selected_ids: %s", str(e))
                self.object_list = self.get_queryset()
                context = self.get_context_data()
                context.update(
                    {
                        "selected_ids": [],
                        "selected_ids_json": json.dumps([]),
                        "cannot_delete": [],
                        "can_delete": [],
                        "cannot_delete_count": 0,
                        "can_delete_count": 0,
                        "error_message": "Invalid selected IDs provided.",
                        "model_verbose_name": self.model._meta.verbose_name_plural,
                    }
                )
                return render(request, "partials/bulk_delete_form.html", context)

        # Bulk delete form rendering for soft delete
        if request.POST.get("soft_delete_form") == "true":
            selected_ids = request.POST.get("selected_ids", "[]")
            try:
                selected_ids = json.loads(selected_ids)
                selected_ids = [int(id) for id in selected_ids if str(id).isdigit()]
                valid_ids = (
                    self.get_queryset()
                    .filter(id__in=selected_ids)
                    .values_list("id", flat=True)
                )
                valid_ids = list(valid_ids)

                cannot_delete, can_delete, _dependency_details = (
                    HorillaBulkDeleteMixin._check_dependencies(self, valid_ids)
                )
                self.object_list = self.get_queryset()
                context = self.get_context_data()
                context.update(
                    {
                        "selected_ids": valid_ids,
                        "selected_ids_json": json.dumps(valid_ids),
                        "cannot_delete": cannot_delete,
                        "can_delete": can_delete,
                        "cannot_delete_count": len(cannot_delete),
                        "can_delete_count": len(can_delete),
                        "model_verbose_name": self.model._meta.verbose_name_plural,
                    }
                )
                return render(request, "partials/soft_delete_form.html", context)
            except (json.JSONDecodeError, ValueError) as e:
                logger.error("Error processing selected_ids: %s", str(e))
                self.object_list = self.get_queryset()
                context = self.get_context_data()
                context.update(
                    {
                        "selected_ids": [],
                        "selected_ids_json": json.dumps([]),
                        "cannot_delete": [],
                        "can_delete": [],
                        "cannot_delete_count": 0,
                        "can_delete_count": 0,
                        "error_message": "Invalid selected IDs provided.",
                        "model_verbose_name": self.model._meta.verbose_name_plural,
                    }
                )
                return render(request, "partials/soft_delete_form.html", context)

        # Confirm or re-render bulk delete
        if action == "bulk_delete" and record_ids:
            try:
                record_ids_list = json.loads(record_ids)

                # Enforce delete_own permission: restrict to owned records only
                # when the user lacks the global delete permission.
                app_label = self.model._meta.app_label
                model_name = self.model._meta.model_name
                delete_perm = f"{app_label}.delete_{model_name}"
                delete_own_perm = f"{app_label}.delete_own_{model_name}"

                if not request.user.has_perm(delete_perm) and request.user.has_perm(
                    delete_own_perm
                ):
                    owner_fields = getattr(self.model, "OWNER_FIELDS", None)
                    if owner_fields:
                        ownership_query = reduce(
                            or_,
                            (Q(**{field: request.user}) for field in owner_fields),
                            Q(),
                        )
                        allowed_ids = (
                            self.get_queryset()
                            .filter(id__in=record_ids_list)
                            .filter(ownership_query)
                            .values_list("id", flat=True)
                        )
                        skipped_count = len(record_ids_list) - len(allowed_ids)
                        record_ids_list = list(allowed_ids)
                    else:
                        skipped_count = 0
                else:
                    skipped_count = 0

                cannot_delete, can_delete, _dependency_details = (
                    HorillaBulkDeleteMixin._check_dependencies(self, record_ids_list)
                )

                if request.POST.get("confirm_delete") == "true":
                    try:
                        can_delete_ids = [item["id"] for item in can_delete]
                        individual_view_id = request.POST.get("view_id", "")

                        if delete_type == "soft":
                            deleted_count = HorillaBulkDeleteMixin._perform_soft_delete(
                                self, can_delete_ids
                            )
                            if skipped_count > 0:
                                messages.warning(
                                    request,
                                    f"Successfully soft deleted {deleted_count} record(s). {skipped_count} record(s) were skipped because you do not have permission to delete them.",
                                )
                            else:
                                messages.success(
                                    request,
                                    f"Successfully soft deleted {deleted_count} records.",
                                )
                            return HttpResponse(
                                f"<script>$('#reloadButton').click();closeModal();$('#unselect-all-btn-{individual_view_id}').click();</script>"
                            )

                        if delete_type == "hard_non_dependent":
                            deleted_count = self.model.objects.filter(
                                id__in=can_delete_ids
                            ).delete()[0]
                            if skipped_count > 0:
                                messages.warning(
                                    request,
                                    f"Successfully hard deleted {deleted_count} record(s). {skipped_count} record(s) were skipped because you do not have permission to delete them.",
                                )
                            else:
                                messages.success(
                                    request,
                                    f"Successfully hard deleted {deleted_count} records.",
                                )
                            return HttpResponse(
                                f"<script>$('#reloadButton').click();$('#unselect-all-btn-{individual_view_id}').click();</script>"
                            )
                    except Exception as e:
                        logger.error("Delete failed: %s", str(e))
                        messages.error(request, f"Delete failed: {str(e)}")
                        return HttpResponse(
                            "<script>$('#reloadButton').click();</script>"
                        )

                # Render the bulk delete form with dependency information
                self.object_list = self.get_queryset()
                context = self.get_context_data()
                context.update(
                    {
                        "selected_ids": record_ids_list,
                        "cannot_delete": cannot_delete,
                        "can_delete": can_delete,
                        "cannot_delete_count": len(cannot_delete),
                        "can_delete_count": len(can_delete),
                        "selected_ids_json": json.dumps(record_ids_list),
                        "model_verbose_name": self.model._meta.verbose_name_plural,
                    }
                )
                return render(request, "partials/bulk_delete_form.html", context)
            except json.JSONDecodeError as e:
                logger.error("JSON decode error: %s", e)
                return HttpResponse("Invalid JSON data for record_ids", status=400)

        # Delete a single dependency for one record (hard or soft)
        if action == "delete_item_with_dependencies" and request.POST.get("record_id"):
            try:
                item_id = int(request.POST.get("record_id"))
                selected_ids = json.loads(request.POST.get("selected_ids", "[]"))
                selected_data = [int(id) for id in selected_ids] if selected_ids else []
                is_soft = request.POST.get("delete_type") == "soft"
                if is_soft:
                    context = (
                        HorillaBulkDeleteMixin._soft_delete_item_with_dependencies(
                            self, item_id, record_ids, selected_data
                        )
                    )
                    return render(request, "partials/soft_delete_form.html", context)
                context = HorillaBulkDeleteMixin._delete_item_with_dependencies(
                    self, item_id, record_ids, selected_data
                )
                return render(request, "partials/bulk_delete_form.html", context)
            except json.JSONDecodeError as e:
                logger.error("JSON decode error: %s", e)
                self.object_list = self.get_queryset()
                context = self.get_context_data()
                context["error_message"] = "Invalid JSON data for record_ids."
                template = (
                    "partials/soft_delete_form.html"
                    if request.POST.get("delete_type") == "soft"
                    else "partials/bulk_delete_form.html"
                )
                return render(request, template, context)

        # Delete all dependencies for one record (hard or soft)
        if action == "delete_all_dependencies" and request.POST.get("record_id"):
            try:
                item_id = int(request.POST.get("record_id"))
                selected_ids = json.loads(request.POST.get("selected_ids", "[]"))
                selected_data = [int(id) for id in selected_ids] if selected_ids else []
                is_soft = request.POST.get("delete_type") == "soft"
                if is_soft:
                    context = HorillaBulkDeleteMixin._soft_delete_all_dependencies(
                        self, item_id, selected_data
                    )
                    return render(request, "partials/soft_delete_form.html", context)
                context = HorillaBulkDeleteMixin._delete_all_dependencies(
                    self, item_id, selected_data
                )
                return render(request, "partials/bulk_delete_form.html", context)
            except json.JSONDecodeError as e:
                logger.error("JSON decode error: %s", e)
                self.object_list = self.get_queryset()
                context = self.get_context_data()
                context["error_message"] = "Invalid JSON data for record_ids."
                template = (
                    "partials/soft_delete_form.html"
                    if request.POST.get("delete_type") == "soft"
                    else "partials/bulk_delete_form.html"
                )
                return render(request, template, context)
            except ValueError as e:
                logger.error("Value error: %s", str(e))
                self.object_list = self.get_queryset()
                context = self.get_context_data()
                context["error_message"] = "Invalid record ID provided."
                template = (
                    "partials/soft_delete_form.html"
                    if request.POST.get("delete_type") == "soft"
                    else "partials/bulk_delete_form.html"
                )
                return render(request, template, context)

        # Infinite scroll: load more dependency records for a single parent record
        if action == "load_dep_records":
            try:
                item_id = int(request.POST.get("record_id", 0))
                dep_model_name = request.POST.get("dep_model_name", "")
                offset = int(request.POST.get("offset", 10))
                limit = 10
                search_url = getattr(self, "search_url", None) or request.path

                record = self.model.objects.get(id=item_id)
                for related in self.model._meta.related_objects:
                    related_model = related.related_model
                    if related_model._meta.verbose_name_plural == dep_model_name:
                        field_name = related.field.name
                        manager = getattr(
                            related_model,
                            "objects",
                            getattr(related_model, "all_objects", None),
                        )
                        if manager is None:
                            return HttpResponse("")
                        qs = manager.filter(**{field_name: record})
                        total = qs.count()
                        records = list(qs[offset : offset + limit])
                        next_offset = offset + limit
                        return render(
                            request,
                            "partials/dep_records_partial.html",
                            {
                                "records": [str(r) for r in records],
                                "has_more": next_offset < total,
                                "next_offset": next_offset,
                                "record_id": item_id,
                                "dep_model_name": dep_model_name,
                                "search_url": search_url,
                            },
                        )
                return HttpResponse("")
            except Exception as e:
                logger.error("Error loading more dependency records: %s", str(e))
                return HttpResponse("")

        # Not a bulk delete–related request
        return None

    def _check_dependencies(self, record_ids):
        """
        Check for dependencies in related models for the given record IDs.
        Returns two lists: records that cannot be deleted (with dependencies) and records that can be deleted.
        """
        from horilla.db.models import Prefetch

        can_delete = []
        cannot_delete = []

        str_fields = ["id"]
        queryset = self.model.objects.filter(id__in=record_ids).only(*str_fields)

        related_objects = self.model._meta.related_objects
        if not related_objects:
            for obj in queryset:
                can_delete.append({"id": obj.id, "name": str(obj)})
            return (cannot_delete, can_delete, {})

        prefetch_queries = []

        for related in related_objects:
            related_model = related.related_model
            related_name = related.get_accessor_name()
            if related_name:
                manager = getattr(
                    related_model,
                    "objects",
                    getattr(related_model, "all_objects", None),
                )
                if manager is None:
                    raise AttributeError(
                        f"No manager ('objects' or 'all_objects') defined for {related_model.__name__}"
                    )
                prefetch_queries.append(
                    Prefetch(
                        related_name,
                        queryset=manager.all(),
                        to_attr=f"prefetched_{related_name}",
                    )
                )

        try:
            queryset = queryset.prefetch_related(*prefetch_queries)
        except AttributeError as e:
            raise AttributeError(
                f"Invalid prefetch_related lookup. Check related_name for {self.model.__name__} relations. Error: {str(e)}"
            ) from e

        for obj in queryset:
            dependencies = []
            for related in related_objects:
                related_model = related.related_model
                related_name = related.get_accessor_name()
                field_name = related.field.name
                if related_name:
                    related_records = getattr(obj, f"prefetched_{related_name}", [])
                    if related_records:
                        manager = getattr(
                            related_model,
                            "objects",
                            getattr(related_model, "all_objects", None),
                        )
                        actual_count = (
                            manager.filter(**{field_name: obj}).count()
                            if manager is not None
                            else len(related_records)
                        )
                        dependencies.append(
                            {
                                "model_name": related_model._meta.verbose_name_plural,
                                "count": actual_count,
                                "records": [str(rec) for rec in related_records],
                            }
                        )

            if dependencies:
                cannot_delete.append(
                    {"id": obj.id, "name": str(obj), "dependencies": dependencies}
                )
            else:
                can_delete.append({"id": obj.id, "name": str(obj)})

        dependency_details = {
            item["id"]: item["dependencies"] for item in cannot_delete
        }

        return cannot_delete, can_delete, dependency_details

    def _delete_all_dependencies(self, item_id, selected_data):
        """
        Hard delete all dependencies of a single record, not the record itself.
        Returns the updated context for rendering the modal with remaining dependencies.
        """
        try:
            if isinstance(selected_data, int):
                selected_data = [selected_data]
            elif not isinstance(selected_data, (list, tuple)):
                selected_data = []

            if item_id not in selected_data:
                selected_data.append(item_id)

            record = self.model.objects.get(id=item_id)
            related_objects = self.model._meta.related_objects

            total_deleted_count = 0
            deleted_models = []

            for related in related_objects:
                related_model = related.related_model
                field_name = related.field.name
                filter_kwargs = {field_name: record}
                manager = getattr(
                    related_model,
                    "objects",
                    getattr(related_model, "all_objects", None),
                )
                if manager is None:
                    raise AttributeError(
                        f"No manager ('objects' or 'all_objects') defined for {related_model.__name__}"
                    )
                dependent_records = manager.filter(**filter_kwargs)
                count = dependent_records.count()

                if count > 0:
                    for dep_record in dependent_records:
                        dep_record.delete()
                    total_deleted_count += count
                    deleted_models.append(
                        f"{related_model._meta.verbose_name_plural} ({count})"
                    )

            cannot_delete, can_delete, _dependency_details = (
                HorillaBulkDeleteMixin._check_dependencies(self, selected_data)
            )

            can_delete_count = len(can_delete)

            if deleted_models:
                deleted_summary = ", ".join(deleted_models)
                success_message = f"Successfully hard deleted {total_deleted_count} dependencies: {deleted_summary}"
            else:
                success_message = f"No dependencies found for '{record}'"

            self.object_list = self.get_queryset()
            context = self.get_context_data()
            context.update(
                {
                    "selected_ids": selected_data,
                    "selected_ids_json": json.dumps(selected_data),
                    "cannot_delete": cannot_delete,
                    "can_delete": can_delete,
                    "cannot_delete_count": len(cannot_delete),
                    "can_delete_count": can_delete_count,
                    "success_message": success_message,
                    "model_verbose_name": self.model._meta.verbose_name_plural,
                }
            )

            return context

        except self.model.DoesNotExist:
            logger.error("Record with ID %s does not exist.", item_id)
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            context.update(
                {
                    "selected_ids": selected_data,
                    "selected_ids_json": json.dumps(selected_data),
                    "error_message": f"Record with ID {item_id} does not exist.",
                }
            )
            return context
        except Exception as e:
            logger.error("Hard delete of all dependencies failed: %s", str(e))
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            context.update(
                {
                    "selected_ids": selected_data,
                    "selected_ids_json": json.dumps(selected_data),
                    "error_message": f"Hard delete of all dependencies failed: {str(e)}",
                }
            )
            return context

    def _delete_item_with_dependencies(self, item_id, record_ids, selected_data):
        """
        Hard delete only the specified dependency of a single record, not the record itself.
        Returns the updated context for rendering the modal with remaining dependencies.
        """
        try:
            if isinstance(selected_data, int):
                selected_data = [selected_data]
            elif not isinstance(selected_data, (list, tuple)):
                selected_data = []

            if item_id not in selected_data:
                selected_data.append(item_id)

            record = self.model.objects.get(id=item_id)
            dep_model_name = self.request.POST.get("dep_model_name")
            related_objects = self.model._meta.related_objects

            deleted_count = 0
            for related in related_objects:
                related_model = related.related_model
                if related_model._meta.verbose_name_plural == dep_model_name:
                    field_name = related.field.name
                    filter_kwargs = {field_name: record}
                    manager = getattr(
                        related_model,
                        "objects",
                        getattr(related_model, "all_objects", None),
                    )
                    if manager is None:
                        raise AttributeError(
                            f"No manager ('objects' or 'all_objects') defined for {related_model.__name__}"
                        )
                    dependent_records = manager.filter(**filter_kwargs)

                    for dep_record in dependent_records:
                        dep_record.delete()
                        deleted_count += 1

            cannot_delete, can_delete, _dependency_details = (
                HorillaBulkDeleteMixin._check_dependencies(self, selected_data)
            )

            can_delete_count = len(can_delete)

            self.object_list = self.get_queryset()
            context = self.get_context_data()
            context.update(
                {
                    "selected_ids": selected_data,
                    "selected_ids_json": json.dumps(selected_data),
                    "cannot_delete": cannot_delete,
                    "can_delete": can_delete,
                    "cannot_delete_count": len(cannot_delete),
                    "can_delete_count": can_delete_count,
                    "success_message": f"Successfully hard deleted {deleted_count} '{dep_model_name}' dependencies of '{record}'.",
                    "model_verbose_name": self.model._meta.verbose_name_plural,
                }
            )

            return context

        except self.model.DoesNotExist:
            logger.error("Record with ID %s does not exist.", item_id)
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            context.update(
                {
                    "selected_ids": selected_data,
                    "selected_ids_json": json.dumps(selected_data),
                    "error_message": f"Record with ID {item_id} does not exist.",
                }
            )
            return context
        except Exception as e:
            logger.error("Hard delete of dependencies failed: %s", str(e))
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            context.update(
                {
                    "selected_ids": selected_data,
                    "selected_ids_json": json.dumps(selected_data),
                    "error_message": f"Hard delete of dependencies failed: {str(e)}",
                }
            )
            return context

    def _soft_delete_all_dependencies(self, item_id, selected_data):
        """
        Soft delete all dependencies of a single record; re-check and return
        context for soft_delete_form.
        """
        try:
            if isinstance(selected_data, int):
                selected_data = [selected_data]
            elif not isinstance(selected_data, (list, tuple)):
                selected_data = []

            if item_id not in selected_data:
                selected_data.append(item_id)

            record = self.model.objects.get(id=item_id)
            related_objects = self.model._meta.related_objects

            total_deleted_count = 0
            deleted_models = []

            for related in related_objects:
                related_model = related.related_model
                field_name = related.field.name
                filter_kwargs = {field_name: record}
                manager = getattr(
                    related_model,
                    "objects",
                    getattr(related_model, "all_objects", None),
                )
                if manager is None:
                    raise AttributeError(
                        f"No manager ('objects' or 'all_objects') defined for {related_model.__name__}"
                    )
                dependent_records = list(manager.filter(**filter_kwargs))

                if dependent_records:
                    for dep_record in dependent_records:
                        RecycleBin.create_from_instance(
                            dep_record, user=self.request.user
                        )
                        dep_record.delete()
                    total_deleted_count += len(dependent_records)
                    deleted_models.append(
                        f"{related_model._meta.verbose_name_plural} ({len(dependent_records)})"
                    )

            cannot_delete, can_delete, _ = HorillaBulkDeleteMixin._check_dependencies(
                self, selected_data
            )

            can_delete_count = len(can_delete)
            if deleted_models:
                deleted_summary = ", ".join(deleted_models)
                success_message = f"Successfully soft deleted {total_deleted_count} dependencies: {deleted_summary}"
            else:
                success_message = f"No dependencies found for '{record}'"

            self.object_list = self.get_queryset()
            context = self.get_context_data()
            context.update(
                {
                    "selected_ids": selected_data,
                    "selected_ids_json": json.dumps(selected_data),
                    "cannot_delete": cannot_delete,
                    "can_delete": can_delete,
                    "cannot_delete_count": len(cannot_delete),
                    "can_delete_count": can_delete_count,
                    "success_message": success_message,
                    "model_verbose_name": self.model._meta.verbose_name_plural,
                }
            )
            return context

        except self.model.DoesNotExist:
            logger.error("Record with ID %s does not exist.", item_id)
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            context.update(
                {
                    "selected_ids": selected_data,
                    "selected_ids_json": json.dumps(selected_data),
                    "error_message": f"Record with ID {item_id} does not exist.",
                }
            )
            return context
        except Exception as e:
            logger.error("Soft delete of all dependencies failed: %s", str(e))
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            context.update(
                {
                    "selected_ids": selected_data,
                    "selected_ids_json": json.dumps(selected_data),
                    "error_message": f"Soft delete of all dependencies failed: {str(e)}",
                }
            )
            return context

    def _soft_delete_item_with_dependencies(self, item_id, record_ids, selected_data):
        """
        Soft delete only the specified dependency of a single record; re-check
        and return context for soft_delete_form.
        """
        try:
            if isinstance(selected_data, int):
                selected_data = [selected_data]
            elif not isinstance(selected_data, (list, tuple)):
                selected_data = []

            if item_id not in selected_data:
                selected_data.append(item_id)

            record = self.model.objects.get(id=item_id)
            dep_model_name = self.request.POST.get("dep_model_name")
            related_objects = self.model._meta.related_objects

            deleted_count = 0
            for related in related_objects:
                related_model = related.related_model
                if related_model._meta.verbose_name_plural == dep_model_name:
                    field_name = related.field.name
                    filter_kwargs = {field_name: record}
                    manager = getattr(
                        related_model,
                        "objects",
                        getattr(related_model, "all_objects", None),
                    )
                    if manager is None:
                        raise AttributeError(
                            f"No manager ('objects' or 'all_objects') defined for {related_model.__name__}"
                        )
                    dependent_records = manager.filter(**filter_kwargs)

                    for dep_record in dependent_records:
                        RecycleBin.create_from_instance(
                            dep_record, user=self.request.user
                        )
                        dep_record.delete()
                        deleted_count += 1

            cannot_delete, can_delete, _ = HorillaBulkDeleteMixin._check_dependencies(
                self, selected_data
            )

            can_delete_count = len(can_delete)

            self.object_list = self.get_queryset()
            context = self.get_context_data()
            context.update(
                {
                    "selected_ids": selected_data,
                    "selected_ids_json": json.dumps(selected_data),
                    "cannot_delete": cannot_delete,
                    "can_delete": can_delete,
                    "cannot_delete_count": len(cannot_delete),
                    "can_delete_count": can_delete_count,
                    "success_message": f"Successfully soft deleted {deleted_count} '{dep_model_name}' dependencies of '{record}'.",
                    "model_verbose_name": self.model._meta.verbose_name_plural,
                }
            )
            return context

        except self.model.DoesNotExist:
            logger.error("Record with ID %s does not exist.", item_id)
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            context.update(
                {
                    "selected_ids": selected_data,
                    "selected_ids_json": json.dumps(selected_data),
                    "error_message": f"Record with ID {item_id} does not exist.",
                }
            )
            return context
        except Exception as e:
            logger.error("Soft delete of dependencies failed: %s", str(e))
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            context.update(
                {
                    "selected_ids": selected_data,
                    "selected_ids_json": json.dumps(selected_data),
                    "error_message": f"Soft delete of dependencies failed: {str(e)}",
                }
            )
            return context

    def _perform_soft_delete(self, record_ids):
        """
        Perform soft deletion by moving records and their dependencies to RecycleBin model.
        Returns the number of records deleted (main records only).
        """
        try:
            queryset = self.model.objects.filter(id__in=record_ids)
            deleted_count = 0
            for obj in queryset:
                related_objects = self.model._meta.related_objects
                for related in related_objects:
                    related_model = related.related_model
                    field_name = related.field.name
                    filter_kwargs = {field_name: obj}
                    manager = getattr(
                        related_model,
                        "objects",
                        getattr(related_model, "all_objects", None),
                    )
                    if manager is None:
                        raise AttributeError(
                            f"No manager ('objects' or 'all_objects') defined for {related_model.__name__}"
                        )
                    dependent_records = manager.filter(**filter_kwargs)
                    for dep_record in dependent_records:
                        RecycleBin.create_from_instance(
                            dep_record, user=self.request.user
                        )
                        dep_record.delete()
                RecycleBin.create_from_instance(obj, user=self.request.user)
                obj.delete()
                deleted_count += 1
            return deleted_count
        except Exception as e:
            logger.error("Soft delete failed: %s", str(e))
            raise
