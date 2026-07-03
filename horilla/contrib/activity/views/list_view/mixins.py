"""
Shared mixins and constants for activity list views.
"""

from urllib.parse import urlencode

from django.utils.functional import cached_property  # type: ignore

from horilla.contrib.core.models import HorillaContentType
from horilla.contrib.core.utils import get_allowed_user_ids
from horilla.contrib.generics.views.details import (
    check_record_change_access,
    check_record_delete_access,
)
from horilla.contrib.utils.methods import get_section_info_for_model
from horilla.urls import resolve
from horilla.utils.translation import gettext_lazy as _
from horilla.web import HttpResponse

from ...filters import ActivityFilter
from ...models import Activity

_ACTIVITY_TYPE_TO_TAB = {
    "task": "tab-tasks",
    "meeting": "tab-meetings",
    "log_call": "tab-calls",
    "event": "tab-events",
}

# ---------------------------------------------------------------------------
# Shared action / col-attr constants used by global type list views
# ---------------------------------------------------------------------------

COMMON_COL_ATTRS_KWARGS = dict(
    permission="activity.change_activity",
    own_permission="activity.change_own_activity",
    owner_field="owner",
)

COMMON_ACTIONS = [
    {
        "action": "Edit",
        "src": "assets/icons/edit.svg",
        "img_class": "w-4 h-4",
        "permission": "activity.change_activity",
        "own_permission": "activity.change_own_activity",
        "owner_field": ["owner", "assigned_to"],
        "attrs": """
                    hx-get="{get_activity_edit_url}?new=true"
                    hx-target="#modalBox"
                    hx-swap="innerHTML"
                    onclick="openModal()"
                    """,
    },
    {
        "action": "Delete",
        "src": "assets/icons/a4.svg",
        "img_class": "w-4 h-4",
        "permission": "activity.delete_activity",
        "attrs": """
                    hx-post="{get_delete_url}"
                    hx-target="#deleteModeBox"
                    hx-swap="innerHTML"
                    hx-trigger="click"
                    hx-vals='{{"check_dependencies": "true"}}'
                    onclick="openDeleteModeModal()"
                """,
    },
    {
        "action": _("Duplicate"),
        "src": "assets/icons/duplicate.svg",
        "img_class": "w-4 h-4",
        "permission": "activity.add_activity",
        "attrs": """
                        hx-get="{get_activity_edit_url}?duplicate=true"
                        hx-target="#modalBox"
                        hx-swap="innerHTML"
                        onclick="openModal()"
                        """,
    },
]


class ActivityTabListMixin:
    """
    Mixin for activity tab list views (Task, Meeting, Call, Event).
    Provides a col_attrs cached_property that includes referrer params so that
    clicking a row navigates to the Activity detail view with the correct
    breadcrumb pointing back to the parent object.

    Also rewrites Edit/Delete actions based on the parent record's change/delete
    permissions — same pattern as HorillaRelatedListSectionView.
    """

    _col_attrs_first_field = "title"

    def _get_parent_object(self):
        """Resolve the parent object from object_id + content_type_id in the request."""
        object_id = self.kwargs.get("object_id")
        content_type_id = self.request.GET.get("content_type_id")
        if not object_id or not content_type_id:
            return None
        try:
            ct = HorillaContentType.objects.get(id=content_type_id)
            model_class = ct.model_class()
            return model_class.objects.get(pk=object_id)
        except Exception:
            return None

    def _filter_tab_actions(self, actions, parent_obj):
        """
        Rewrite actions based on parent record permissions — mirrors
        HorillaRelatedListSectionView._filter_actions_for_user().

        - Global Change on parent → Edit shown for all rows (no permission keys)
        - Change Own on parent → Edit shown only for own/subordinate rows (hidden_if)
        - No change access → Edit removed
        - Delete follows the same logic with delete access
        - No parent object → return actions unchanged (fallback to activity perms)
        """
        if not parent_obj:
            return actions

        user = self.request.user
        app = parent_obj._meta.app_label
        model = parent_obj._meta.model_name
        has_global_change = user.is_superuser or user.has_perm(f"{app}.change_{model}")
        has_global_delete = user.is_superuser or user.has_perm(f"{app}.delete_{model}")
        can_change = has_global_change or check_record_change_access(user, parent_obj)
        can_delete = has_global_delete or check_record_delete_access(user, parent_obj)

        _CHANGE_KEYWORDS = {"edit", "change", "update"}
        _DELETE_KEYWORDS = {"delete", "remove"}
        _STRIP_KEYS = {"permission", "own_permission", "owner_field", "owner_method"}

        allowed_ids = get_allowed_user_ids(user)

        def _hidden_if_not_allowed(activity):
            owner = getattr(activity, "owner", None)
            assigned = getattr(activity, "assigned_to", None)
            owners = []
            if owner:
                owners.append(owner.pk if hasattr(owner, "pk") else owner)
            if assigned:
                if hasattr(assigned, "all"):
                    owners.extend(u.pk for u in assigned.all())
                else:
                    owners.append(assigned.pk if hasattr(assigned, "pk") else assigned)
            if not owners:
                return False
            return not any(pk in allowed_ids for pk in owners)

        rewritten = []
        for action in actions:
            if not isinstance(action, dict):
                rewritten.append(action)
                continue
            label = str(action.get("action", "")).lower()
            if any(k in label for k in _CHANGE_KEYWORDS):
                if not can_change:
                    continue
                if has_global_change:
                    action = {k: v for k, v in action.items() if k not in _STRIP_KEYS}
                else:
                    action = {k: v for k, v in action.items() if k not in _STRIP_KEYS}
                    action["hidden_if"] = _hidden_if_not_allowed
            elif any(k in label for k in _DELETE_KEYWORDS):
                if not can_delete:
                    continue
                if has_global_delete:
                    action = {k: v for k, v in action.items() if k not in _STRIP_KEYS}
                else:
                    action = {k: v for k, v in action.items() if k not in _STRIP_KEYS}
                    action["hidden_if"] = _hidden_if_not_allowed
            rewritten.append(action)
        return rewritten

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        parent_obj = self._get_parent_object()
        if parent_obj and hasattr(self, "actions") and self.actions:
            self.actions = self._filter_tab_actions(list(self.actions), parent_obj)
            context["actions"] = self.actions
        return context

    @cached_property
    def col_attrs(self):
        """Return col_attrs with HTMX referrer params for navigating to the activity detail."""
        object_id = self.kwargs.get("object_id")
        content_type_id = self.request.GET.get("content_type_id")

        activity_section = get_section_info_for_model(Activity).get("section", "")

        referrer_params = ""
        if object_id and content_type_id:
            try:
                content_type = HorillaContentType.objects.get(id=content_type_id)
                parent_model_class = content_type.model_class()
                app_label = parent_model_class._meta.app_label
                model_name = parent_model_class._meta.model_name

                parent_obj = parent_model_class.objects.filter(pk=object_id).first()
                referrer_url = ""
                if parent_obj and hasattr(parent_obj, "get_detail_url"):
                    try:
                        detail_path = str(parent_obj.get_detail_url())
                        resolved = resolve(detail_path)
                        referrer_url = resolved.url_name or ""
                    except Exception:
                        pass

                referrer_params = (
                    f"referrer_app={app_label}"
                    f"&referrer_model={model_name}"
                    f"&referrer_id={object_id}"
                    f"&referrer_url={referrer_url}"
                )
            except Exception:
                pass

        section_param = f"&section={activity_section}" if activity_section else ""
        if referrer_params:
            hx_get = f"{{get_detail_url}}?{referrer_params}{section_param}"
        else:
            hx_get = (
                f"{{get_detail_url}}?{section_param.lstrip('&')}"
                if section_param
                else "{get_detail_url}"
            )

        return [
            {
                self._col_attrs_first_field: {
                    "hx-get": hx_get,
                    "hx-target": "#mainContent",
                    "hx-swap": "outerHTML",
                    "hx-push-url": "true",
                    "hx-select": "#mainContent",
                    "hx-select-oob": "#sideMenuContainer",
                    "permission": "activity.change_activity",
                    "own_permission": "activity.change_own_activity",
                    "owner_field": "owner",
                }
            }
        ]


