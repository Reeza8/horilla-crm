"""
Split view layout: left panel = tile list, right panel = simple details of the selected item.
Uses the same queryset and filters as HorillaListView; tiles load detail fragment into the right panel via HTMX.
"""

# Standard library imports
import logging
from urllib.parse import urlencode

# Third-party imports (Django)
from django.template.loader import render_to_string

# First party imports (Horilla)
from horilla.shortcuts import render
from horilla.web import HttpResponse

# Local imports
from .list import HorillaListView

logger = logging.getLogger(__name__)


class HorillaSplitView(HorillaListView):
    """
    View for split layout: left = scrollable tile list, right = detail of clicked item.
    Reuses list queryset, filters, and columns. Tiles use col_attrs with hx-target
    pointing to the right panel and detail URL with layout=split for fragment response.
    """

    template_name = "split_view.html"
    supports_quick_filters = False
    # Split views should always use their explicit `columns` configuration
    # and not the per-user ListColumnVisibility settings from the list view.
    list_column_visibility = False
    bulk_select_option = False
    table_class = False
    table_width = False
    paginate_by = 50
    split_detail_target = "#splitViewDetailPanel"
    split_layout_param = "layout=split"

    def get_context_data(self, **kwargs):
        """Add split-specific col_attrs so tile clicks load detail into right panel."""
        context = super().get_context_data(**kwargs)
        # Override col_attrs for split view: target right panel and request fragment
        context["split_detail_target"] = self.split_detail_target
        context["split_layout_param"] = self.split_layout_param
        # Attach next/prev IDs to each object for tile nav (next/prev in detail panel)
        queryset = context.get("queryset") or []
        for i, obj in enumerate(queryset):
            obj.split_next_id = str(queryset[i + 1].id) if i + 1 < len(queryset) else ""
            obj.split_prev_id = str(queryset[i - 1].id) if i > 0 else ""
        # Auto-load first item in detail panel when none selected
        context["split_first_detail_url"] = None
        if queryset:
            first_obj = queryset[0]
            # Prefer get_detail_url; fall back to get_detail_view_url if available
            detail_method_name = None
            if hasattr(first_obj, "get_detail_url"):
                detail_method_name = "get_detail_url"
            elif hasattr(first_obj, "get_detail_view_url"):
                detail_method_name = "get_detail_view_url"
            if detail_method_name:
                first_url = getattr(first_obj, detail_method_name)()
                if first_url:
                    params = {"layout": "split"}
                    for key in ("section", "view_type"):
                        if self.request.GET.get(key):
                            params[key] = self.request.GET.get(key)
                    context["split_first_detail_url"] = (
                        first_url + "?" + urlencode(params)
                    )
        split_col_attrs = self._get_split_col_attrs(queryset=queryset)
        if split_col_attrs:
            first_col = (context.get("columns") or []) and context["columns"][0]
            if first_col:
                field_name = (
                    first_col[1] if isinstance(first_col, (list, tuple)) else first_col
                )
                col_attrs_dict = context.get("col_attrs") or {}
                col_attrs_dict[field_name] = split_col_attrs
                context["col_attrs"] = col_attrs_dict
        return context

    def _get_split_col_attrs(self, queryset=None):
        """Build col_attrs for the first column so clicking a tile loads detail in right panel.

        Uses whichever detail URL accessor the model provides:
        prefers get_detail_url, falls back to get_detail_view_url.
        """
        # Detect which placeholder to use based on the first object in the queryset
        detail_placeholder = "{get_detail_url}"
        if queryset:
            first_obj = queryset[0]
            if hasattr(first_obj, "get_detail_url"):
                detail_placeholder = "{get_detail_url}"
            elif hasattr(first_obj, "get_detail_view_url"):
                detail_placeholder = "{get_detail_view_url}"
            else:
                logger.warning(
                    "HorillaSplitView: neither get_detail_url nor get_detail_view_url "
                    "found on model %s; split tiles will not load details.",
                    type(first_obj),
                )

        query_params = {}
        for key in ("section", "view_type"):
            if self.request.GET.get(key):
                query_params[key] = self.request.GET.get(key)
        query_string = urlencode(query_params)
        base = f"{detail_placeholder}?{self.split_layout_param}&next_id={{split_next_id}}&prev_id={{split_prev_id}}"
        if query_string:
            base = f"{base}&{query_string}"
        attrs = {
            "hx-get": base,
            "hx-target": self.split_detail_target,
            "hx-swap": "innerHTML",
            "permission": getattr(self, "split_view_permission", None),
            "own_permission": getattr(self, "split_view_own_permission", None),
        }
        owner_method = getattr(self, "split_view_owner_method", None)
        if owner_method:
            attrs["owner_method"] = owner_method
        else:
            attrs["owner_field"] = getattr(self, "split_view_owner_field", "owner")
        return attrs

    def render_to_response(self, context, **response_kwargs):
        """Use split template for HTMX and full requests."""
        is_htmx = self.request.headers.get("HX-Request") == "true"
        context["request_params"] = self.request.GET.copy()
        if is_htmx:
            page_kwarg = getattr(self, "page_kwarg", "page")
            if self.request.GET.get(page_kwarg):
                html = render_to_string(
                    "partials/split_view_tiles.html",
                    context,
                    request=self.request,
                )
                return HttpResponse(html)
            return render(self.request, self.template_name, context)
        return super(HorillaListView, self).render_to_response(
            context, **response_kwargs
        )
