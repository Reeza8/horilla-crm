"""
Generic view for displaying data in a grouped list layout.
Groups rows by a selected field (ChoiceField or ForeignKey) and displays.
"""

# Standard library imports
import logging

# Third-party imports (Django)
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.template.loader import render_to_string

from horilla.contrib.core.models import KanbanGroupBy
from horilla.contrib.core.utils import get_user_field_permission
from horilla.core.exceptions import FieldError
from horilla.db.models import ForeignKey
from horilla.shortcuts import render

# First-party (Horilla)
from horilla.urls import reverse
from horilla.utils.decorators import htmx_required, method_decorator
from horilla.utils.text import slugify
from horilla.utils.translation import gettext_lazy as _
from horilla.web import HttpResponse

# Local imports
from .list import HorillaListView

logger = logging.getLogger(__name__)


@method_decorator(htmx_required, name="dispatch")
class HorillaGroupByView(HorillaListView):
    """
    Generic view for displaying data in a grouped list layout.
    Groups rows by a selected field (ChoiceField or ForeignKey) and displays
    them as collapsible sections. Uses same group-by preference as Kanban.
    """

    template_name = "group_by_view.html"
    group_by_field = None
    filterset_module = "filters"
    bulk_select_option = False
    table_class = True
    paginate_by = 20

    _view_registry = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "model") and cls.model:
            HorillaGroupByView._view_registry[cls.model] = cls

    def _get_kanban_exclude_include_fields(self, view_type="group_by"):
        """Return (exclude_fields, include_fields) used by Kanban/GroupBy settings for this view."""
        exclude_str = getattr(self, "exclude_kanban_fields", "") or ""
        exclude_fields = [f.strip() for f in exclude_str.split(",") if f.strip()]
        include_fields = getattr(self, "include_kanban_fields", None)
        return exclude_fields, include_fields

    def _get_allowed_group_by_fields(self, view_type="group_by"):
        """Return list of field names the user is allowed to group by (respects field permissions
        and exclude_kanban_fields so we only consider fields shown in settings).
        """
        model_name = self.model.__name__
        app_label = self.model._meta.app_label
        exclude_fields, include_fields = self._get_kanban_exclude_include_fields(
            view_type
        )
        temp = KanbanGroupBy(model_name=model_name, app_label=app_label)
        choices = temp.get_model_groupby_fields(
            user=self.request.user,
            exclude_fields=exclude_fields,
            include_fields=include_fields,
        )
        return [c[0] for c in choices]

    def _is_field_visible_for_group_by(self, field_name):
        """Check if a field is visible (not hidden) for the current user."""
        if not field_name:
            return False
        perm = get_user_field_permission(self.request.user, self.model, field_name)
        return perm != "hidden"

    def get_group_by_field(self):
        """Return the field used to group rows. Uses separate preference from Kanban.
        Falls back to an allowed field when the preferred field has 'hidden' permission.
        Never returns a field with 'hidden' permission.
        """
        model_name = self.model.__name__
        app_label = self.model._meta.app_label
        default_group = KanbanGroupBy.all_objects.filter(
            model_name=model_name,
            app_label=app_label,
            user=self.request.user,
            view_type="group_by",
        ).first()
        preferred = default_group.field_name if default_group else self.group_by_field
        allowed = self._get_allowed_group_by_fields(view_type="group_by")
        if (
            preferred
            and preferred in allowed
            and self._is_field_visible_for_group_by(preferred)
        ):
            return preferred
        for field_name in allowed:
            if self._is_field_visible_for_group_by(field_name):
                return field_name
        return None

    def get_context_data(self, **kwargs):
        """Populate context with grouped items for list display."""
        if not hasattr(self, "object_list"):
            self.object_list = self.get_queryset()

        context = super().get_context_data(**kwargs)
        queryset = self.object_list
        group_by = self.get_group_by_field()

        app_label = self.model._meta.app_label if self.model else ""
        model_name = self.model.__name__ if self.model else ""
        context["app_label"] = app_label
        context["model_name"] = model_name

        if not group_by:
            context["error"] = _(
                "No grouping field specified or you don't have permission to view any grouping fields."
            )
            return context

        try:
            field = self.model._meta.get_field(group_by)
            if not (
                (hasattr(field, "choices") and field.choices)
                or isinstance(field, ForeignKey)
            ):
                context["error"] = _(
                    "Field '%(field)s' is not a Choice field or ForeignKey field."
                ) % {"field": group_by}
                return context

            grouped_items = {}
            paginated_groups = {}
            paginate_by = getattr(self, "paginate_by", 20)

            if hasattr(field, "choices") and field.choices:
                for value, label in field.choices:
                    grouped_items[value] = {
                        "label": label,
                        "items": queryset.filter(**{group_by: value}).order_by("id"),
                    }
                existing_values = set(queryset.values_list(group_by, flat=True))
                for value in existing_values:
                    if value not in grouped_items:
                        grouped_items[value] = {
                            "label": f"Unknown ({value})",
                            "items": queryset.filter(**{group_by: value}).order_by(
                                "id"
                            ),
                        }
                sorted_items = {}
                for value, __ in field.choices:
                    if value in grouped_items:
                        sorted_items[value] = grouped_items[value]
                for key, group in grouped_items.items():
                    if key not in sorted_items:
                        sorted_items[key] = group

                for key, group in sorted_items.items():
                    total_count = group["items"].count()
                    ordered_items = group["items"].order_by("id")
                    paginator = Paginator(ordered_items, paginate_by)
                    page = self.request.GET.get(f"page_{key}", 1)
                    try:
                        page_obj = paginator.page(page)
                    except PageNotAnInteger:
                        page_obj = paginator.page(1)
                    except EmptyPage:
                        page_obj = paginator.page(paginator.num_pages)
                    load_more_params = self.request.GET.copy()
                    load_more_params["group_key"] = key
                    load_more_params["page"] = (
                        page_obj.next_page_number() if page_obj.has_next() else 1
                    )
                    app_label = self.model._meta.app_label
                    model_name = self.model.__name__
                    load_more_base = reverse(
                        "generics:group_by_load_more",
                        kwargs={"app_label": app_label, "model_name": model_name},
                    )
                    paginated_groups[key] = {
                        "label": group["label"],
                        "items": page_obj.object_list,
                        "page_obj": page_obj,
                        "has_next": page_obj.has_next(),
                        "next_page": (
                            page_obj.next_page_number() if page_obj.has_next() else None
                        ),
                        "total_count": total_count,
                        "load_more_url": f"{load_more_base}?{load_more_params.urlencode()}",
                        "data_container_id": f"{self.view_id}-{slugify(str(key))}",
                    }

            elif isinstance(field, ForeignKey):
                queryset = queryset.prefetch_related(group_by)
                related_model = field.related_model
                if "order" in [f.name for f in related_model._meta.fields]:
                    related_items = related_model.objects.all().order_by("order")
                else:
                    related_items = related_model.objects.all().order_by("pk")

                for related_item in related_items:
                    grouped_items[related_item.pk] = {
                        "label": str(related_item),
                        "items": queryset.filter(
                            **{f"{group_by}__pk": related_item.pk}
                        ).order_by("id"),
                    }

                if field.null:
                    grouped_items[None] = {
                        "label": _("None"),
                        "items": queryset.filter(
                            **{f"{group_by}__isnull": True}
                        ).order_by("id"),
                    }

                if None in grouped_items and not grouped_items[None]["items"].exists():
                    del grouped_items[None]

                sorted_items = {}
                for related_item in related_items:
                    if related_item.pk in grouped_items:
                        sorted_items[related_item.pk] = grouped_items[related_item.pk]
                if None in grouped_items:
                    sorted_items[None] = grouped_items[None]

                for key, group in sorted_items.items():
                    total_count = group["items"].count()
                    ordered_items = group["items"].order_by("id")
                    paginator = Paginator(ordered_items, paginate_by)
                    page = self.request.GET.get(f"page_{key}", 1)
                    try:
                        page_obj = paginator.page(page)
                    except PageNotAnInteger:
                        page_obj = paginator.page(1)
                    except EmptyPage:
                        page_obj = paginator.page(paginator.num_pages)
                    load_more_params = self.request.GET.copy()
                    load_more_params["group_key"] = key
                    load_more_params["page"] = (
                        page_obj.next_page_number() if page_obj.has_next() else 1
                    )
                    app_label = self.model._meta.app_label
                    model_name = self.model.__name__
                    load_more_base = reverse(
                        "generics:group_by_load_more",
                        kwargs={"app_label": app_label, "model_name": model_name},
                    )
                    paginated_groups[key] = {
                        "label": group["label"],
                        "items": page_obj.object_list,
                        "page_obj": page_obj,
                        "has_next": page_obj.has_next(),
                        "next_page": (
                            page_obj.next_page_number() if page_obj.has_next() else None
                        ),
                        "total_count": total_count,
                        "load_more_url": f"{load_more_base}?{load_more_params.urlencode()}",
                        "data_container_id": f"{self.view_id}-{slugify(str(key))}",
                    }

            context["grouped_items"] = paginated_groups
            context["group_by_field"] = group_by
            context["group_by_label"] = field.verbose_name
            context["queryset"] = queryset
            context["total_records_count"] = queryset.count()

        except FieldError as e:
            context["error"] = _("Invalid grouping field '%(field)s': %(err)s") % {
                "field": group_by,
                "err": str(e),
            }
        except Exception as e:
            context["error"] = _("Error grouping by field '%(field)s': %(err)s") % {
                "field": group_by,
                "err": str(e),
            }
        return context

    def load_more_items(self, request, *args, **kwargs):
        """
        Load more items for a specific group with filters and search applied.
        Returns table rows (tr elements) for the next page of the group.
        """
        group_key = request.GET.get("group_key")
        page = request.GET.get("page")
        group_by = self.get_group_by_field()

        if not page or not group_by:
            return HttpResponse(status=400, content="Missing required parameters")

        try:
            field = self.model._meta.get_field(group_by)
            if group_key == "None":
                group_key = None
            elif isinstance(field, ForeignKey) and group_key and group_key.isdigit():
                group_key = int(group_key)

            queryset = self.get_queryset()

            if hasattr(field, "choices") and field.choices:
                items = queryset.filter(**{group_by: group_key}).order_by("id")
            elif isinstance(field, ForeignKey):
                if group_key is None:
                    items = queryset.filter(**{f"{group_by}__isnull": True}).order_by(
                        "id"
                    )
                else:
                    items = queryset.filter(**{f"{group_by}__pk": group_key}).order_by(
                        "id"
                    )
            else:
                return HttpResponse(status=400, content="Invalid group field")

            paginate_by = getattr(self, "paginate_by", 20)
            paginator = Paginator(items, paginate_by)
            try:
                page_obj = paginator.page(page)
            except PageNotAnInteger:
                page_obj = paginator.page(1)
            except EmptyPage:
                return HttpResponse("")

            context = self.get_context_data()
            context["queryset"] = page_obj.object_list
            context["has_next"] = page_obj.has_next()
            context["next_page"] = (
                page_obj.next_page_number() if page_obj.has_next() else None
            )
            context["group_key"] = group_key
            context["data_container_id"] = (
                f"{self.get_view_id()}-{slugify(str(group_key))}"
            )
            load_more_params = request.GET.copy()
            load_more_params["group_key"] = group_key
            load_more_params["page"] = (
                page_obj.next_page_number() if page_obj.has_next() else 1
            )
            app_label = self.model._meta.app_label
            model_name = self.model.__name__
            load_more_base = reverse(
                "generics:group_by_load_more",
                kwargs={"app_label": app_label, "model_name": model_name},
            )
            context["group_by_load_more_url"] = (
                f"{load_more_base}?{load_more_params.urlencode()}"
            )
            context["search_params"] = request.GET.urlencode()

            return HttpResponse(
                render_to_string(
                    "partials/group_by_load_more_rows.html", context, request=request
                )
            )
        except Exception as e:
            logger.error("Group by load more failed: %s", str(e))
            return HttpResponse(status=500, content=f"Error: {str(e)}")

    def get_view_id(self):
        """Return the view_id for this view."""
        return getattr(self, "view_id", "group-by-view")

    def render_to_response(self, context, **response_kwargs):
        """Override to ensure HTMX requests get the group_by template."""
        is_htmx = self.request.headers.get("HX-Request") == "true"
        context["request_params"] = self.request.GET.copy()
        if is_htmx:
            return render(self.request, self.template_name, context)
        return super().render_to_response(context, **response_kwargs)