class GlobalTypeListMixin:
    """
    Shared base for global per-type list views (not tied to a parent object).
    Filters the queryset to a single activity_type and wires up the HTMX
    col_attrs so clicking a row opens the activity detail page.
    """

    _activity_type: str = ""

    filterset_class = ActivityFilter
    model = Activity
    bulk_update_fields = ["status"]
    actions = COMMON_ACTIONS
    table_height_as_class = "h-[calc(_100vh_-_340px_)]"

    def get_main_url(self):
        """
        Return the outer shell URL so the filter panel's hx-select="#mainSession"
        finds the element it needs. The shell (ActivityView / HorillaView) renders
        base.html which contains #mainSession, and it forwards all GET params
        (including apply_filter) to the tabbed list view.
        """
        from horilla.urls import reverse_lazy as _reverse_lazy

        return _reverse_lazy("activity:activity_view")

    @cached_property
    def col_attrs(self):
        """Return col_attrs with HTMX attrs for navigating to the activity detail."""
        query_params = {}
        if "section" in self.request.GET:
            query_params["section"] = self.request.GET.get("section")
        query_string = urlencode(query_params)
        return [
            {
                "subject": {
                    "hx-get": f"{{get_detail_url}}?{query_string}",
                    "hx-target": "#mainContent",
                    "hx-swap": "outerHTML",
                    "hx-push-url": "true",
                    "hx-select": "#mainContent",
                    **COMMON_COL_ATTRS_KWARGS,
                }
            }
        ]

    def get_queryset(self):
        """Filter the queryset to only this mixin's activity type."""
        return super().get_queryset().filter(activity_type=self._activity_type)

    @property
    def search_url(self):
        """Return the search URL for this global list view."""
        return self.get_search_url()

    @property
    def main_url(self):
        """Return the main URL for this global list view."""
        return self.get_main_url()

    def post(self, request, *args, **kwargs):
        """
        Intercept bulk action responses and replace the generic #reloadButton trigger
        with a tab-specific click so the correct tab reloads instead of always
        reverting to the first tab.
        """
        response = super().post(request, *args, **kwargs)
        tab_id = _ACTIVITY_TYPE_TO_TAB.get(self._activity_type)
        if (
            tab_id
            and isinstance(response, HttpResponse)
            and b"$('#reloadButton').click()" in response.content
        ):
            patched = response.content.replace(
                b"$('#reloadButton').click()",
                f"htmx.trigger('#{tab_id}','click')".encode(),
            )
            return HttpResponse(patched, content_type="text/html")
        return response
